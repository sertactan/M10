"""Phase 28: independent real-data financial diagnostics, NOT a new canonical model.

Reads Phase27 and the user-authorized SEC-origin archive strictly read-only.
Writes only a newly marked Phase28 staging database. Normalizes ONLY components
with existing frozen source-code rubrics. Missing independent 0-100 quality
specifications remain missing; no current research value is silently canonical.
"""
from __future__ import annotations

from contextlib import closing
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import sqlite3
from typing import Any

from app.feature_materializer import _dilution_quality, _score_growth
from core.historical.s16_feature_coverage import S16_REQUIRED_FEATURES
from core.scoring.dna60 import core48, control12, dna60
from core.scoring.math import accel_score, pos_score, wa
from core.scoring.s1_s14 import s1, s2, s3, s14
from core.models.s153_v12 import S153V12Model
from core.models.s153_v14 import S153V14Model
from core.models.s153_v141 import S153V141Model

SCHEMA = "M10_PHASE28_REAL_SCORING_V1"
ENGINE_VERSION = "PHASE28_EVIDENCED_COMPONENTS_V1"
EXTRA_SEC = ("ASSETS", "EQUITY", "CURRENT_ASSETS", "CURRENT_LIABILITIES")
RISK_CONTROLS = ("DNR", "GDR", "DILR", "AQR", "PPR", "VR")
S14_LEGS = ("B_Q", "S6", "S7", "S11", "S12", "S13")


def _readonly(path: Path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Read-only source file does not exist or is a symlink")
    # No immutable=1 for a staged producer DB that might still be live elsewhere:
    # SQLite mode=ro plus query_only supports safe consistent read snapshots.
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=4)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    return db


def _stage(path: Path):
    if path.is_symlink() or path.name.casefold() == "operational.db" or "phase28" not in {
            x.lower() for x in path.resolve().parts}:
        raise ValueError("Phase28 stage must be isolated, non-symlink and not operational.db")
    if path.is_file():
        with closing(_readonly(path)) as db:
            x = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='phase28_meta'").fetchone()
            if not x or db.execute("SELECT schema FROM phase28_meta").fetchone()[0] != SCHEMA:
                raise ValueError("Refusing to overwrite unrecognized SQLite")
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript("""
    CREATE TABLE IF NOT EXISTS phase28_meta(schema TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS sourced_features(
      ticker TEXT NOT NULL, feature_key TEXT NOT NULL,
      value REAL NOT NULL, unit TEXT NOT NULL,
      as_of TEXT NOT NULL, available_at TEXT NOT NULL,
      period_end TEXT, source TEXT NOT NULL, source_ref TEXT NOT NULL,
      license_scope TEXT NOT NULL, quality_status TEXT NOT NULL,
      computation_version TEXT NOT NULL, evidence_hash TEXT NOT NULL,
      evidence_json TEXT NOT NULL, PRIMARY KEY(ticker,feature_key));
    CREATE TABLE IF NOT EXISTS scored_models(
      ticker TEXT NOT NULL, model TEXT NOT NULL, version TEXT,
      score REAL, status TEXT NOT NULL, present INTEGER NOT NULL,
      required INTEGER, coverage_pct REAL,
      missing_json TEXT NOT NULL, evidence_json TEXT NOT NULL,
      PRIMARY KEY(ticker,model));
    CREATE TABLE IF NOT EXISTS phase28_runs(
      ticker TEXT PRIMARY KEY, as_of TEXT NOT NULL, price REAL,
      price_time TEXT, currency TEXT, financial_period TEXT, full_score_count INTEGER,
      report_json TEXT NOT NULL);
    """)
    if not db.execute("SELECT 1 FROM phase28_meta").fetchone():
        db.execute("INSERT INTO phase28_meta VALUES (?)", (SCHEMA,))
    db.commit()
    return db


def _time(when: str | None):
    if not when:
        return None
    try:
        x = datetime.fromisoformat(when.replace("Z", "+00:00"))
        return x if x.tzinfo is not None else None
    except (TypeError, ValueError):
        return None


