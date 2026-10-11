"""Source-bound FY2025 Piotroski S9 Research calculations and offline replay."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, localcontext
from hashlib import sha256
from pathlib import Path
import json
import math
import zipfile

from app.task9_jones_cohort import SECCache

MODEL_SOURCE_SHA256 = "53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794"
SCORE_VERSION = "PIOTROSKI_F_SCORE_9_SIGNAL_FROZEN_V1"
PAPER_URL = "https://www.ivey.uwo.ca/media/3775523/value_investing_the_use_of_historical_financial_statement_information.pdf"

# Companyfacts taxonomy tags and accessions are issuer-specific and pinned.
TARGETS = {
    "TMDX": {
        "cik": "0001756262", "end": "2025-12-31", "prior_end": "2024-12-31",
        "begin_end": "2023-12-31", "current_accession": "0001193125-26-067032",
        "prior_accession": "0000950170-25-029104", "revenue_tag": "Revenues",
        "companyfacts_sha256": "8096066125323b72557bd9d582cfab4bcdec59b814cee4e082ede5ade1a800ab",
        "cogs_tag": "CostOfRevenue",
        "debt_2025": [("LongTermDebtCurrent", 1), ("ConvertibleDebtNoncurrent", 1),
                       ("OtherLongTermDebtNoncurrent", 1)],
        "debt_2024": [("ConvertibleDebtNoncurrent", 1),
                       ("OtherLongTermDebtNoncurrent", 1),
                       {"tag": "LongTermDebtCurrent", "weight": 1,
                        "explicit_zero_when_absent": True,
                        "statement_label": "Current portion of long-term debt"}],
        "issue_tags": ["ProceedsFromIssuanceOfCommonStock",
                       "StockIssuedDuringPeriodValueNewIssues",
                       "ProceedsFromStockOptionsExercised"],
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1756262/000119312526067032/tmdx-20251231.htm",
        "issuer_title": "transmedics group, inc.",
        "header_sha256": "04ab2e9d8b53891d57d629585a5e94aa6a6c1b63f301280733f339af59ee8c2c",
    },
    "PENG": {
        "cik": "0001616533", "end": "2025-08-29", "prior_end": "2024-08-30",
        "begin_end": "2023-08-25", "current_accession": "0001616533-25-000061",
        "prior_accession": "0001628280-24-043646",
        "companyfacts_sha256": "7f49ae1db8700690e6ea142ddafad7a524e5ab04b5a49e16e5be72bd82ebaca6",
        "revenue_tag": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "cogs_tag": "CostOfGoodsAndServicesSold",
        "debt_2025": [("LongTermDebt", 1)], "debt_2024": [("LongTermDebt", 1)],
        "issue_tags": ["StockIssuedDuringPeriodValueNewIssues",
                       "ProceedsFromIssuanceOfCommonStock"],
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1616533/000161653325000061/peng-20250829.htm",
        "issuer_title": "penguin solutions, inc.",
        "header_sha256": "462a4a7d6accfa1009a80ca68c29a783abfba77337420648ce0ddf33861a631d",
    },
    "ETON": {
        "cik": "0001710340", "end": "2025-12-31", "prior_end": "2024-12-31",
        "begin_end": "2023-12-31", "current_accession": "0001437749-26-009059",
        "prior_accession": "0001437749-25-008136",
        "companyfacts_sha256": "f7f154bb5484ead9734e7792fe9226c296b72a5adb5779a7e452499ba4d8b45b",
        "revenue_tag": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "cogs_tag": "CostOfGoodsAndServicesSold",
        "debt_2025": [("LongTermDebtCurrent", 1), ("LongTermDebtNoncurrent", 1)],
        "debt_2024": [("LongTermDebtCurrent", 1), ("LongTermDebtNoncurrent", 1)],
        "issue_tags": ["ProceedsFromStockOptionsExercised"],
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1710340/000143774926009059/eton20251231_10k.htm",
        "issuer_title": "eton pharmaceuticals, inc.",
        "header_sha256": "e569ca6d73cebbeeadca604eb4adc95ef45cb059b344c649ef9cdae4af61af0b",
    },
}


def _digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _entry(facts: dict, tag: str, accession: str, end: str, *, flow: bool):
    concept = facts.get(tag)
    if not isinstance(concept, dict):
        return None
    matches = []
    for unit, rows in (concept.get("units") or {}).items():
        for row in rows:
            if (row.get("accn") != accession or row.get("end") != end
                    or row.get("form") != "10-K"):
                continue
            if flow:
                start = row.get("start")
                if not start:
                    continue
                days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
                if not 330 <= days <= 400:
                    continue
            elif row.get("start"):
                continue
            matches.append((unit, row))
    if len(matches) != 1:
        return None
    unit, row = matches[0]
    return {"tag": tag, "unit": unit, "value": str(row["val"]),
            "start": row.get("start"), "end": end, "accession": accession,
            "filed": row.get("filed"), "form": row.get("form"),
            "fact_sha256": _digest(json.dumps(row, sort_keys=True,
                                               separators=(",", ":")).encode())}


def _required(facts, tag, accession, end, *, flow):
    row = _entry(facts, tag, accession, end, flow=flow)
    if row is None:
        raise ValueError(f"EXACT_SEC_FACT_MISSING_OR_AMBIGUOUS:{tag}:{end}")
    return row


def _debt(facts, components, accession, end, filing_html):
    rows, weights = [], []
    rendered = " ".join(__import__("html").unescape(
        __import__("re").sub(r"<[^>]*>", " ", filing_html.decode("utf-8", errors="replace"))).split())
    for component in components:
        if isinstance(component, dict):
            tag, weight = component["tag"], component["weight"]
        else:
            tag, weight = component
        row = _entry(facts, tag, accession, end, flow=False)
        if row is None and isinstance(component, dict) and component.get("explicit_zero_when_absent"):
            label = component["statement_label"]
            import re
            explicit = re.search(re.escape(label)+r".{0,220}?(?:—|&mdash;|&#8212;|&#x2014;)",
                                 rendered, re.I)
            if not explicit:
                raise ValueError(f"EXPLICIT_FILED_ZERO_NOT_PROVEN:{tag}:{end}")
            row = {"tag": tag, "unit": "USD", "value": "0", "start": None,
                   "end": end, "accession": accession, "filed": None,
                   "form": "10-K", "fact_sha256": None,
                   "filed_zero_statement_label": label}
        if row is None:
            raise ValueError(f"EXACT_SEC_FACT_MISSING_OR_AMBIGUOUS:{tag}:{end}")
        rows.append(row)
        weights.append(weight)
    total = sum((Decimal(row["value"]) * Decimal(str(weight))
                 for row, weight in zip(rows, weights)), Decimal(0))
    return {"value": str(total), "components": rows}


def _issue(facts, tags, accession, end, start):
    candidates = []
    for tag in tags:
        row = _entry(facts, tag, accession, end, flow=True)
        if row and row["start"] == start:
            candidates.append(row)
    positive = [row for row in candidates if Decimal(row["value"]) > 0]
    if positive:
        return {"issued": True, "basis": positive,
                "assessment": "POSITIVE_FILED_COMMON_EQUITY_ISSUANCE"}
    # Absence or a set of unreported tags cannot establish that no equity was issued.
    raise ValueError(f"COMMON_EQUITY_ISSUANCE_NOT_DETERMINED:{end}")


def _verify_filing_metadata(cache: SECCache, runtime: Path, cfg: dict,
                            accession: str, expected_end: str):
    cik = cfg["cik"]
    raw, source = cache.load(f"https://data.sec.gov/submissions/CIK{cik}.json",
                             limit=2_500_000)
    if raw is None:
        raise ValueError("SEC_SUBMISSIONS_CACHE_REQUIRED")
    payload = json.loads(raw)
    recent = payload["filings"]["recent"]
    fields = ("accessionNumber", "form", "reportDate", "filingDate",
              "acceptanceDateTime")
    if len({len(recent.get(field, [])) for field in fields}) != 1:
        raise ValueError("SEC_SUBMISSIONS_ARRAYS_MISALIGNED")
    found = []
    for values in zip(*(recent[field] for field in fields)):
        acc, form, report_date, filing_date, accepted = values
        if acc == accession:
            found.append({"accession": acc, "form": form, "report_date": report_date,
                          "filing_date": filing_date, "accepted_at": accepted})
    if len(found) != 1 or found[0]["form"] != "10-K" or found[0]["report_date"] != expected_end:
        raise ValueError("SEC_FILING_IDENTITY_OR_PERIOD_MISMATCH")
    return found[0], source


def _verify_current_header(cache: SECCache, cfg: dict):
    cik = cfg["cik"]
    accession = cfg["current_accession"]
    url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
           f"{accession.replace('-', '')}/{accession}.txt")
    raw, source = cache.load(url, limit=250_000, partial=True)
    if raw is None or source.get("sha256") != cfg["header_sha256"]:
        raise ValueError("ORIGINAL_SEC_10K_HEADER_FINGERPRINT_MISMATCH")
    upper = raw.upper()
    if (accession.encode() not in raw or cik.lstrip("0").encode() not in upper
            or cfg["end"].replace("-", "").encode() not in upper):
        raise ValueError("SEC_10K_HEADER_IDENTITY_PERIOD_MISMATCH")
    return {"url": url, "sha256": _digest(raw),
            "source_receipt": source}


def score_companyfacts(ticker: str, raw: bytes, *, current_meta: dict,
                       prior_meta: dict, filing_html: bytes | None = None) -> dict:
    """Calculate the frozen nine signals from exact annual Companyfacts rows."""
    if ticker not in TARGETS:
        raise ValueError("UNSUPPORTED_S9_TICKER")
    cfg = TARGETS[ticker]
    payload = json.loads(raw)
    if str(payload.get("cik", "")).zfill(10) != cfg["cik"]:
        raise ValueError("COMPANYFACTS_CIK_MISMATCH")
    facts = (payload.get("facts") or {}).get("us-gaap") or {}
    current, prior = cfg["current_accession"], cfg["prior_accession"]
    end, p_end, b_end = cfg["end"], cfg["prior_end"], cfg["begin_end"]
    if (current_meta.get("accession") != current or current_meta.get("report_date") != end
            or prior_meta.get("accession") != prior
            or prior_meta.get("report_date") != p_end):
        raise ValueError("SEC_FILING_PERIOD_BINDING_MISMATCH")
    if _digest(raw) != cfg["companyfacts_sha256"]:
        raise ValueError("COMPANYFACTS_SOURCE_FINGERPRINT_MISMATCH")
    if filing_html is None:
        raise ValueError("OFFICIAL_10K_BODY_REQUIRED")
    body_lower = filing_html.decode("utf-8", errors="replace").lower()
    if cfg["issuer_title"] not in body_lower or b"form 10-k" not in body_lower.encode():
        raise ValueError("OFFICIAL_10K_BODY_ISSUER_OR_FORM_MISMATCH")

    # Flows use the current filed annual statement's comparative columns.
    ni_t = _required(facts, "NetIncomeLoss", current, end, flow=True)
    ni_p = _required(facts, "NetIncomeLoss", current, p_end, flow=True)
    cfo_t = _required(facts, "NetCashProvidedByUsedInOperatingActivities", current,
                       end, flow=True)
    rev_t = _required(facts, cfg["revenue_tag"], current, end, flow=True)
    rev_p = _required(facts, cfg["revenue_tag"], current, p_end, flow=True)
    cogs_t = _required(facts, cfg["cogs_tag"], current, end, flow=True)
    cogs_p = _required(facts, cfg["cogs_tag"], current, p_end, flow=True)

    assets_t = _required(facts, "Assets", current, end, flow=False)
    assets_p = _required(facts, "Assets", current, p_end, flow=False)
    assets_b = _required(facts, "Assets", prior, b_end, flow=False)
    ca_t = _required(facts, "AssetsCurrent", current, end, flow=False)
    ca_p = _required(facts, "AssetsCurrent", current, p_end, flow=False)
    cl_t = _required(facts, "LiabilitiesCurrent", current, end, flow=False)
    cl_p = _required(facts, "LiabilitiesCurrent", current, p_end, flow=False)
    debt_t = _debt(facts, cfg["debt_2025"], current, end, filing_html)
    debt_p = _debt(facts, cfg["debt_2024"], current, p_end, filing_html)
    issued = _issue(facts, cfg["issue_tags"], current, end,
                    ni_t["start"])

    with localcontext() as context:
        context.prec = 60
        D = Decimal
        n_t, n_p = D(ni_t["value"]), D(ni_p["value"])
        cfo = D(cfo_t["value"])
        a_t, a_p, a_b = D(assets_t["value"]), D(assets_p["value"]), D(assets_b["value"])
        revenue_t, revenue_p = D(rev_t["value"]), D(rev_p["value"])
        cogs_current, cogs_prior = D(cogs_t["value"]), D(cogs_p["value"])
        cur_a, prev_a = D(ca_t["value"]), D(ca_p["value"])
        cur_l, prev_l = D(cl_t["value"]), D(cl_p["value"])
        debt_current, debt_prior = D(debt_t["value"]), D(debt_p["value"])
        if min(a_t, a_p, a_b, revenue_t, revenue_p, cur_l, prev_l) <= 0:
            raise ValueError("S9_REQUIRED_POSITIVE_DENOMINATOR_FAILED")
        roa_t, roa_p = n_t/a_p, n_p/a_b
        avg_t, avg_p = (a_t+a_p)/2, (a_p+a_b)/2
        leverage_t, leverage_p = debt_current/avg_t, debt_prior/avg_p
        liquidity_t, liquidity_p = cur_a/cur_l, prev_a/prev_l
        margin_t, margin_p = (revenue_t-cogs_current)/revenue_t, (revenue_p-cogs_prior)/revenue_p
        turnover_t, turnover_p = revenue_t/avg_t, revenue_p/avg_p
        signals = {
            "F_ROA": int(roa_t > 0), "F_CFO": int(cfo > 0),
            "F_DELTA_ROA": int(roa_t-roa_p > 0),
            "F_ACCRUAL": int(cfo > n_t),
            "F_DELTA_LEVERAGE": int(leverage_t < leverage_p),
            "F_DELTA_LIQUIDITY": int(liquidity_t > liquidity_p),
            "F_NO_COMMON_EQUITY_ISSUANCE": int(not issued["issued"]),
            "F_DELTA_GROSS_MARGIN": int(margin_t > margin_p),
            "F_DELTA_ASSET_TURNOVER": int(turnover_t > turnover_p),
        }
        count = sum(signals.values())
        score = D(100)*D(count)/D(9)
        ratios = {
            "roa_current": str(roa_t), "roa_prior": str(roa_p),
            "leverage_current": str(leverage_t), "leverage_prior": str(leverage_p),
            "liquidity_current": str(liquidity_t), "liquidity_prior": str(liquidity_p),
            "gross_margin_current": str(margin_t), "gross_margin_prior": str(margin_p),
            "asset_turnover_current": str(turnover_t), "asset_turnover_prior": str(turnover_p),
        }

    decimal_reference = _independent_reference(
        ni_t, ni_p, cfo_t, assets_t, assets_p, assets_b, rev_t, rev_p, cogs_t,
        cogs_p, ca_t, ca_p, cl_t, cl_p, debt_t, debt_p, issued)
    if decimal_reference["score"] != str(score) or decimal_reference["signals"] != signals:
        raise ValueError("S9_DECIMAL_REFERENCE_MISMATCH")
    material = {"ticker": ticker, "cik": cfg["cik"], "end": end,
                "current_accession": current, "prior_accession": prior,
                "current_filing": current_meta, "prior_filing": prior_meta,
                "facts": {"ni_current": ni_t, "ni_prior": ni_p, "cfo_current": cfo_t,
                          "revenue_current": rev_t, "revenue_prior": rev_p,
                          "cogs_current": cogs_t, "cogs_prior": cogs_p,
                          "assets_current": assets_t, "assets_prior": assets_p,
                          "assets_begin_prior": assets_b, "current_assets": ca_t,
                          "prior_current_assets": ca_p, "current_liabilities": cl_t,
                          "prior_current_liabilities": cl_p, "debt_current": debt_t,
                          "debt_prior": debt_p, "equity_issuance": issued}}
    material["source_companyfacts_sha256"] = _digest(raw)
    material["model_source_sha256"] = MODEL_SOURCE_SHA256
    material["independent_decimal_reference"] = decimal_reference
    material["financial_ratios"] = ratios
    material["signals"] = signals
    material["signal_count"] = count
    material["score_decimal"] = str(score)
    material["score"] = float(score)
    material["score_status"] = "REAL_SCORE_ACCEPTED_RESEARCH"
    material["historical_pit_accepted"] = False
    material["canonical_accepted"] = False
    material["current_filing_header_sha256"] = cfg["header_sha256"]
    material["filing_url"] = cfg["filing_url"]
    if filing_html is not None:
        material["filing_body_sha256"] = _digest(filing_html)
        # Each current filing explicitly reports common-stock issuance amounts.
        for row in issued["basis"]:
            amount = f"{int(Decimal(row['value'])/Decimal(1000)):,}"
            if amount not in filing_html.decode("utf-8", errors="replace"):
                # IXBRL may render ungrouped digits; require either representation.
                plain = str(int(Decimal(row["value"])/Decimal(1000)))
                if plain.encode() not in filing_html:
                    raise ValueError("ISSUANCE_FACT_NOT_FOUND_IN_CURRENT_10K_BODY")
    return material


def _independent_reference(ni_t, ni_p, cfo_t, assets_t, assets_p, assets_b,
                           rev_t, rev_p, cogs_t, cogs_p, ca_t, ca_p, cl_t,
                           cl_p, debt_t, debt_p, issued):
    """Separate explicit Decimal-ratio implementation for the nine binary gates."""
    with localcontext() as context:
        context.prec = 60
        d = Decimal
        n0, n1 = d(ni_t["value"]), d(ni_p["value"])
        cash = d(cfo_t["value"])
        a0, a1, a2 = d(assets_t["value"]), d(assets_p["value"]), d(assets_b["value"])
        sales0, sales1 = d(rev_t["value"]), d(rev_p["value"])
        cost0, cost1 = d(cogs_t["value"]), d(cogs_p["value"])
        current_ratio0 = d(ca_t["value"])/d(cl_t["value"])
        current_ratio1 = d(ca_p["value"])/d(cl_p["value"])
        leverage0 = d(debt_t["value"])/(a0+a1)*2
        leverage1 = d(debt_p["value"])/(a1+a2)*2
        flags = {
            "F_ROA": int(n0/a1 > 0), "F_CFO": int(cash > 0),
            "F_DELTA_ROA": int(n0/a1 > n1/a2), "F_ACCRUAL": int(cash > n0),
            "F_DELTA_LEVERAGE": int(leverage0 < leverage1),
            "F_DELTA_LIQUIDITY": int(current_ratio0 > current_ratio1),
            "F_NO_COMMON_EQUITY_ISSUANCE": int(not issued["issued"]),
            "F_DELTA_GROSS_MARGIN": int((sales0-cost0)/sales0 > (sales1-cost1)/sales1),
            "F_DELTA_ASSET_TURNOVER": int(sales0/(a0+a1)*2 > sales1/(a1+a2)*2),
        }
        count = sum(flags.values())
        return {"signals": flags, "signal_count": count,
                "score": str(d(100)*d(count)/d(9)),
                "reference": "independent_60_digit_decimal_ratios"}


def create_receipt(*, ticker: str, runtime: Path, cache_root: Path,
                   companyfacts_archive: Path, filing_html: bytes,
                   submissions_cache: Path, now=None) -> dict:
    cfg = TARGETS[ticker]
    cik = cfg["cik"]
    with zipfile.ZipFile(companyfacts_archive) as archive:
        member = f"CIK{cik}.json"
        raw = archive.read(member)
    sec = SECCache(cache_root, contact=None, request_budget=0)
    current, current_source = _verify_filing_metadata(sec, runtime, cfg,
                                                       cfg["current_accession"], cfg["end"])
    prior, prior_source = _verify_filing_metadata(sec, runtime, cfg,
                                                   cfg["prior_accession"], cfg["prior_end"])
    result = score_companyfacts(ticker, raw, current_meta=current,
                                prior_meta=prior, filing_html=filing_html)
    header = _verify_current_header(sec, cfg)
    result["current_filing_header"] = header
    result["as_of"] = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    result["submissions_sources"] = {"current": current_source, "prior": prior_source}
    result["private_cache_path"] = str(cache_root.resolve())
    result["runtime_path"] = str(runtime.resolve())
    result["companyfacts_archive_path"] = str(companyfacts_archive.resolve())
    result["submission_cache_path"] = str(submissions_cache.resolve())
    result["filing_response_sha256"] = _digest(filing_html)
    return result


def verify_s9_receipt(receipt_path: Path, *, companyfacts_archive: Path,
                      cache_root: Path, runtime: Path) -> dict:
    receipt_path = Path(receipt_path)
    if (receipt_path.name != "report.json" or receipt_path.parent.parent.name != "piotroski_s9"
            or receipt_path.is_symlink() or not receipt_path.is_file()):
        raise ValueError("PRIVATE_V7_S9_RECEIPT_REQUIRED")
    raw_receipt = receipt_path.read_bytes()
    seal_path = Path(str(receipt_path)+".sha256")
    if not seal_path.is_file() or seal_path.read_text("ascii").strip() != _digest(raw_receipt):
        raise ValueError("S9_RECEIPT_SEAL_CHANGED")
    previous = json.loads(raw_receipt)
    ticker = previous.get("ticker")
    if ticker not in TARGETS or previous.get("score_status") != "REAL_SCORE_ACCEPTED_RESEARCH":
        raise ValueError("S9_RECEIPT_STATUS_OR_TICKER_INVALID")
    cfg = TARGETS[ticker]
    with zipfile.ZipFile(companyfacts_archive) as archive:
        companyfacts_raw = archive.read(f"CIK{cfg['cik']}.json")
    sec = SECCache(Path(cache_root), contact=None, request_budget=0)
    current, current_source = _verify_filing_metadata(sec, Path(runtime), cfg,
                                                       cfg["current_accession"], cfg["end"])
    prior, prior_source = _verify_filing_metadata(sec, Path(runtime), cfg,
                                                   cfg["prior_accession"], cfg["prior_end"])
    header = _verify_current_header(sec, cfg)
    filed_path = Path(cache_root)/"responses"/_digest(cfg["filing_url"].encode())
    # The response URL is hashed for SEC cache lookup. Both response and receipt hashes must agree.
    file_hash = _digest(cfg["filing_url"].encode())
    body_path = Path(cache_root)/"responses"/(file_hash+".bin")
    meta_path = Path(cache_root)/"responses"/(file_hash+".json")
    if not body_path.is_file() or not meta_path.is_file():
        raise ValueError("S9_OFFICIAL_FILING_BODY_CACHE_MISSING")
    filing_html = body_path.read_bytes()
    metadata = json.loads(meta_path.read_text(encoding="utf8"))
    if metadata.get("url") != cfg["filing_url"] or metadata.get("sha256") != _digest(filing_html):
        raise ValueError("S9_OFFICIAL_FILING_BODY_HASH_MISMATCH")
    replay = score_companyfacts(ticker, companyfacts_raw,
                                current_meta=current, prior_meta=prior,
                                filing_html=filing_html)
    for key, value in (("as_of", previous.get("as_of")),
                       ("submissions_sources", {"current": current_source,"prior": prior_source}),
                       ("private_cache_path", str(Path(cache_root).resolve())),
                       ("runtime_path", str(Path(runtime).resolve())),
                       ("companyfacts_archive_path", str(Path(companyfacts_archive).resolve())),
                       ("submission_cache_path", previous.get("submission_cache_path"))):
        replay[key] = value
    replay["current_filing_header"] = header
    replay["filing_response_sha256"] = _digest(filing_html)
    if replay != previous:
        raise ValueError("S9_ORIGINAL_SEC_COMPANYFACTS_REPLAY_CHANGED")
    if sec.requests:
        raise ValueError("S9_VERIFICATION_MUST_BE_OFFLINE")
    return replay


def seal_report(result: dict, report_path: Path):
    report_path = Path(report_path)
    if (report_path.exists() or report_path.is_symlink()
            or report_path.parent.parent.name != "piotroski_s9"):
        raise ValueError("NEW_PRIVATE_S9_REPORT_PATH_REQUIRED")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True,
                       allow_nan=False)+"\n").encode()
    with report_path.open("xb") as stream:
        stream.write(data)
    seal_path = Path(str(report_path)+".sha256")
    with seal_path.open("x", encoding="ascii") as stream:
        stream.write(_digest(data)+"\n")
