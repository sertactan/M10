"""V8 offline evidence audit for frozen S8 and S10; deliberately never scores.

Companyfacts prove reported XBRL facts, not complete Ohlson SIZE deflation or
an eligible five-year historical residual-quality peer regression.  This module
reads only five named members of an existing SEC Companyfacts bulk ZIP, checks
their previously published SHA-256 digests, and records exact 10-K fiscal
windows without creating a database, derived model, or canonical observation.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from hashlib import sha256
import json
import math
from pathlib import Path
import zipfile

FROZEN_SOURCE_SHA256 = "53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794"
MODEL_SCOPE = "RESEARCH_INPUT_INVENTORY_ONLY_NOT_CANONICAL_PIT"
FISCAL_YEARS = (2021, 2022, 2023, 2024, 2025)

# Existing V4/V6/V7 source hash pins and exact FY2025 10-K accession evidence.
TARGETS = {
    "INOD": {"cik": "0000903651", "fy_end": "2025-12-31",
             "accession": "0001104659-26-020655",
             "sha256": "6ccc9dcc93b9c303cee51c166f345350fb16258408c884e2ed5d1231f2741b38"},
    "TMDX": {"cik": "0001756262", "fy_end": "2025-12-31",
             "accession": "0001193125-26-067032",
             "sha256": "8096066125323b72557bd9d582cfab4bcdec59b814cee4e082ede5ade1a800ab"},
    "CRMD": {"cik": "0001410098", "fy_end": "2025-12-31",
             "accession": "0001213900-26-023889",
             "sha256": "b75757faacc84388fbe591a3ec2593969ffefe3c9ea86056a188a6fcb0c2f8bb"},
    "PENG": {"cik": "0001616533", "fy_end": "2025-08-29",
             "accession": "0001616533-25-000061",
             "sha256": "7f49ae1db8700690e6ea142ddafad7a524e5ab04b5a49e16e5be72bd82ebaca6"},
    "ETON": {"cik": "0001710340", "fy_end": "2025-12-31",
             "accession": "0001437749-26-009059",
             "sha256": "f7f154bb5484ead9734e7792fe9226c296b72a5adb5779a7e452499ba4d8b45b"},
}

# These are strict US-GAAP *diagnostic inventory tags*, not a declaration that
# Companyfacts itself supplies all the frozen S8/S10 derived variables.
S8_TAGS = {
    "assets": ("Assets", False),
    "liabilities": ("Liabilities", False),
    "equity": ("StockholdersEquity", False),
    "current_assets": ("AssetsCurrent", False),
    "current_liabilities": ("LiabilitiesCurrent", False),
    "net_income": ("NetIncomeLoss", True),
}
S10_TAGS = {
    "assets": ("Assets", False),
    "net_income": ("NetIncomeLoss", True),
    "cfo": ("NetCashProvidedByUsedInOperatingActivities", True),
    "current_assets": ("AssetsCurrent", False),
    "current_liabilities": ("LiabilitiesCurrent", False),
    "receivables": ("AccountsReceivableNetCurrent", False),
    "ppe": ("PropertyPlantAndEquipmentNet", False),
}


def _date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _record_key(row: dict) -> str:
    return sha256(json.dumps(row, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _annual(row: dict, *, year: int, end: str, flow: bool, accession: str | None) -> bool:
    if row.get("form") != "10-K" or row.get("end") != end:
        return False
    if accession and row.get("accn") != accession:
        return False
    # For older fiscal periods use original FY filings, rather than quietly
    # selecting a restated comparative from an unrelated newer accession.
    if not accession and (row.get("fy") != year or row.get("fp") != "FY"):
        return False
    if not isinstance(row.get("filed"), str) or not _date(row["filed"]):
        return False
    if type(row.get("val")) not in (int, float) or not math.isfinite(row["val"]):
        return False
    start = row.get("start")
    if not flow:
        return start is None
    begin, finish = _date(start), _date(end)
    return bool(begin and finish and 330 <= (finish - begin).days + 1 <= 400)


def fiscal_ends(gaap: dict, anchor: str) -> dict[int, str | None]:
    """Find FY end from issuer's own original 10-K Assets instant, not 12/31.

    We require one unique possible end within 40 days of the target's FY
    month/day. Ambiguities and genuinely unavailable historical years stay N/A.
    """
    ending = _date(anchor)
    assert ending is not None
    out = {2025: anchor}
    records = (gaap.get("Assets") or {}).get("units", {}).get("USD", [])
    for year in FISCAL_YEARS[:-1]:
        day = date(year, ending.month, min(ending.day, 28))
        hits = set()
        for row in records:
            end = _date(row.get("end"))
            if (end and end.year == year and abs((end - day).days) <= 40
                    and _annual(row, year=year, end=end.isoformat(),
                                flow=False, accession=None)):
                hits.add(end.isoformat())
        out[year] = next(iter(hits)) if len(hits) == 1 else None
    return out


def exact_fact(gaap: dict, tag: str, *, year: int, end: str | None,
               flow: bool, accession: str | None = None) -> dict:
    """Check matched annual concept, window, 10-K provenance and ambiguity."""
    if not end:
        return {"status": "FISCAL_YEAR_END_NOT_EVIDENCED", "period": str(year)}
    concept = gaap.get(tag)
    if not isinstance(concept, dict):
        return {"status": "US_GAAP_TAG_ABSENT", "period": end, "tag": tag}
    rows = (concept.get("units") or {}).get("USD", [])
    matches = [r for r in rows if isinstance(r, dict) and
               _annual(r, year=year, end=end, flow=flow, accession=accession)]
    if not matches:
        return {"status": "EXACT_10K_FY_WINDOW_MISSING", "period": end,
                "tag": tag, "accession": accession or "ORIGINAL_FY_10K"}
    # The exact same SEC record may appear more than once. Different records,
    # even identical values from different accessions, must be distinguished.
    distinct = {json.dumps(r, sort_keys=True, separators=(",", ":")) for r in matches}
    if len(distinct) > 1:
        return {"status": "AMBIGUOUS_MULTIPLE_RECORDS", "period": end,
                "tag": tag, "candidate_accessions":
                    sorted({str(r.get("accn")) for r in matches})}
    row = matches[0]
    return {"status": "EXACT_REPORTED_10K_FACT", "period": end, "tag": tag,
            "accession": row.get("accn"), "filed": row["filed"],
            "record_sha256": _record_key(row), "unit": "USD",
            "acceptance_or_public_pit_proven": False}


def audit_payload(ticker: str, raw: bytes) -> dict:
    """Independently check a single existing SEC bulk member; never score."""
    if ticker not in TARGETS:
        raise ValueError("Ticker not in frozen five-stock set")
    target = TARGETS[ticker]
    checksum = sha256(raw).hexdigest()
    if checksum != target["sha256"]:
        raise ValueError(f"SEC_COMPANYFACTS_SHA256_MISMATCH:{ticker}")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or str(payload.get("cik")).zfill(10) != target["cik"]:
        raise ValueError(f"SEC_COMPANYFACTS_CIK_MISMATCH:{ticker}")
    gaap = payload.get("facts", {}).get("us-gaap")
    if not isinstance(gaap, dict):
        raise ValueError(f"SEC_US_GAAP_SECTION_MISSING:{ticker}")
    ends = fiscal_ends(gaap, target["fy_end"])
    s8 = {}
    for year in (2024, 2025):
        end = ends[year]
        s8[str(year)] = {
            name: exact_fact(gaap, tag, year=year, end=end, flow=flow,
                             accession=target["accession"] if year == 2025 else None)
            for name, (tag, flow) in S8_TAGS.items()
        }
    s10 = {}
    for year in FISCAL_YEARS:
        end = ends[year]
        s10[str(year)] = {
            name: exact_fact(gaap, tag, year=year, end=end, flow=flow,
                             accession=target["accession"] if year == 2025 else None)
            for name, (tag, flow) in S10_TAGS.items()
        }
    missing_s8 = [
        f"{year}:{name}:{fact['status']}"
        for year, items in s8.items() for name, fact in items.items()
        if fact["status"] != "EXACT_REPORTED_10K_FACT"
    ]
    missing_s10 = [
        f"{year}:{name}:{fact['status']}"
        for year, items in s10.items() for name, fact in items.items()
        if fact["status"] != "EXACT_REPORTED_10K_FACT"
    ]
    # Independently mandatory, source-specific requirements intentionally
    # remain unqualified. S8: an original contract-compatible GNP index with
    # base year, unit conversion, period, observation and source hash.
    # S10: five years of the FROZEN accrual/cash-flow mappings, historical
    # same-industry eligible peers at each FY, regression and normalization.
    missing_s8 += [
        f"{ends[y]}:OHLSON_SIZE_GNP_PRICE_INDEX:FROZEN_SERIES_AND_BASE_UNVERIFIED"
        for y in (2024, 2025)
    ]
    missing_s8 += [
        "OHLSON_FUNDS_FROM_OPERATIONS_TO_LIABILITIES:ISSUER_CLASSIFICATION_UNVERIFIED",
        "OHLSON_DISTRESS_BINARY_AND_CHANGE_NI:ORIGINAL_RUBRIC_INPUT_REVIEW",
    ]
    missing_s10 += [
        f"{year}:{ends[year] or 'FY_END_UNKNOWN'}:ELIGIBLE_HISTORIC_INDUSTRY_PEER_PANEL:"
        "DATED_MEMBERSHIP_AND_SOURCE_RECEIPTS_MISSING" for year in FISCAL_YEARS
    ]
    missing_s10 += [
        "FROZEN_S10_ACCRUAL_AND_CASH_FLOW_VARIABLE_MAPPINGS_UNVERIFIED",
        "FROZEN_S10_REGRESSION_COEFFICIENTS_AND_RESIDUAL_NORMALIZATION_UNVERIFIED",
        "S10_PEER_MINIMUM_AND_MATCH_POLICY_NOT_LOCALLY_SOURCE_VERIFIED",
    ]
    return {
        "ticker": ticker, "cik": target["cik"],
        "companyfacts_sha256": checksum, "source": "LOCAL_SEC_COMPANYFACTS_BULK_ZIP",
        "fy2025_10k_accession": target["accession"], "fiscal_ends": ends,
        "source_scope": MODEL_SCOPE, "network_requests": 0,
        "s8": {"status": "DATA_MISSING", "score": None,
               "annual_fact_inventory": s8, "missing": missing_s8,
               "gnp_size_deflator_verified": False},
        "s10": {"status": "DATA_MISSING", "score": None,
                "annual_fact_inventory": s10, "missing": missing_s10,
                "historical_industry_peer_panel_verified": False},
        "research_score_promoted": False, "canonical_pit_accepted": False,
    }


def audit_bulk(archive: Path) -> dict:
    """Read five exact members only: no extractall, directory scans or HTTP."""
    archive = Path(archive)
    if archive.is_symlink() or not archive.is_file():
        raise ValueError("Existing regular SEC Companyfacts ZIP required")
    results = {}
    with zipfile.ZipFile(archive) as zf:
        for ticker, cfg in TARGETS.items():
            entry = f"CIK{cfg['cik']}.json"
            info = zf.getinfo(entry)
            if info.file_size > 40_000_000:
                raise ValueError(f"SEC_MEMBER_TOO_LARGE:{ticker}")
            results[ticker] = audit_payload(ticker, zf.read(info))
    return {
        "schema": "M10_V8_S8_S10_FROZEN_EVIDENCE_AUDIT_V1",
        "contract_sha256": FROZEN_SOURCE_SHA256,
        "scope": MODEL_SCOPE,
        "source_bulk_archive": str(archive),
        "bulk_read_mode": "FIVE_EXACT_ZIP_MEMBERS_ONLY",
        "network_requests": 0, "new_scores": 0, "canonical_pit_accepted": 0,
        "research_score_baseline_v7_unchanged": 15,
        "stocks": results,
    }


def missing_matrix(report: dict) -> list[dict]:
    """Small, reviewable table with every missing period/deflator/peer."""
    rows = []
    for ticker, item in report["stocks"].items():
        for model in ("s8", "s10"):
            rows.append({
                "ticker": ticker, "model": model.upper(),
                "fiscal_ends": item["fiscal_ends"], "score": None,
                "missing": item[model]["missing"],
                "reported_fact_statuses": dict(Counter(
                    fact["status"] for per in item[model]["annual_fact_inventory"].values()
                    for fact in per.values()
                )),
            })
    return rows