def _valid(row: dict[str, Any], as_of: datetime):
    avail = _time(row.get("available_at"))
    if avail is None or avail > as_of:
        return False
    if row.get("filing_date") and row["filing_date"] > as_of.date().isoformat():
        return False
    if row.get("period_end") and row["period_end"] > as_of.date().isoformat():
        return False
    if row.get("source") not in ("SEC_EDGAR_LOCAL_ARCHIVE_ACCEPTED_UNVERIFIED", "SEC_EDGAR"):
        return False
    if row.get("form_type") not in ("10-Q", "10-K"):
        return False
    if not row.get("source_ref") or not row.get("accession"):
        return False
    if row.get("value") is None or not math.isfinite(float(row["value"])):
        return False
    if not re.fullmatch(r"[0-9a-fA-F]{64}", str(row.get("evidence_hash") or "")):
        return False
    return True


def _one(rows: list[dict], metric: str, *, kind: str, end: str | None = None,
         start: str | None = None) -> dict | None:
    found = [x for x in rows if x["metric"] == metric and x["period_kind"] == kind
             and (end is None or x["period_end"] == end)
             and (start is None or x["period_start"] == start)]
    if not found:
        return None
    # Prefer newest fiscal period, then later available-at, then accession;
    # re-issued restated comparisons remain research, not historical PIT.
    return max(found, key=lambda x: (x["period_end"], x["available_at"], x["accession"]))


def _financial_rows(db: sqlite3.Connection, ticker: str, at: datetime):
    rows = [dict(r) for r in db.execute(
        "SELECT * FROM research_facts WHERE ticker=?", (ticker,))]
    return [x for x in rows if _valid(x, at)]


def _extra_financial_rows(archive: Path, sid: str, at: datetime):
    # Pull only a handful of missing accounting concepts from the unchanged
    # historical archive. Do not touch or duplicate a full operational DB.
    with closing(_readonly(archive)) as db:
        rows = db.execute(
            "SELECT metric_name AS metric,value,unit,period_start,period_end,period_kind,"
            "filing_date,accepted_at,available_at,source,source_document AS source_ref,"
            "accession_number AS accession,form_type,raw_payload_hash AS evidence_hash "
            "FROM fundamental_facts_source WHERE security_id=? "
            "AND metric_name IN (?,?,?,?) AND source='SEC_EDGAR'",
            (sid, *EXTRA_SEC)
        )
        return [d for r in rows if _valid(d := dict(r), at)]


def _fraction(new, previous):
    if previous is None or new is None or previous <= 0:
        return None
    return float(new) / float(previous) - 1.0


def _from_rows(rows, metric, *, kind, end=None, start=None):
    return _one(rows, metric, kind=kind, end=end, start=start)


def _latest_fiscal_year(rows, metric):
    return _one(rows, metric, kind="ANNUAL")


def _previous_annual(rows, metric, latest):
    if not latest:
        return None
    prev_year = str(int(latest["period_end"][:4]) - 1)
    candidates = [x for x in rows if x["metric"] == metric
                  and x["period_kind"] == "ANNUAL"
                  and x["period_end"][:4] == prev_year
                  and x["period_end"][4:] == latest["period_end"][4:]]
    return max(candidates, key=lambda x: x["available_at"]) if candidates else None


def _asof_run(phase27: Path, ticker: str):
    with closing(_readonly(phase27)) as db:
        base = db.execute("SELECT * FROM stock_runs WHERE ticker=?", (ticker,)).fetchone()
        if base is None:
            raise ValueError("Phase27 cached ticker is not available")
        data = dict(base)
        as_of = _time(data["checked_at"])
        if as_of is None:
            raise ValueError("Source checked_at not offset-aware")
        facts = _financial_rows(db, ticker, as_of)
        evidence = [dict(row) for row in db.execute(
            "SELECT feature_key,value,as_of,available_at,source,source_ref,"
            "evidence_hash,quality_status FROM research_features WHERE ticker=?", (ticker,))]
        return data, facts, evidence, as_of


def _save_feature(features: dict, key: str, val: float | None, unit: str,
                  inputs: list[dict], *, period: str | None, as_of: datetime,
                  origin="SEC_ARCHIVE_RESEARCH") -> None:
    if val is None or not math.isfinite(float(val)) or not inputs:
        return
    for x in inputs:
        if not x or _time(x.get("available_at")) is None or _time(x["available_at"]) > as_of:
            raise ValueError(f"Refusing inadmissible evidence for {key}")
    refs = [{"metric": x["metric"], "period": x["period_end"],
             "kind": x["period_kind"], "accession": x["accession"],
             "source_ref": x["source_ref"], "available_at": x["available_at"],
             "accepted_at": x.get("accepted_at"), "hash": x["evidence_hash"]}
            for x in inputs]
    payload = json.dumps({"feature": key, "inputs": refs, "value": val,
                          "computation": ENGINE_VERSION}, sort_keys=True, default=str)
    features[key] = {
        "value": float(val), "unit": unit, "as_of": as_of.isoformat(),
        "available_at": max(x["available_at"] for x in inputs),
        "period_end": period, "source": origin,
        "source_ref": " | ".join(dict.fromkeys(x["source_ref"] for x in inputs)),
        "license_scope": "LOCAL_PRIVATE_RESEARCH_ONLY",
        "quality_status": "RESEARCH_ONLY_ACCEPTED_AT_UNVERIFIED",
        "computation_version": ENGINE_VERSION,
        "evidence_hash": sha256(payload.encode()).hexdigest(),
        "evidence": refs
    }


