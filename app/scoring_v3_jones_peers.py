"""Read-only SEC Companyfacts peer ingest for original S11 Modified Jones.

The SEC's Companyfacts bulk ZIP carries audited figures, but no dated SIC or
NAICS classifications and no accession acceptance timestamps. Both are
independently required by app.recovered_jones.compute_s11. An as-of SEC
Submissions SIC snapshot is a *hint*, never historical FY2025 SIC evidence.

Only source-linked, time-aligned annual rows are admitted. No zero-valued
imputation, ambiguous tag coalescing, unaudited SIC inference or score promotion.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Mapping
import zipfile

from app.recovered_jones import (
    MAX_FISCAL_END_GAP_DAYS, MIN_OTHER_PEERS, compute_s11,
)

_CIK = re.compile(r"\d{1,10}\Z")
_ACCESSION = re.compile(r"\d{10}-\d{2}-\d{6}\Z")
_HEX = re.compile(r"[0-9a-fA-F]{64}\Z")
_TAGS = {
    "NET_INCOME": "NetIncomeLoss",
    "OPERATING_CASH_FLOW": "NetCashProvidedByUsedInOperatingActivities",
    "REVENUE": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "ACCOUNTS_RECEIVABLE_NET": "AccountsReceivableNetCurrent",
    "PPE_NET": "PropertyPlantAndEquipmentNet",
    "TOTAL_ASSETS": "Assets",
}
INSTANT = {"ACCOUNTS_RECEIVABLE_NET", "PPE_NET", "TOTAL_ASSETS"}


def _utc(when):
    if not isinstance(when, str):
        return None
    try:
        value = datetime.fromisoformat(when.replace("Z", "+00:00"))
        return value.astimezone(timezone.utc) if value.tzinfo else None
    except ValueError:
        return None


def _sha(raw):
    return sha256(raw).hexdigest()


def _canon(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf8")


def _cik(value):
    value = str(value)
    if not _CIK.fullmatch(value) or int(value) == 0:
        raise ValueError("Valid SEC CIK is required")
    return value.zfill(10)


def read_universe(db_file: Path) -> tuple[list[dict], dict]:
    """Inventory active root security universe, strictly SQLite read-only.

    immutable=1 prevents creating WAL or shared-memory files beside a live DB.
    Immutable snapshots might omit uncheckpointed WAL entries; no PIT claim.
    """
    db_file = Path(db_file)
    if not db_file.is_file() or db_file.is_symlink():
        raise ValueError("Verified local universe SQLite file required")
    uri = "file:" + db_file.resolve().as_posix() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        # Do not infer a dated SIC from sector/industry text in security_master.
        rows = conn.execute(
            "SELECT security_id,ticker,cik,active FROM security_master "
            "ORDER BY ticker,security_id"
        ).fetchall()
        cls = conn.execute("SELECT COUNT(*) FROM security_classification_history").fetchone()[0]
    universe = [{"security_id": str(sid), "ticker": ticker,
                 "cik": str(cik).zfill(10) if cik and _CIK.fullmatch(str(cik)) else None,
                 "active": bool(active)} for sid, ticker, cik, active in rows]
    return universe, {
        "total_security_master": len(universe),
        "unique_sec_cik": len({r["cik"] for r in universe if r["cik"]}),
        "classification_history_rows": cls,
        "sqlite_read_mode": "IMMUTABLE_READONLY_LIVE_WAL_NOT_INCLUDED",
    }


def cached_archive_companyfacts(archive_file: Path, cik: str) -> tuple[bytes | None, dict]:
    """Read only one CIK from the bulk ZIP; never unpack its ~19GB contents."""
    cik = _cik(cik)
    archive_file = Path(archive_file)
    if not archive_file.is_file() or archive_file.is_symlink():
        return None, {"status": "BULK_ZIP_MISSING"}
    filename = f"CIK{cik}.json"
    with zipfile.ZipFile(archive_file, "r") as zf:
        try:
            entry = zf.getinfo(filename)
        except KeyError:
            return None, {"status": "CIK_NOT_IN_BULK_ZIP", "entry": filename}
        if entry.file_size > 50_000_000:
            return None, {"status": "SEC_ENTRY_TOO_LARGE", "entry": filename}
        raw = zf.read(entry)
    return raw, {
        "status": "BULK_SEC_COMPANYFACTS_CACHE", "entry": filename,
        "source_sha256": _sha(raw), "bytes": len(raw),
        "archive_path": str(archive_file), "network_requests": 0,
    }


def _submission_accession(payload: dict, fiscal_year: int, *, at: datetime):
    """Find exactly one annual 10-K with matching reportDate and SEC acceptance."""
    recent = (payload.get("filings") or {}).get("recent") or {}
    fields = ("accessionNumber", "form", "reportDate", "filingDate", "acceptanceDateTime")
    arrays = [recent.get(field) for field in fields]
    if not all(isinstance(a, list) for a in arrays) or len({len(a) for a in arrays}) != 1:
        return None, "SEC_SUBMISSIONS_INDEX_MISSING_OR_MISALIGNED"
    hits = []
    amended = False
    for values in zip(*arrays):
        accession, form, report_date, filed, accepted = values
        when = _utc(accepted)
        period = None
        filed_day = None
        try:
            period = date.fromisoformat(report_date)
            filed_day = date.fromisoformat(filed)
        except (TypeError, ValueError):
            continue
        if (period.year != fiscal_year
                or abs((period - date(fiscal_year, 12, 31)).days)
                > MAX_FISCAL_END_GAP_DAYS or not when or when > at):
            continue
        if form == "10-K/A":
            amended = True
            continue
        if (form == "10-K"
                and _ACCESSION.fullmatch(str(accession or ""))
                and 0 <= (when.date() - filed_day).days <= 1):
            hits.append({"accession": accession, "accepted_at": when.isoformat(),
                         "filing_date": filed, "report_date": report_date})
    if amended:
        return None, "FY2025_10K_AMENDMENT_REQUIRES_REVIEW"
    if len(hits) != 1:
        return None, ("FY2025_10K_ACCEPTANCE_MISSING" if not hits
                      else "MULTIPLE_FY2025_10K_ACCEPTANCES_CONFLICT")
    return hits[0], None


def _select_record(taxonomy, tag, accession, end, start):
    concept = taxonomy.get(tag)
    if not isinstance(concept, dict):
        return None, "EXACT_US_GAAP_TAG_MISSING"
    series = (concept.get("units") or {}).get("USD") or []
    def matching_start(record):
        if start != "__FULL_YEAR__":
            return record.get("start") == start
        try:
            initial = date.fromisoformat(record["start"])
            return 330 <= (date.fromisoformat(end) - initial).days + 1 <= 400
        except (TypeError, ValueError, KeyError):
            return False
    records = [r for r in series if isinstance(r, dict) and r.get("accn") == accession
               and r.get("form") == "10-K" and r.get("end") == end
               and matching_start(r) and r.get("filed")]
    # Duplicated SEC XBRL rows with identical content are safe to collapse.
    # Differing raw facts for the same concept/window remain ambiguous.
    if not records:
        return None, "EXACT_ACCESSION_WINDOW_MISSING"
    uniques = {_canon(r) for r in records}
    if len(uniques) != 1:
        return None, "DUPLICATE_OR_CONFLICTING_SEC_FACT"
    record = records[0]
    if type(record.get("val")) not in (int, float):
        return None, "NON_NUMERIC_SEC_FACT"
    from math import isfinite
    if not isfinite(record["val"]):
        return None, "NONFINITE_SEC_FACT"
    return record, None


def _historical_sic(header, *, cik, accession, fiscal_end, as_of, observed):
    """Only an actual SEC FY10-K SGML header can establish FY-period SIC.

    An SEC Submissions *current* SIC field cannot populate this input. The
    provided raw header is hash checked and independently matched to accession,
    issuer CIK, SEC FY report period, and bracketed assigned SIC.
    """
    if not isinstance(header, Mapping):
        return None, None
    raw = header.get("header_bytes")
    claimed_hash = header.get("header_sha256")
    if not isinstance(raw, bytes) or not isinstance(claimed_hash, str):
        return None, None
    content_sha = _sha(raw)
    if content_sha != claimed_hash.lower():
        return None, None
    when = _utc(header.get("observed_at"))
    if when is None or when > as_of or when < _utc(accession["accepted_at"]):
        return None, None
    uri = (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{int(cik)}/{accession['accession'].replace('-', '')}/{accession['accession']}.txt"
    )
    if header.get("source_ref") != uri:
        return None, None
    # Stop at the first filing header: do not find unrelated CIK/SIC in filing
    # exhibits or the rest of a complete archived submission.
    head = raw[:250000].decode("latin-1", errors="replace").split("</SEC-HEADER>", 1)[0]
    required = {
        "accession": re.search(r"ACCESSION NUMBER:\s*(\d{10}-\d{2}-\d{6})", head),
        "period": re.search(r"CONFORMED PERIOD OF REPORT:\s*(\d{8})", head),
        "type": re.search(r"CONFORMED SUBMISSION TYPE:\s*(10-K)\b", head),
        "cik": re.search(r"CENTRAL INDEX KEY:\s*(\d{1,10})", head),
        "sic": re.search(r"STANDARD INDUSTRIAL CLASSIFICATION:[^\r\n]*\[(\d{4})\]", head),
    }
    if not all(required.values()):
        return None, None
    if (required["accession"].group(1) != accession["accession"]
            or required["period"].group(1) != fiscal_end.replace("-", "")
            or int(required["cik"].group(1)) != int(cik)):
        return None, None
    sic = required["sic"].group(1)
    # Fiscal period is the explicit *classification anchor*, not a claim that
    # the SEC filing itself was publicly disseminated by fiscal year-end.
    industry = {
        "scheme": "SIC", "code": sic, "effective_on": fiscal_end,
        "source": "SEC_EDGAR",
        "source_ref": f"https://data.sec.gov/submissions/CIK{cik}.json",
        "evidence_hash": content_sha, "available_at": when.isoformat(),
    }
    evidence = {
        "original_header_url": uri, "original_header_sha256": content_sha,
        "original_header_observed_at": when.isoformat(),
        "accepted_at": accession["accepted_at"], "filing_report_date": fiscal_end,
        "sector_is_fy_filing_classification_not_pit_asof_fiscal_end": True,
        "original_header_content_sha_matches_local_bytes": True,
        "sec_origin_authenticity_is_not_cryptographically_guaranteed": True,
    }
    return industry, evidence


def extract_company_year(
    companyfacts_raw: bytes, submissions_raw: bytes, *,
    security_id: str, ticker: str, cik: str,
    as_of: datetime, submissions_observed_at: datetime,
    companyfacts_observed_at: datetime,
    dated_industry: Mapping | None = None,
    fiscal_year: int = 2025,
) -> tuple[dict | None, dict]:
    """Prepare the eight exact S11 fields and independently dated industry.

    All historical-filing facts must use ONE FY2025 10-K accession. SIC from a
    present-day SEC Submissions snapshot is diagnostic only; it does not supply
    'effective_on' for the 2025 reporting interval. A dated_industry entry must
    provide real SEC historical FY10-K SGML header bytes, URL, capture time,
    and independently verifiable SHA-256. Merely setting a verified flag is
    never accepted.
    """
    if not all(isinstance(t, datetime) and t.tzinfo is not None for t in
               (as_of, submissions_observed_at, companyfacts_observed_at)):
        raise ValueError("All timestamps must be timezone-aware")
    at = as_of.astimezone(timezone.utc)
    sub_time = submissions_observed_at.astimezone(timezone.utc)
    facts_time = companyfacts_observed_at.astimezone(timezone.utc)
    cik = _cik(cik)
    evidence = {"ticker": ticker, "security_id": security_id, "cik": cik,
                "fiscal_year": fiscal_year, "network_requests": 0,
                "companyfacts_sha256": _sha(companyfacts_raw),
                "submissions_sha256": _sha(submissions_raw),
                "submissions_observed_at": sub_time.isoformat(),
                "companyfacts_observed_at": facts_time.isoformat(),
                "selected": [], "missing": [], "scope": "RESEARCH_NOT_HISTORICAL_PIT"}
    if sub_time > at or facts_time > at:
        evidence["missing"].append("SOURCE_OBSERVED_AFTER_AS_OF")
        return None, evidence
    try:
        payload, submissions = json.loads(companyfacts_raw), json.loads(submissions_raw)
    except (ValueError, TypeError):
        evidence["missing"].append("INVALID_SEC_JSON")
        return None, evidence
    if not isinstance(payload, dict) or not isinstance(submissions, dict) or any(
        int(x.get("cik", -1)) != int(cik) for x in (payload, submissions)
    ):
        evidence["missing"].append("SEC_CIK_MISMATCH")
        return None, evidence
    evidence["reported_sec_sic_current_snapshot"] = submissions.get("sic")
    evidence["sic_snapshot_historical_fy_classification"] = False
    accession, error = _submission_accession(submissions, fiscal_year, at=at)
    if error:
        evidence["missing"].append(error)
        return None, evidence
    evidence["accession"] = accession
    facts_available = max(sub_time, facts_time, _utc(accession["accepted_at"]))
    taxonomy = (payload.get("facts") or {}).get("us-gaap") or {}
    rows = []
    annual_end = accession["report_date"]
    current_revenue, issue = _select_record(
        taxonomy, _TAGS["REVENUE"], accession["accession"],
        annual_end, "__FULL_YEAR__",
    )
    if issue:
        evidence["missing"].append("REVENUE_CURRENT_" + issue)
        return None, evidence
    period_start = current_revenue["start"]
    prior_end = (date.fromisoformat(period_start) - timedelta(days=1)).isoformat()
    previous_revenue, issue = _select_record(
        taxonomy, _TAGS["REVENUE"], accession["accession"],
        prior_end, "__FULL_YEAR__",
    )
    if issue:
        evidence["missing"].append("REVENUE_PREVIOUS_" + issue)
        return None, evidence
    previous_start = previous_revenue["start"]
    starts = (period_start, previous_start)
    ends = (annual_end, prior_end)
    selections = (
        ("NET_INCOME", 0), ("OPERATING_CASH_FLOW", 0),
        ("REVENUE", 0), ("REVENUE", 1),
        ("ACCOUNTS_RECEIVABLE_NET", 0), ("ACCOUNTS_RECEIVABLE_NET", 1),
        ("PPE_NET", 0), ("TOTAL_ASSETS", 1),
    )
    for metric, window in selections:
        end = ends[window]
        start = None if metric in INSTANT else starts[window]
        tag = _TAGS[metric]
        record, problem = _select_record(taxonomy, tag, accession["accession"], end, start)
        if problem:
            evidence["missing"].append(f"{metric}_{end}_{problem}")
            continue
        if record.get("filed") != accession["filing_date"]:
            evidence["missing"].append(f"{metric}_{end}_FILED_DATE_MISMATCH")
            continue
        fact_hash = _sha(_canon({"payload_sha256": evidence["companyfacts_sha256"],
                                "tag": tag, "record": record}))
        row = {
            "security_id": security_id, "metric": metric, "value": record["val"],
            "unit": "USD", "period_start": start, "period_end": end,
            "period_kind": "INSTANT" if metric in INSTANT else "ANNUAL",
            "source": "SEC_EDGAR",
            "source_ref": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
            "form_type": "10-K", "accession": accession["accession"],
            "filing_date": accession["filing_date"],
            "accepted_at": accession["accepted_at"],
            "available_at": facts_available.isoformat(), "evidence_hash": fact_hash,
        }
        evidence["selected"].append({
            "metric": metric, "period_end": end, "source_tag": f"us-gaap:{tag}",
            "accession": accession["accession"], "evidence_hash": fact_hash
        })
        rows.append(row)
    if evidence["missing"]:
        return None, evidence
    industry, industry_evidence = _historical_sic(
        dated_industry, cik=cik, accession=accession, fiscal_end=ends[0],
        as_of=at, observed=sub_time
    )
    if industry_evidence:
        evidence["historical_industry_provenance"] = industry_evidence
    if industry is None:
        evidence["missing"].append("DATED_SEC_INDUSTRY_CLASSIFICATION_FY2025")
    result = {
        "security_id": security_id, "cik": cik, "fiscal_year": fiscal_year,
        "period_start": starts[0], "period_end": ends[0],
        "industry": industry, "facts": rows,
    }
    return result, evidence


def scan_available(
    universe: list[dict], *, archive: Path, submissions_directory: Path,
    as_of: datetime, observed_at: datetime,
    dated_classifications: Mapping | None = None,
    ticker: str = "INOD",
) -> dict:
    """Cache-only exploration. Missing submissions/classifications remain N/A."""
    matches = [item for item in universe if item["ticker"] == ticker and item["cik"]]
    if len(matches) != 1:
        return {"ticker": ticker, "score": None, "blockers": ["UNIQUE_INOD_CIK_MISSING"]}
    target_identity = matches[0]
    raw, source = cached_archive_companyfacts(archive, target_identity["cik"])
    submission = Path(submissions_directory) / f"CIK{target_identity['cik']}.json"
    if raw is None or not submission.is_file() or submission.is_symlink():
        return {"ticker": ticker, "score": None, "source": source,
                "blockers": ["SEC_TARGET_COMPANYFACTS_OR_SUBMISSIONS_CACHE_MISSING"]}
    sub_raw = submission.read_bytes()
    # Receipt for all cached submission snapshots is separately validated by CLI.
    packet, audit = extract_company_year(
        raw, sub_raw, security_id=target_identity["security_id"], ticker=ticker,
        cik=target_identity["cik"], as_of=as_of, submissions_observed_at=observed_at,
        companyfacts_observed_at=observed_at,
        dated_industry=(dated_classifications or {}).get(target_identity["cik"]),
    )
    if packet is None:
        return {"ticker": ticker, "score": None, "source": source,
                "target": audit, "blockers": audit["missing"]}
    # Discover ONLY independently dated, evidenced classifications; the
    # operational 18,799-security universe is not a dated SIC cohort.
    grouped = []
    for item in universe:
        if item["security_id"] == target_identity["security_id"] or not item["cik"]:
            continue
        historical = (dated_classifications or {}).get(item["cik"])
        if not isinstance(historical, dict) or packet["industry"] is None:
            continue
        candidate_raw, candidate_source = cached_archive_companyfacts(archive, item["cik"])
        submission_path = Path(submissions_directory) / f"CIK{item['cik']}.json"
        if candidate_raw is None or not submission_path.is_file():
            continue
        other, other_audit = extract_company_year(
            candidate_raw, submission_path.read_bytes(),
            security_id=item["security_id"], ticker=item["ticker"], cik=item["cik"],
            as_of=as_of, submissions_observed_at=observed_at,
            companyfacts_observed_at=observed_at, dated_industry=historical,
        )
        if (other and not other_audit["missing"]
                and other["industry"]["scheme"] == packet["industry"]["scheme"]
                and other["industry"]["code"] == packet["industry"]["code"]):
            grouped.append(other)
    s11 = compute_s11(packet, grouped, as_of)
    return {
        "ticker": ticker, "score": s11["score"], "status": s11["status"],
        "target": audit, "source": source,
        "eligible_peer_count": s11["components"].get("eligible_peer_count", 0),
        "candidate_peer_count": len(grouped), "minimum_peer_count": MIN_OTHER_PEERS,
        "blockers": sorted(set(audit["missing"] + s11["missing"])),
        "s11_components": s11["components"] if s11["score"] is not None else {},
        "s11_evidence_hash": s11["evidence_hash"],
        "canonical_accepted": False,
    }
