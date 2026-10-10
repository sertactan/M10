"""Current-stock RESEARCH pilot; deliberately separate from canonical PIT / production DB.

Free Yahoo-compatible data is not an exchange-certified live feed. Cached SEC
companyfacts with missing accepted_at are research evidence, not accepted PIT.
Never create model score inputs by substituting unknowns with neutral numbers.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from contextlib import closing
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import sqlite3
from statistics import mean, pstdev

import httpx

from app.feature_materializer import _cagr, _growth, _score_growth
from core.historical.s16_feature_coverage import S16_REQUIRED_FEATURES, assess_feature_coverage
from core.models.s153_v12 import S153V12Model
from core.models.s153_v12_contracts import S153V12Input
from core.models.s153_v141 import S153V141Model
from core.models.s153_v14_contracts import S153V14Input
from core.scoring.s1_s14 import s1, s2, s3, s14
from core.scoring.math import pos_score, wa

SCHEMA_VERSION = "M10_PHASE27_CURRENT_RESEARCH_V1"
PROVIDER = "YAHOO_COMPAT_RESEARCH"
URL = "https://query2.finance.yahoo.com/v8/finance/chart/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/154.0 Safari/537.36"
METRICS = ("REVENUE", "NET_INCOME", "OPERATING_INCOME", "GROSS_PROFIT",
           "OPERATING_CASH_FLOW", "CAPEX", "CASH", "LONG_TERM_DEBT",
           "SHARES_OUTSTANDING", "SBC", "DILUTED_EPS")
PRICE_CUTOFF_DAYS = 4  # research freshness heuristic, NOT an exchange SLA


def check_ticker(ticker: str) -> str:
    t = ticker.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,11}", t):
        raise ValueError("Ticker contains unsupported characters")
    return t


def stage_connect(path: Path) -> sqlite3.Connection:
    """Refuse existing non-stage SQLite; caller must pass isolated Phase27 path."""
    resolved = path.resolve()
    if "phase27" not in {part.lower() for part in resolved.parts} or path.name.lower() == "operational.db":
        raise ValueError("Stage path must contain a dedicated phase27 component")
    if path.is_symlink():
        raise ValueError("Stage SQLite symlink rejected")
    if path.is_file():
        # Inspect BEFORE any DDL to avoid accidentally mutating an existing
        # operational/user SQLite database passed as a stage argument.
        with closing(sqlite3.connect(resolved.as_uri() + "?mode=ro", uri=True)) as probe:
            tables = probe.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='stage_meta'"
            ).fetchall()
            schema = (probe.execute("SELECT schema FROM stage_meta").fetchall()
                      if tables else [])
        if len(schema) != 1 or schema[0][0] != SCHEMA_VERSION:
            raise ValueError("Refusing non-Phase27 existing SQLite")
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript("""
      CREATE TABLE IF NOT EXISTS stage_meta(schema TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS stock_runs(
       ticker TEXT PRIMARY KEY, security_id TEXT, cik TEXT, quote_status TEXT,
       finance_status TEXT, quote_price REAL, quote_currency TEXT, quote_time TEXT,
       quote_trade_date TEXT, quote_source TEXT, financial_period TEXT,
       checked_at TEXT NOT NULL, details_json TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS research_bars(
       ticker TEXT NOT NULL, trade_date TEXT NOT NULL,
       o REAL NOT NULL,h REAL NOT NULL,l REAL NOT NULL,c REAL NOT NULL,
       adjusted REAL,volume REAL, source TEXT NOT NULL,
       source_ref TEXT NOT NULL,retrieved_at TEXT NOT NULL,evidence_hash TEXT NOT NULL,
       PRIMARY KEY(ticker,trade_date,source));
      CREATE TABLE IF NOT EXISTS research_facts(
       ticker TEXT NOT NULL,metric TEXT NOT NULL,period_start TEXT,period_end TEXT NOT NULL,
       period_kind TEXT,form_type TEXT,accession TEXT,accepted_at TEXT,
       available_at TEXT,filing_date TEXT,value REAL NOT NULL,unit TEXT,
       source TEXT NOT NULL,source_ref TEXT,evidence_hash TEXT NOT NULL,
       PRIMARY KEY(ticker,metric,period_end,period_start,period_kind,accession));
      CREATE TABLE IF NOT EXISTS research_features(
       ticker TEXT NOT NULL,security_id TEXT,feature_key TEXT NOT NULL,value REAL,
       as_of TEXT NOT NULL,available_at TEXT,source TEXT NOT NULL,source_ref TEXT,
       quality_status TEXT NOT NULL,computation_version TEXT NOT NULL,
       evidence_hash TEXT NOT NULL, PRIMARY KEY(ticker,feature_key,as_of));
      CREATE TABLE IF NOT EXISTS model_audits(
       ticker TEXT NOT NULL,model TEXT NOT NULL,version TEXT,score REAL,
       status TEXT NOT NULL,coverage REAL NOT NULL,missing_json TEXT NOT NULL,
       evidence_json TEXT NOT NULL,PRIMARY KEY(ticker,model));
      CREATE TABLE IF NOT EXISTS provider_events(
       event_id INTEGER PRIMARY KEY AUTOINCREMENT,ticker TEXT NOT NULL,
       status TEXT NOT NULL,checked_at TEXT NOT NULL,detail TEXT);
    """)
    rows = con.execute("SELECT schema FROM stage_meta").fetchall()
    if rows and (len(rows) != 1 or rows[0][0] != SCHEMA_VERSION):
        con.close()
        raise ValueError("Refusing unknown stage database schema")
    if not rows:
        con.execute("INSERT INTO stage_meta(schema) VALUES (?)", (SCHEMA_VERSION,))
    # SQLite UNIQUE/PRIMARY KEY permits multiple NULL components on rowid tables.
    # Normalize nullable period fields in a stage-only expression index. Migrate
    # duplicates left by older phase27 prototypes before creating the index.
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='index' "
                       "AND name='phase27_facts_null_safe_unique'").fetchone():
        con.execute("""
          DELETE FROM research_facts WHERE rowid NOT IN (
            SELECT MAX(rowid) FROM research_facts
            GROUP BY ticker,metric,period_end,COALESCE(period_start,''),
                     COALESCE(period_kind,''),COALESCE(accession,'')
          )
        """)
        con.execute("""
          CREATE UNIQUE INDEX phase27_facts_null_safe_unique
          ON research_facts(ticker,metric,period_end,COALESCE(period_start,''),
                            COALESCE(period_kind,''),COALESCE(accession,''))
        """)
    con.commit()
    return con


def load_identity(archive: Path, ticker: str) -> tuple[str, str, list[dict]]:
    """No writes, no private DB migration, no implied independent SEC acceptance."""
    if archive.is_symlink() or not archive.is_file():
        raise FileNotFoundError("Verified research source archive unavailable")
    uri = archive.resolve().as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True, timeout=4)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        matches = db.execute(
            "SELECT security_id,cik,market FROM security_master WHERE ticker=? AND market='US'",
            (ticker,),
        ).fetchall()
        if len(matches) != 1 or not matches[0]["cik"]:
            raise ValueError("No unique verified US ticker/CIK identity")
        sid, cik = matches[0]["security_id"], matches[0]["cik"]
        facts = [dict(row) for row in db.execute(
            "SELECT metric_name,value,unit,period_start,period_end,period_kind,"
            "filing_date,accepted_at,available_at,source,source_document,"
            "accession_number,form_type,raw_payload_hash,quality_status "
            "FROM fundamental_facts_source WHERE security_id=? AND source='SEC_EDGAR' "
            "AND metric_name IN (" + ",".join("?" * len(METRICS)) + ") "
            "ORDER BY period_end DESC LIMIT 2500", (sid, *METRICS)
        )]
    return sid, cik, facts


def parse_yahoo_chart(payload: dict, ticker: str, retrieved_at: datetime) -> tuple[list[dict], dict]:
    result = (payload.get("chart") or {}).get("result") or []
    if len(result) != 1:
        raise ValueError("Yahoo chart result missing or ambiguous")
    entry = result[0]
    meta = entry.get("meta") or {}
    if meta.get("symbol") != ticker or meta.get("currency") != "USD":
        raise ValueError("Ticker/currency mismatch; research price rejected")
    q = ((entry.get("indicators") or {}).get("quote") or [{}])[0]
    adj = ((entry.get("indicators") or {}).get("adjclose") or [{}])[0].get("adjclose") or []
    timestamps = entry.get("timestamp") or []
    bars = []
    seen = set()
    now = retrieved_at.astimezone(timezone.utc)
    for i, ts in enumerate(timestamps):
        stamp = datetime.fromtimestamp(int(ts), timezone.utc)
        if stamp > now + timedelta(minutes=5):
            raise ValueError("Future price timestamp rejected")
        trade_day = stamp.date().isoformat()
        if trade_day in seen:
            raise ValueError("Duplicate daily price date")
        seen.add(trade_day)
        try:
            fields = [q[k][i] for k in ("open", "high", "low", "close", "volume")]
        except (IndexError, KeyError, TypeError):
            continue
        if any(v is None for v in fields):
            continue
        o, h, l, c, vol = map(float, fields)
        if not all(math.isfinite(x) for x in (o, h, l, c, vol)):
            continue
        if o <= 0 or h <= 0 or l <= 0 or c <= 0 or vol < 0 or l > h or c < l * 0.90 or c > h * 1.10:
            continue
        adj_price = adj[i] if i < len(adj) else None
        if adj_price is not None and (not math.isfinite(float(adj_price)) or float(adj_price) <= 0):
            adj_price = None
        bars.append(dict(trade_date=trade_day, o=o, h=h, l=l, c=c,
                         adjusted=(float(adj_price) if adj_price is not None else None),
                         volume=vol, timestamp=stamp.isoformat()))
    bars.sort(key=lambda item: item["trade_date"])
    if not bars:
        raise ValueError("No valid timestamped Yahoo OHLCV")
    return bars, meta


def yahoo_fetch(ticker: str, *, timeout: float = 12) -> tuple[list[dict], dict, str, datetime]:
    """One bounded request, no credential scraping, no unbounded retries."""
    retrieved = datetime.now(timezone.utc)
    with httpx.Client(timeout=timeout, follow_redirects=True,
                      headers={"User-Agent": UA, "Accept": "application/json"}) as client:
        response = client.get(URL + ticker, params={
            "range": "1y", "interval": "1d", "events": "div,splits",
            "includeAdjustedClose": "true",
        })
        response.raise_for_status()
        if "json" not in response.headers.get("content-type", "").lower():
            raise ValueError("Price provider returned non-JSON content")
        payload = response.json()
    rows, meta = parse_yahoo_chart(payload, ticker, retrieved)
    return rows, meta, sha256(response.content).hexdigest(), retrieved


def _put_feature(db: sqlite3.Connection, ticker: str, sid: str, key: str, value: float,
                 as_of: str, available_at: str, source: str, source_ref: str, evidence: str) -> None:
    if not math.isfinite(value):
        return
    db.execute("INSERT OR REPLACE INTO research_features VALUES (?,?,?,?,?,?,?,?,?,?,?)",
               (ticker, sid, key, float(value), as_of, available_at, source, source_ref,
                "RESEARCH_ONLY_NOT_CANONICAL_PIT", "phase27-current-v1",
                sha256(evidence.encode()).hexdigest()))


def price_features(db: sqlite3.Connection, ticker: str, sid: str, bars: list[dict],
                   quote_ref: str, payload_hash: str, at: str) -> dict[str, float]:
    closes = [x["c"] for x in bars]
    volumes = [x["volume"] for x in bars]
    latest = bars[-1]
    values: dict[str, float] = {"RAW_CURRENT_PRICE": latest["c"]}
    for days in (20, 50, 200):
        if len(closes) >= days:
            values[f"SMA_{days}"] = mean(closes[-days:])
    if len(volumes) >= 21 and mean(volumes[-21:-1]) > 0:
        values["RVOL_20_PRIOR"] = volumes[-1] / mean(volumes[-21:-1])
    if len(closes) >= 6:
        values["WEEKLY_RETURN_5_SESSION"] = closes[-1] / closes[-6] - 1
    if len(closes) >= 2:
        values["DAILY_RETURN"] = closes[-1] / closes[-2] - 1
    if len(closes) >= 21 and all(closes[i] > 0 for i in range(-21, 0)):
        log_returns = [math.log(closes[i] / closes[i-1]) for i in range(-19, 0)]
        values["VOLATILITY_20_ANNUALIZED"] = pstdev(log_returns) * math.sqrt(252)
    # Existing frozen materializer's explicit normalization; research component ONLY.
    if len(bars) >= 120:
        avg20 = mean(volumes[-20:])
        avg120 = mean(volumes[-120:])
        if avg120 > 0:
            values["TURNACC_RESEARCH"] = pos_score(avg20 / avg120, 1.0, 3.0)
    if len(bars) >= 200:
        sma200 = values["SMA_200"]
        if sma200 > 0:
            values["PIR_EXT_P200_ONLY_RESEARCH"] = pos_score(closes[-1]/sma200-1, 0.2, 1.0)
    for key, value in values.items():
        _put_feature(db, ticker, sid, key, value, latest["trade_date"], at,
                     PROVIDER, quote_ref, payload_hash + key + str(value))
    return values


def finance_features(db: sqlite3.Connection, ticker: str, sid: str, facts: list[dict],
                     as_of: str) -> tuple[dict[str, float], str | None]:
    latest_period = None
    visible = []
    for x in facts:
        available = x.get("available_at")
        if not available or available[:10] > as_of:
            continue
        if x.get("form_type") not in ("10-K", "10-Q") or not x.get("accession_number"):
            continue
        if x.get("metric_name") not in METRICS:
            continue
        if x["value"] is None or not math.isfinite(float(x["value"])):
            continue
        visible.append(x)
        if x["metric_name"] != "SHARES_OUTSTANDING":
            latest_period = max(latest_period or x["period_end"], x["period_end"])
        db.execute("INSERT OR REPLACE INTO research_facts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (ticker, x["metric_name"], x.get("period_start"), x["period_end"],
                    x.get("period_kind"), x.get("form_type"), x["accession_number"],
                    x.get("accepted_at"), available, x.get("filing_date"), float(x["value"]),
                    x.get("unit"), "SEC_EDGAR_LOCAL_ARCHIVE_ACCEPTED_UNVERIFIED",
                    x.get("source_document"), x.get("raw_payload_hash") or sha256(str(x).encode()).hexdigest()))
    # Annual-only comparison exactly as the existing S15.3 materializer does.
    annual = sorted([x for x in visible if x["metric_name"] == "REVENUE"
                     and x["period_kind"] == "ANNUAL" and x.get("period_start")],
                    key=lambda item: (item["period_end"], item["available_at"]))
    dedup = {x["period_end"]: x for x in annual}
    series = [dedup[k] for k in sorted(dedup)]
    values = {}
    if len(series) >= 2:
        growth = _growth(series[-1]["value"], series[-2]["value"])
        if growth is not None:
            values["REVENUE_ANNUAL_YOY"] = growth
            _put_feature(db, ticker, sid, "REVENUE_ANNUAL_YOY", growth, as_of,
                         max(series[-1]["available_at"], series[-2]["available_at"]),
                         "SEC_EDGAR_LOCAL_ARCHIVE_ACCEPTED_UNVERIFIED",
                         series[-1].get("source_document") or "", str(series[-2:]))
            score = _score_growth(growth)
            if score is not None:
                values["REVENUE_GROWTH_LEG_RESEARCH_0_100"] = score
                _put_feature(db, ticker, sid, "REVENUE_GROWTH_LEG_RESEARCH_0_100",
                             score, as_of, series[-1]["available_at"],
                             "S15.3_EXISTING_GROWTH_KNOTS_RESEARCH_ONLY",
                             series[-1].get("source_document") or "", str(series[-2:]))
    if len(series) >= 4:
        # Four consecutive fiscal-year ends only; do not bridge an absent year.
        ends = [int(x["period_end"][:4]) for x in series[-4:]]
        if ends == list(range(ends[0], ends[0] + 4)):
            cagr = _cagr(series[-1]["value"], series[-4]["value"], 3)
            if cagr is not None:
                values["REVENUE_CAGR_3Y_RESEARCH"] = cagr
                _put_feature(db, ticker, sid, "REVENUE_CAGR_3Y_RESEARCH", cagr,
                             as_of, series[-1]["available_at"],
                             "SEC_EDGAR_LOCAL_ARCHIVE_ACCEPTED_UNVERIFIED",
                             series[-1].get("source_document") or "", str(series[-4:]))
    quarters = sorted(
        [x for x in visible if x["metric_name"] == "REVENUE"
         and x.get("period_kind") == "QUARTER" and x.get("period_start") and x.get("unit") == "USD"],
        key=lambda x: (x["period_end"], x["available_at"]),
    )
    q_dedup = {(x["period_start"], x["period_end"]): x for x in quarters}
    if q_dedup:
        latest_q = max(q_dedup.values(), key=lambda x: x["period_end"])
        previous_quarters = sorted(
            (x for x in q_dedup.values() if x["period_end"] < latest_q["period_end"]),
            key=lambda x: x["period_end"], reverse=True
        )
        if previous_quarters:
            previous = previous_quarters[0]
            interval = (date.fromisoformat(latest_q["period_end"])
                        - date.fromisoformat(previous["period_end"])).days
            if 75 <= interval <= 105:
                qoq = _growth(latest_q["value"], previous["value"])
                if qoq is not None:
                    values["REVENUE_SEQUENTIAL_QOQ"] = qoq
                    _put_feature(db, ticker, sid, "REVENUE_SEQUENTIAL_QOQ", qoq, as_of,
                                 max(latest_q["available_at"], previous["available_at"]),
                                 "SEC_EDGAR_LOCAL_ARCHIVE_ACCEPTED_UNVERIFIED",
                                 latest_q.get("source_document") or "", str((previous,latest_q)))
        prior = [
            x for x in q_dedup.values()
            if x["period_end"][:4] == str(int(latest_q["period_end"][:4]) - 1)
            and x["period_end"][4:] == latest_q["period_end"][4:]
            and x["period_start"][4:] == latest_q["period_start"][4:]
        ]
        if len(prior) == 1:
            year_earlier = prior[0]
            yoy = _growth(latest_q["value"], year_earlier["value"])
            if yoy is not None:
                values["REVENUE_LATEST_QUARTER_YOY"] = yoy
                _put_feature(db, ticker, sid, "REVENUE_LATEST_QUARTER_YOY", yoy, as_of,
                             max(latest_q["available_at"], year_earlier["available_at"]),
                             "SEC_EDGAR_LOCAL_ARCHIVE_ACCEPTED_UNVERIFIED",
                             latest_q.get("source_document") or "", str((year_earlier,latest_q)))
                leg = _score_growth(yoy)
                if leg is not None:
                    values["QUARTER_GROWTH_LEG_RESEARCH_0_100"] = leg
                    _put_feature(db, ticker, sid, "QUARTER_GROWTH_LEG_RESEARCH_0_100", leg, as_of,
                                 max(latest_q["available_at"], year_earlier["available_at"]),
                                 "S15.3_EXISTING_GROWTH_KNOTS_RESEARCH_ONLY",
                                 latest_q.get("source_document") or "", str((year_earlier,latest_q)))
        # Do not divide values from inconsistent fiscal periods or YTD/quarter mixes.
        period_matches = lambda metric: sorted(
            [x for x in visible if x["metric_name"] == metric
             and x.get("period_kind") == latest_q["period_kind"]
             and x.get("period_start") == latest_q["period_start"]
             and x["period_end"] == latest_q["period_end"] and x.get("unit") == "USD"],
            key=lambda x: x["available_at"],
        )
        for name, metric in (("GROSS_MARGIN_LATEST_QUARTER", "GROSS_PROFIT"),
                             ("NET_MARGIN_LATEST_QUARTER", "NET_INCOME"),
                             ("OPERATING_MARGIN_LATEST_QUARTER", "OPERATING_INCOME")):
            matches = period_matches(metric)
            if matches and latest_q["value"] > 0:
                row = matches[-1]
                margin = float(row["value"]) / float(latest_q["value"])
                values[name] = margin
                _put_feature(db, ticker, sid, name, margin, as_of,
                             max(latest_q["available_at"], row["available_at"]),
                             "SEC_EDGAR_LOCAL_ARCHIVE_ACCEPTED_UNVERIFIED",
                             row.get("source_document") or "", str((latest_q,row)))
        # Match year-to-date CFO and capex to the identical exact fiscal window.
        ytd = [x for x in visible if x["metric_name"] == "REVENUE"
               and x.get("period_kind") == "YTD"
               and x["period_end"] == latest_q["period_end"]]
        if ytd:
            anchor = max(ytd, key=lambda x: x["available_at"])
            def ytd_match(metric: str) -> dict | None:
                candidates = [x for x in visible if x["metric_name"] == metric
                              and x.get("period_kind") == "YTD"
                              and x.get("period_start") == anchor["period_start"]
                              and x["period_end"] == anchor["period_end"] and x.get("unit") == "USD"]
                return max(candidates, key=lambda x: x["available_at"]) if candidates else None
            cashflow, capex = ytd_match("OPERATING_CASH_FLOW"), ytd_match("CAPEX")
            if cashflow and capex:
                fcf = float(cashflow["value"]) - abs(float(capex["value"]))
                values["FCF_EXACT_YTD_RESEARCH_USD"] = fcf
                _put_feature(db, ticker, sid, "FCF_EXACT_YTD_RESEARCH_USD", fcf, as_of,
                             max(cashflow["available_at"], capex["available_at"]),
                             "SEC_EDGAR_LOCAL_ARCHIVE_ACCEPTED_UNVERIFIED",
                             cashflow.get("source_document") or "", str((cashflow,capex)))
    return values, latest_period


def model_matrix(ticker: str, sid: str, quote: float | None, when: datetime,
                 features: dict[str, float], financial_accepted_verified: bool) -> list[dict]:
    """Runs frozen engines with all unsupported PIT legs absent, never guessed."""
    result = []
    # No cached filing with null accepted_at is entitled to canonical classification.
    canonical = bool(financial_accepted_verified)
    v12_input = S153V12Input(sid, ticker, when, {}, {}, {},
                              current_price=quote, current_market_cap=None)
    v14_input = S153V14Input(sid, ticker, when, {}, {}, {},
                              current_price=quote, current_market_cap=None)
    v12 = S153V12Model().analyze(v12_input)
    v141 = S153V141Model().analyze(v14_input)
    for name, score, missing in [
        ("S1", s1(None, None, None, None), ("DNA60","Router","Historical H","N61")),
        ("S2", s2(None, None, None, None), ("DNA60","Gate6","Historical H","FalsePositiveRisk")),
        ("S3", s3(None, None, None), ("DNA60","Router","Historical H")),
        ("S14", s14({})[0], ("B_Q","S6","S7","S11","S12","S13")),
    ]:
        result.append(dict(model=name, version="S1-S14_FROZEN", score=score,
                           status="INCONCLUSIVE", coverage=0.0, missing=list(missing),
                           evidence={"financial_accepted_verified": canonical}))
    for n in range(4, 14):
        result.append(dict(model=f"S{n}", version=None, score=None, status="SPEC_MISSING",
                           coverage=0.0, missing=["Independent frozen model specification not implemented"],
                           evidence={"reference_as_component": n in (6,7,8,9,10,11,12,13)}))
    for name, model in (("S15.3 V1.2", v12), ("S15.3 V1.4.1", v141)):
        result.append(dict(model=name, version=model.model_id if hasattr(model,"model_id") else name,
                           score=model.score, status="INCONCLUSIVE" if model.score is None else "RESEARCH_ONLY",
                           coverage=0.0, missing=list(model.missing_requirements) or ["Canonical feature contract absent"],
                           evidence={"input_sources":"No forged canonical PIT inputs"}))
    for name in ("S15.3 V1.4",):
        result.append(dict(model=name, version="S15.3_V1.4_RECOVERED_2026-10-05",
                           score=None, status="INCONCLUSIVE", coverage=0.0,
                           missing=["V1.2 and V1.4 required feature contracts"],
                           evidence={"formula_unchanged":True}))
    coverage = assess_feature_coverage({})
    result.append(dict(model="S16-C", version="S16 V1.0",score=None,status="INCONCLUSIVE",
                       coverage=coverage.coverage_pct, missing=list(coverage.missing),
                       evidence={"required":coverage.required, "present":coverage.present}))
    result.append(dict(model="S16-E",version=None,score=None,status="SPEC_MISSING",
                       coverage=0.0, missing=["No approved/versioned Estimated S16 contract"],
                       evidence={"not_equivalent_to_S16_C":True}))
    result.append(dict(model="S16-EA",version="S16-EA V1.3",score=None,status="INCONCLUSIVE",
                       coverage=0.0,missing=["Verified 1m/5m reaction bars","Primary event timestamps",
                                            "Same-clock baseline"],evidence={"news_open_or_zero_pm":False}))
    return result


def run_pilot(db_path: Path, archive: Path, ticker: str, *,
              fetch=yahoo_fetch, as_of: datetime | None = None) -> dict:
    ticker = check_ticker(ticker)
    now = as_of or datetime.now(timezone.utc)
    sid, cik, source_facts = load_identity(archive, ticker)
    quote_status = "PROVIDER_ERROR"
    rows: list[dict] = []
    meta: dict = {}
    price_hash = ""
    retrieved = now
    err = None
    try:
        rows, meta, price_hash, retrieved = fetch(ticker)
        age = now.date() - date.fromisoformat(rows[-1]["trade_date"])
        quote_status = ("SUCCESS" if timedelta(0) <= age <= timedelta(days=PRICE_CUTOFF_DAYS)
                        else "STALE_DATA")
    except (httpx.HTTPError, ValueError, RuntimeError, KeyError) as exc:
        err = f"{type(exc).__name__}: {str(exc)[:350]}"
    with closing(stage_connect(db_path)) as db:
        price = rows[-1]["c"] if rows else None
        last_day = rows[-1]["trade_date"] if rows else None
        quoted_at = datetime.fromtimestamp(int(meta["regularMarketTime"]), timezone.utc).isoformat() if rows and meta.get("regularMarketTime") else (rows[-1]["timestamp"] if rows else None)
        if quoted_at and quoted_at > (now + timedelta(minutes=5)).isoformat():
            quote_status = "PROVIDER_ERROR"
            price = None
            err = "Future market timestamp rejected"
        db.execute("INSERT INTO provider_events(ticker,status,checked_at,detail) VALUES (?,?,?,?)",
                   (ticker, quote_status, now.isoformat(), err))
        if quote_status != "SUCCESS":
            prior = db.execute(
                "SELECT details_json FROM stock_runs WHERE ticker=? AND quote_status='SUCCESS'",
                (ticker,)
            ).fetchone()
            if prior is not None:
                db.commit()
                cached = json.loads(prior["details_json"])
                cached.update(quote_status=quote_status, provider_error=err,
                              reused_last_known_good_cache=True)
                return cached
        if quote_status == "SUCCESS":
            # Replacing an earlier successful research run is transactional;
            # obsolete derived values must never masquerade as current.
            db.execute("DELETE FROM research_features WHERE ticker=?", (ticker,))
        source_ref = URL + ticker + "?range=1y&interval=1d"
        for bar in rows:
            db.execute("INSERT OR REPLACE INTO research_bars VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                       (ticker,bar["trade_date"],bar["o"],bar["h"],bar["l"],bar["c"],
                        bar["adjusted"],bar["volume"],PROVIDER,source_ref,
                        retrieved.isoformat(), price_hash))
        features = (price_features(db,ticker,sid,rows,source_ref,price_hash,
                                   retrieved.isoformat()) if rows else {})
        fin_features, fin_period = finance_features(db,ticker,sid,source_facts,
                                                    now.date().isoformat())
        features.update(fin_features)
        # A current price times a *dated* earlier SEC share count is a
        # research-only estimate, NEVER an authoritative real-time market cap.
        if price is not None and rows:
            shares = db.execute(
                "SELECT value,period_end,available_at,source_ref FROM research_facts "
                "WHERE ticker=? AND metric='SHARES_OUTSTANDING' AND unit IN ('shares','Shares') "
                "ORDER BY period_end DESC,available_at DESC LIMIT 1", (ticker,)
            ).fetchone()
            if shares and shares["value"] > 0:
                mc = price * float(shares["value"])
                features["MARKET_CAP_ESTIMATE_DATED_SHARES_USD"] = mc
                _put_feature(db, ticker, sid, "MARKET_CAP_ESTIMATE_DATED_SHARES_USD",
                             mc, now.date().isoformat(), retrieved.isoformat(),
                             "YAHOO_LAST_TRADE_X_LOCAL_SEC_DATED_SHARES_RESEARCH_ONLY",
                             source_ref + " + " + str(shares["source_ref"]),
                             f"{price_hash}|{price}|{shares['period_end']}|{shares['value']}")
        audits = model_matrix(ticker,sid,price,now,features,
                              financial_accepted_verified=False)
        for audit in audits:
            db.execute("INSERT OR REPLACE INTO model_audits VALUES (?,?,?,?,?,?,?,?)",
                       (ticker,audit["model"],audit["version"],audit["score"],audit["status"],
                        audit["coverage"],json.dumps(audit["missing"],ensure_ascii=False),
                        json.dumps(audit["evidence"],ensure_ascii=False)))
        financial_status = ("CACHED_RESEARCH_ONLY_ACCEPTED_AT_UNVERIFIED"
                            if fin_period else "MISSING_DATA")
        report = dict(ticker=ticker, security_id=sid,cik=cik,as_of=now.isoformat(),
                      price=price,currency=meta.get("currency") if price else None,
                      quote_time=quoted_at,trade_date=last_day,
                      quote_status=quote_status,financial_status=financial_status,
                      financial_period=fin_period, price_provider=PROVIDER,
                      price_payload_sha256=price_hash,bars=len(rows),
                      raw_research_features=len(features),research_features=features,
                      model_audits=audits,provider_error=err,
                      research_only=True,canonical_accepted_securities=0,
                      canonical_accepted_security_dates=0,wf9="BLOCKED",
                      learning_v3="NOT_TRAINED")
        db.execute("INSERT OR REPLACE INTO stock_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (ticker,sid,cik,quote_status,financial_status,price,
                    meta.get("currency") if price else None,quoted_at,last_day,
                    PROVIDER if price else None,fin_period,now.isoformat(),
                    json.dumps(report,ensure_ascii=False)))
        db.commit()
        return report