def financial_features(facts: list[dict], at: datetime):
    """Pair exact fiscal windows; apply only existing frozen component rubrics."""
    raw: dict = {}
    annual = _latest_fiscal_year(facts, "REVENUE")
    prev_rev = _previous_annual(facts, "REVENUE", annual)
    _save_feature(raw, "REVENUE_ANNUAL_YOY", _fraction(
        annual["value"] if annual else None, prev_rev["value"] if prev_rev else None),
        "fraction", [annual,prev_rev] if annual and prev_rev else [], period=annual["period_end"] if annual else None, as_of=at)
    if "REVENUE_ANNUAL_YOY" in raw:
        _save_feature(raw,"D01_REVENUE_GROWTH_1Y_LEG",
                      _score_growth(raw["REVENUE_ANNUAL_YOY"]["value"]), "0_100",
                      [annual,prev_rev],period=annual["period_end"],as_of=at,
                      origin="FROZEN_S15_3_GROWTH_KNOTS_RESEARCH_COMPONENT")
    def annual_growth(metric: str, feature: str):
        curr=_latest_fiscal_year(facts,metric)
        prev=_previous_annual(facts,metric,curr)
        if curr and prev:
            _save_feature(raw,feature,_fraction(curr["value"],prev["value"]),
                          "fraction",[curr,prev],period=curr["period_end"],as_of=at)
    annual_growth("GROSS_PROFIT","GROSS_PROFIT_ANNUAL_YOY")
    annual_growth("OPERATING_INCOME","OPERATING_INCOME_ANNUAL_YOY")
    annual_growth("DILUTED_EPS","DILUTED_EPS_ANNUAL_YOY")
    if "DILUTED_EPS_ANNUAL_YOY" in raw:
        curr=_latest_fiscal_year(facts,"DILUTED_EPS")
        prev=_previous_annual(facts,"DILUTED_EPS",curr)
        _save_feature(raw,"D02_EPS_GROWTH_1Y_LEG",
                      _score_growth(raw["DILUTED_EPS_ANNUAL_YOY"]["value"]),
                      "0_100",[curr,prev],period=curr["period_end"],as_of=at,
                      origin="FROZEN_S15_3_GROWTH_KNOTS_RESEARCH_COMPONENT")
    if annual and prev_rev:
        older=_previous_annual(facts,"REVENUE",prev_rev)
        if older and "REVENUE_ANNUAL_YOY" in raw:
            previous_growth=_fraction(prev_rev["value"],older["value"])
            if previous_growth is not None:
                acceleration=accel_score(
                    (raw["REVENUE_ANNUAL_YOY"]["value"]-previous_growth)*100.0,20.0)
                _save_feature(raw,"D03_REVENUE_ACCELERATION_LEG",acceleration,"0_100",
                              [annual,prev_rev,older],period=annual["period_end"],as_of=at,
                              origin="FROZEN_S15_3_ACCELERATION_RUBRIC_RESEARCH_COMPONENT")
    q_revenue = _one(facts,"REVENUE",kind="QUARTER")
    period = q_revenue["period_end"] if q_revenue else None
    q_start = q_revenue["period_start"] if q_revenue else None
    if q_revenue:
        last_end = date.fromisoformat(period)
        quarters = sorted(
            [x for x in facts if x["metric"]=="REVENUE" and x["period_kind"]=="QUARTER"
             and x["period_end"] < period],key=lambda x:x["period_end"],reverse=True)
        previous = quarters[0] if quarters else None
        if previous and 75 <= (last_end-date.fromisoformat(previous["period_end"])).days <=105:
            _save_feature(raw,"REVENUE_QOQ",_fraction(q_revenue["value"],previous["value"]),
                          "fraction",[q_revenue,previous],period=period,as_of=at)
        yoy_prior = [
            x for x in quarters if x["period_end"][4:]==period[4:]
            and int(x["period_end"][:4])==int(period[:4])-1 and
            x["period_start"][4:]==q_start[4:]]
        if yoy_prior:
            yoy = max(yoy_prior,key=lambda x:x["available_at"])
            _save_feature(raw,"REVENUE_QUARTER_YOY",_fraction(q_revenue["value"],yoy["value"]),
                          "fraction",[q_revenue,yoy],period=period,as_of=at)

        for key,metric in (("GROSS_MARGIN_Q","GROSS_PROFIT"),
                           ("OPERATING_MARGIN_Q","OPERATING_INCOME"),
                           ("NET_MARGIN_Q","NET_INCOME")):
            x=_one(facts,metric,kind="QUARTER",end=period,start=q_start)
            if x and q_revenue["value"]>0:
                _save_feature(raw,key,x["value"]/q_revenue["value"],
                              "fraction",[q_revenue,x],period=period,as_of=at)

        for key,metric in (("GROSS_PROFIT_YOY_Q","GROSS_PROFIT"),
                           ("OPERATING_INCOME_YOY_Q","OPERATING_INCOME"),
                           ("NET_INCOME_YOY_Q","NET_INCOME"),
                           ("DILUTED_EPS_YOY_Q","DILUTED_EPS")):
            q=_one(facts,metric,kind="QUARTER",end=period,start=q_start)
            if q:
                prior=[x for x in facts if x["metric"]==metric and x["period_kind"]=="QUARTER"
                       and x["period_end"][4:]==period[4:] and
                       int(x["period_end"][:4])==int(period[:4])-1 and
                       x["period_start"] and x["period_start"][4:]==q_start[4:]]
                if prior:
                    p=max(prior,key=lambda x:x["available_at"])
                    _save_feature(raw,key,_fraction(q["value"],p["value"]),"fraction",
                                  [q,p],period=period,as_of=at)
    annual_cfo=_latest_fiscal_year(facts,"OPERATING_CASH_FLOW")
    annual_capex=_one(facts,"CAPEX",kind="ANNUAL",
                      end=annual_cfo["period_end"] if annual_cfo else None,
                      start=annual_cfo["period_start"] if annual_cfo else None)
    if annual_cfo and annual_capex and annual_cfo["period_end"]==annual_capex["period_end"]:
        _save_feature(raw,"FCF_ANNUAL_USD",annual_cfo["value"]-abs(annual_capex["value"]),
                      "USD",[annual_cfo,annual_capex],period=annual_cfo["period_end"],as_of=at)
    ytd_revenue=_one(facts,"REVENUE",kind="YTD")
    if ytd_revenue:
        s,end=ytd_revenue["period_start"],ytd_revenue["period_end"]
        cfo=_one(facts,"OPERATING_CASH_FLOW",kind="YTD",start=s,end=end)
        capex=_one(facts,"CAPEX",kind="YTD",start=s,end=end)
        if cfo and capex:
            fcf=cfo["value"]-abs(capex["value"])
            _save_feature(raw,"FCF_YTD_USD",fcf,"USD",[cfo,capex],period=end,as_of=at)
            if ytd_revenue["value"]>0:
                _save_feature(raw,"FCF_MARGIN_YTD",fcf/ytd_revenue["value"],
                              "fraction",[cfo,capex,ytd_revenue],period=end,as_of=at)
        ni=_one(facts,"NET_INCOME",kind="YTD",start=s,end=end)
        if cfo and ni and ni["value"]>0:
            _save_feature(raw,"CASH_CONVERSION_YTD",cfo["value"]/ni["value"],
                          "ratio",[cfo,ni],period=end,as_of=at)
        sbc=_one(facts,"SBC",kind="YTD",start=s,end=end)
        if sbc and ytd_revenue["value"]>0:
            _save_feature(raw,"SBC_REVENUE_RATIO_YTD",sbc["value"]/ytd_revenue["value"],
                          "fraction",[sbc,ytd_revenue],period=end,as_of=at)
        for key,metric in (("GROSS_MARGIN_YTD","GROSS_PROFIT"),
                           ("OPERATING_MARGIN_YTD","OPERATING_INCOME"),
                           ("NET_MARGIN_YTD","NET_INCOME")):
            x=_one(facts,metric,kind="YTD",start=s,end=end)
            if x and ytd_revenue["value"]>0:
                _save_feature(raw,key,x["value"]/ytd_revenue["value"],
                              "fraction",[x,ytd_revenue],period=end,as_of=at)
    # Exact TTM roll-forward: FY(prev fiscal year) + same fiscal YTD(current)
    # - same fiscal YTD(prev year). Never use nonmatching periods or pretend
    # existing YTD + trailing annual is the current TTM.
    if ytd_revenue:
        start,end=ytd_revenue["period_start"],ytd_revenue["period_end"]
        if start and end and int(start[:4]) == int(end[:4]):
            prior_end=str(int(end[:4])-1)+end[4:]
            prior_start=str(int(start[:4])-1)+start[4:]
            for metric,label in (
                ("REVENUE","TTM_REVENUE_USD"),("NET_INCOME","TTM_NET_INCOME_USD"),
                ("OPERATING_CASH_FLOW","TTM_OPERATING_CASH_FLOW_USD"),
                ("CAPEX","TTM_CAPEX_USD")):
                curr=_one(facts,metric,kind="YTD",end=end,start=start)
                prev=_one(facts,metric,kind="YTD",end=prior_end,start=prior_start)
                annual_candidates = [x for x in facts if x["metric"] == metric
                                     and x["period_kind"] == "ANNUAL"
                                     and prior_end < x["period_end"] < end
                                     and x.get("period_start") and
                                     x["period_start"] <= prior_start]
                fiscal=max(annual_candidates,key=lambda x:(x["period_end"],x["available_at"])) if annual_candidates else None
                if curr and prev and fiscal:
                    value=float(fiscal["value"])+float(curr["value"])-float(prev["value"])
                    _save_feature(raw,label,value,"USD",[fiscal,curr,prev],
                                  period=end,as_of=at)
            if ("TTM_OPERATING_CASH_FLOW_USD" in raw and "TTM_CAPEX_USD" in raw):
                cfo=raw["TTM_OPERATING_CASH_FLOW_USD"]
                capex=raw["TTM_CAPEX_USD"]
                _save_feature(raw,"TTM_FCF_USD",cfo["value"]-abs(capex["value"]),
                              "USD", [dict(metric=z["metric"],period_end=z["period"],
                                          period_kind=z["kind"],accession=z["accession"],
                                          source_ref=z["source_ref"],available_at=z["available_at"],
                                          accepted_at=z["accepted_at"],evidence_hash=z["hash"])
                                      for z in cfo["evidence"]+capex["evidence"]],
                              period=end,as_of=at)
    # Exact instant/period arithmetic only; no fabricated zero debt/working capital.
    cash=_one(facts,"CASH",kind="INSTANT")
    equity=_one(facts,"EQUITY",kind="INSTANT",
                end=cash["period_end"] if cash else None) if cash else None
    if cash:
        _save_feature(raw,"CASH_LATEST_USD",cash["value"],"USD",[cash],
                      period=cash["period_end"],as_of=at)
    current_assets=_one(facts,"CURRENT_ASSETS",kind="INSTANT",end=cash["period_end"]) if cash else None
    current_liab=_one(facts,"CURRENT_LIABILITIES",kind="INSTANT",end=cash["period_end"]) if cash else None
    if current_assets and current_liab:
        _save_feature(raw,"WORKING_CAPITAL_USD",current_assets["value"]-current_liab["value"],
                      "USD",[current_assets,current_liab],period=current_assets["period_end"],as_of=at)
        if current_liab["value"]>0:
            _save_feature(raw,"CURRENT_RATIO",current_assets["value"]/current_liab["value"],
                          "ratio",[current_assets,current_liab],
                          period=current_assets["period_end"],as_of=at)
    if ytd_revenue and equity and cash and ytd_revenue["period_end"]==equity["period_end"]:
        # Ending-equity proxy is not textbook ROE (which uses average equity).
        ni=_one(facts,"NET_INCOME",kind="YTD",start=ytd_revenue["period_start"],
                end=ytd_revenue["period_end"])
        if ni and equity["value"]>0:
            _save_feature(raw,"NET_INCOME_YTD_TO_END_EQUITY_PROXY",ni["value"]/equity["value"],
                          "fraction",[ni,equity],period=equity["period_end"],as_of=at)
        begin=_one(facts,"EQUITY",kind="INSTANT",
                   end=str(int(equity["period_end"][:4])-1)+"-12-31")
        if ni and begin and (equity["value"]+begin["value"])>0:
            _save_feature(raw,"ROE_YTD_AVG_EQUITY_UNANNUALIZED",
                          ni["value"]/((equity["value"]+begin["value"])/2),
                          "fraction",[ni,equity,begin],period=equity["period_end"],as_of=at)
    shares=_one(facts,"SHARES_OUTSTANDING",kind="INSTANT")
    if shares:
        _save_feature(raw,"SHARES_OUTSTANDING_DATED",shares["value"],"shares",
                      [shares],period=shares["period_end"],as_of=at)
        previous_candidates = [x for x in facts if x["metric"]=="SHARES_OUTSTANDING"
              and x["period_kind"]=="INSTANT" and x["period_end"] < shares["period_end"]
              and 300 <= (date.fromisoformat(shares["period_end"])-
                          date.fromisoformat(x["period_end"])).days <= 430]
        if previous_candidates:
            p=min(previous_candidates,
                  key=lambda x: abs((date.fromisoformat(shares["period_end"]) -
                                     date.fromisoformat(x["period_end"])).days-365))
            delta=_fraction(shares["value"],p["value"])
            _save_feature(raw,"SHARES_DILUTION_1Y_APPROX",delta,"fraction",
                          [shares,p],period=shares["period_end"],as_of=at)
            # Frozen S15.3 control normalization, only an individual leg.
            _save_feature(raw,"F54_DIL_RESEARCH_LEG",
                          _dilution_quality(delta),"0_100",
                          [shares,p],period=shares["period_end"],as_of=at,
                          origin="FROZEN_DILUTION_RUBRIC_RESEARCH_COMPONENT")
    return raw


def _diag(model: str, required: tuple[str, ...] | None, available: set[str],
          version: str, note: str = ""):
    if required is None:
        return {"model":model, "version":version,"score":None, "status":"SPEC_MISSING",
                "present":0,"required":None,"coverage_pct":None,
                "missing":["Independent frozen scoring specification not found"],
                "evidence":{"note":note}}
    miss=[x for x in required if x not in available]
    return {"model":model,"version":version,"score":None,"status":"INCONCLUSIVE",
            "present":len(required)-len(miss),"required":len(required),
            "coverage_pct":100*(len(required)-len(miss))/len(required) if required else 0,
            "missing":miss,"evidence":{"note":note}}


def coverage_audit(ticker: str, price: float | None, at: datetime, features: dict):
    # Current research != accepted canonical 0..100 model feature.
    # The present *raw* accounting features do not satisfy normalized S1/S2/S3/S14 inputs.
    aud=[]
    aud.append(_diag("S1",("DNA60","ROUTER","HISTORICAL_H","N61"),set(),
                     "S1_FROZEN","DNA60 cannot be treated as complete with only 1–3 discovery legs."))
    aud.append(_diag("S2",("DNA60","GATE6","HISTORICAL_H","FALSE_POSITIVE_RISK"),set(),
                     "S2_FROZEN"))
    aud.append(_diag("S3",("DNA60","ROUTER","HISTORICAL_H"),set(),"S3_FROZEN"))
    aud.append(_diag("S14",S14_LEGS,set(),"S14_FROZEN",
                     "S6/S7/S11/S12/S13 component fields lack independently frozen 0..100 scoring rubrics."))
    for n in range(4,14):
        aud.append(_diag(f"S{n}",None,set(),"SPEC_MISSING",
                         "May be a S14 or company-quality component, not independent certified model."))
    for x in ("S15.3 V1.2","S15.3 V1.4","S15.3 V1.4.1"):
        # Unlike S14/S16 the full concrete gate-input count varies with
        # primary route and missing optional legs. Do not falsely publish 6/6
        # as an exhaustive "feature count"; these are six *gate families*.
        gates=("COMPLETE_CORE48","COMPLETE_CONTROL12","ROUTE_EVIDENCE",
               "SUPPORTED_MARKET_CAP_SCENARIO","HISTORICAL_SIMILARITY",
               "MAGNITUDE_AND_TIME_GATES")
        engine={"S15.3 V1.2":S153V12Model,
                "S15.3 V1.4":S153V14Model,
                "S15.3 V1.4.1":S153V141Model}[x]
        aud.append({
            "model":x, "version":engine.canonical_formula_version,
            "score":None, "status":"INCONCLUSIVE",
            "present":0,"required":None,"coverage_pct":None,
            "missing":list(gates),
            "evidence":{"gate_families_required":len(gates),
                        "exact_route_specific_feature_total":"UNVERIFIED",
                        "note":"Six gate families are not an exhaustive feature denominator."}
        })
    aud.append(_diag("S16-C",tuple(S16_REQUIRED_FEATURES),set(),"S16 V1.0",
                     "22 required normalized PIT features, no direct independent accepted feature evidence."))
    aud.append(_diag("S16-E",None,set(),"SPEC_MISSING",
                     "No user-approved independent estimated model specification; S16-EA is not S16-E."))
    aud.append(_diag("S16-EA",("VERIFIED_1MIN","VERIFIED_5MIN","NEWS_EVENT_UTC",
                               "BASELINE_SAME_CLOCK"),set(),"S16-EA V1.3"))
    # These are diagnostics, not the S1–S16 final score. Frozen individual
    # growth and control functions are useful, even without all 48+12 legs.
    raw={k:x["value"] for k,x in features.items()}
    norm={}
    if "D01_REVENUE_GROWTH_1Y_LEG" in raw:
        norm[1]=raw["D01_REVENUE_GROWTH_1Y_LEG"]
    if "D02_EPS_GROWTH_1Y_LEG" in raw:
        norm[2]=raw["D02_EPS_GROWTH_1Y_LEG"]
    if "D03_REVENUE_ACCELERATION_LEG" in raw:
        norm[3]=raw["D03_REVENUE_ACCELERATION_LEG"]
    disc, fam=core48(norm)
    controls={}
    if "F54_DIL_RESEARCH_LEG" in raw:
        controls["DIL"]=raw["F54_DIL_RESEARCH_LEG"]
    c12=control12(controls)
    diagnostic = {
       "frozen_partial_discovery":disc,
       "frozen_partial_control":c12,
       "frozen_partial_dna":dna60(disc,c12),
       "discovery_inputs_present":len(norm),"discovery_inputs_total":48,
       "control_inputs_present":len(controls),"control_inputs_total":12,
       "component_scope":"INCOMPLETE_RESEARCH_DIAGNOSTIC_NOT_A_MODEL_SCORE",
    }
    # Verify missing canonical inputs never accidentally generate full score.
    assert s1(None,None,None,None) is None and s2(None,None,None,None) is None
    assert s3(None,None,None) is None and s14({})[0] is None
    return aud, diagnostic


def run_phase28(phase27_db: Path, phase28_db: Path, archive: Path, *,
                ticker: str = "INOD") -> dict:
    if ticker != "INOD":
        raise ValueError("INOD-first acceptance gate; no widening before full score")
    data, facts, source_features, at = _asof_run(phase27_db,ticker)
    if data["quote_status"] != "SUCCESS" or data["quote_price"] is None:
        raise ValueError("Phase27 research price not verified; cannot promote")
    sid=data["security_id"]
    extra=_extra_financial_rows(archive,sid,at)
    features=financial_features(facts+extra,at)
    # Derive research-only market cap from source-dated shares and actual last
    # trade, without pretending to own current float or officially live shares.
    share=features.get("SHARES_OUTSTANDING_DATED")
    if share and data["quote_price"]>0:
        f=features["MARKET_CAP_RESEARCH_DATED_SHARES_USD"]={
            "value":float(data["quote_price"])*share["value"],"unit":"USD",
            "as_of":at.isoformat(),"available_at":at.isoformat(),
            "period_end":share["period_end"],"source":"YAHOO_PHASE27_X_SEC_ARCHIVE",
            "source_ref":"PHASE27_RESEARCH_PRICE_AND_DATED_SHARES",
            "license_scope":"LOCAL_PRIVATE_RESEARCH_ONLY",
            "quality_status":"RESEARCH_ONLY_ACCEPTED_AT_UNVERIFIED",
            "computation_version":ENGINE_VERSION,
            "evidence_hash":sha256(f"{data['quote_price']}:{share['evidence_hash']}".encode()).hexdigest(),
            "evidence":[{"source":"phase27_price","quote_time":data["quote_time"],
                         "currency":data["quote_currency"]},*share["evidence"]]
        }
        # P/S requires a common actual revenue period and is explicitly not P/E.
        rev_annual=_latest_fiscal_year(facts,"REVENUE")
        if rev_annual and rev_annual["value"]>0:
            features["PS_LAST_ANNUAL_RESEARCH"]={
                **f, "value":f["value"]/rev_annual["value"],"unit":"ratio",
                "period_end":rev_annual["period_end"],
                "source":"YAHOO_PRICE_SEC_DATED_SHARES_ANNUAL_REVENUE",
                "evidence_hash":sha256(f"{f['evidence_hash']}:{rev_annual['evidence_hash']}".encode()).hexdigest(),
                "evidence":[*f["evidence"],{"accession":rev_annual["accession"],
                            "period_end":rev_annual["period_end"],"metric":"REVENUE",
                            "hash":rev_annual["evidence_hash"],"available_at":rev_annual["available_at"]}],
            }
        def add_research_valuation(key, amount, denominator_source, denominator_feature):
            if denominator_source is None or denominator_source["value"]<=0:
                return
            denominator=float(denominator_source["value"])
            feat=dict(f, value=float(amount)/float(denominator),unit="ratio",
                      period_end=denominator_source["period_end"],
                      source="CURRENT_LAST_PRICE_X_DATED_SHARES_DIVIDED_BY_SEC_CACHED",
                      evidence_hash=sha256(f"{f['evidence_hash']}:{denominator_feature}:{denominator}".encode()).hexdigest(),
                      evidence=[*f["evidence"],{"denominator":denominator_feature,
                            "amount":denominator,
                            "evidence_hash":denominator_source["evidence_hash"],
                            "source":"SEC_LOCAL_ARCHIVE_RESEARCH_ONLY"},
                            *denominator_source["evidence"]])
            features[key]=feat
        ttm_rev=features.get("TTM_REVENUE_USD")
        if ttm_rev:
            add_research_valuation("PS_TTM_RESEARCH",f["value"],ttm_rev,"TTM_REVENUE_USD")
        ttm_ni=features.get("TTM_NET_INCOME_USD")
        if ttm_ni:
            add_research_valuation("PE_TTM_RESEARCH",f["value"],ttm_ni,"TTM_NET_INCOME_USD")
        ttm_fcf=features.get("TTM_FCF_USD")
        if ttm_fcf and f["value"]>0:
            feat=dict(f,value=ttm_fcf["value"]/f["value"],unit="fraction",
                      period_end=ttm_fcf["period_end"],
                      source="SEC_CACHED_TTM_FCF_DIVIDED_BY_PRICE_X_DATED_SHARES",
                      evidence_hash=sha256(f"{f['evidence_hash']}:{ttm_fcf['evidence_hash']}".encode()).hexdigest(),
                      evidence=[*f["evidence"],*ttm_fcf["evidence"]])
            features["FCF_YIELD_TTM_RESEARCH"]=feat
    audits,diag=coverage_audit(ticker,data["quote_price"],at,features)
    report={
        "ticker":ticker, "as_of":at.isoformat(),
        "price":data["quote_price"],"price_time":data["quote_time"],
        "currency":data["quote_currency"],"financial_period":data["financial_period"],
        "source_stage":"PHASE27_READ_ONLY", "accepted_at_verified":False,
        "stage27_features_count":len(source_features),
        "phase28_feature_count":len(features), "features":features,
        "models":audits,"diagnostics":diag,
        "full_model_score_count":sum(x["score"] is not None for x in audits),
        "historical_canonical_securities":0,"historical_canonical_dates":0,
        "WF9":"BLOCKED","LearningV3":"NOT_TRAINED",
    }
    with closing(_stage(phase28_db)) as db:
        # Atomic refresh of this ONE ticker in the Phase28 DB, no effect on 27.
        db.execute("BEGIN")
        db.execute("DELETE FROM sourced_features WHERE ticker=?", (ticker,))
        for name, f in features.items():
            db.execute("INSERT INTO sourced_features VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (ticker,name,f["value"],f["unit"],f["as_of"],f["available_at"],
                 f["period_end"],f["source"],f["source_ref"],f["license_scope"],
                 f["quality_status"],f["computation_version"],f["evidence_hash"],
                 json.dumps(f["evidence"],sort_keys=True)))
        for model in audits:
            db.execute("INSERT OR REPLACE INTO scored_models VALUES (?,?,?,?,?,?,?,?,?,?)",
                (ticker,model["model"],model["version"],model["score"],model["status"],
                 model["present"],model["required"],model["coverage_pct"],
                 json.dumps(model["missing"]),json.dumps(model["evidence"])))
        db.execute("INSERT OR REPLACE INTO phase28_runs VALUES (?,?,?,?,?,?,?,?)",
            (ticker,at.isoformat(),data["quote_price"],data["quote_time"],
             data["quote_currency"],data["financial_period"],
             report["full_model_score_count"],json.dumps(report,sort_keys=True)))
        db.commit()
    return report
