"""Reconcile historical INOD accession reports to sealed SEC Submissions bytes.

Only administrative SEC facts are admitted. No publication or vendor-arrival
timestamp is inferred from the present-day Submissions response.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json


def _utc(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("TIMEZONE_OFFSET_REQUIRED")
    return parsed.astimezone(timezone.utc).isoformat()


def reconcile(submissions: bytes, receipt_bytes: bytes, phase24k: bytes, phase24m: bytes) -> dict:
    """Require exact source seal and 7/7 accession/form/date/acceptance joins."""
    receipt = json.loads(receipt_bytes)
    source_digest = sha256(submissions).hexdigest()
    if (source_digest != receipt.get("sha256") or len(submissions) != receipt.get("bytes")
            or receipt.get("http_status") != 200):
        raise ValueError("SEC_SUBMISSIONS_RECEIPT_MISMATCH")
    sec = json.loads(submissions)
    k = json.loads(phase24k)
    m = json.loads(phase24m)
    if str(sec.get("cik", "")).zfill(10) != str(receipt.get("cik", "")).zfill(10):
        raise ValueError("CIK_MISMATCH")
    if str(sec.get("cik", "")).zfill(10) != "0000903651":
        raise ValueError("UNEXPECTED_ISSUER")
    if k.get("eligible_for_canonical_PIT_promotion") is not False or m.get("canonical_PIT_certified") is not False:
        raise ValueError("UPSTREAM_PIT_STATUS_CONFLICT")
    recent = sec["filings"]["recent"]
    keys = ("accessionNumber", "form", "filingDate", "acceptanceDateTime")
    if len({len(recent[key]) for key in keys}) != 1:
        raise ValueError("SEC_PARALLEL_ARRAYS_INVALID")
    accessions = recent["accessionNumber"]
    if len(accessions) != len(set(accessions)):
        raise ValueError("SEC_ACCESSION_DUPLICATE")
    sec_by_accession = {accession: i for i, accession in enumerate(accessions)}
    k_rows = k["accessions"]
    m_rows = m["records"]
    if len(k_rows) != 7 or len(m_rows) != 7:
        raise ValueError("HISTORICAL_COHORT_NOT_SEVEN")
    if len({r["accession"] for r in k_rows}) != 7 or len({r["accession"] for r in m_rows}) != 7:
        raise ValueError("HISTORICAL_ACCESSION_DUPLICATE")
    m_by_accession = {r["accession"]: r for r in m_rows}
    if set(m_by_accession) != {r["accession"] for r in k_rows}:
        raise ValueError("HISTORICAL_REPORT_COHORT_MISMATCH")
    rows = []
    for old in k_rows:
        accession = old["accession"]
        if accession not in sec_by_accession:
            raise ValueError("ACCESSION_NOT_IN_SEALED_SEC_RESPONSE")
        i = sec_by_accession[accession]
        prior = m_by_accession[accession]
        official = {
            "form": recent["form"][i],
            "filing_date": recent["filingDate"][i],
            "accepted_at": _utc(recent["acceptanceDateTime"][i]),
        }
        if (old["form"] != official["form"] or old["filing_date"] != official["filing_date"]
                or _utc(old["accepted_utc"]) != official["accepted_at"]
                or prior["form"] != official["form"]
                or prior["SEC_official_filing_date_unmodified"] != official["filing_date"]
                or _utc(prior["SEC_accepted_utc_unmodified"]) != official["accepted_at"]):
            raise ValueError("SEC_ADMINISTRATIVE_CLOCK_CONFLICT")
        if old.get("PIT_certified") is not False or prior.get("daily_PIT_replay_use_permitted") is not False:
            raise ValueError("UPSTREAM_ACCESSION_PIT_STATUS_CONFLICT")
        rows.append({"accession": accession, **official,
                     "administrative_join_verified": True,
                     "first_public_at": None,
                     "historical_provider_first_available_at": None,
                     "historical_issuer_mapping_verified": False,
                     "canonical_pit_eligible": False,
                     "missing": ["FIRST_PUBLICATION", "HISTORICAL_PROVIDER_ARRIVAL",
                                 "HISTORICAL_ISSUER_MAPPING"]})
    rows.sort(key=lambda r: (r["accepted_at"], r["accession"]))
    return {"schema": "M10_V13_PIT_SEC_ADMIN_RECONCILIATION_V1",
            "cik": "0000903651", "sources": {
                "sec_submissions_sha256": source_digest,
                "sec_receipt_sha256": sha256(receipt_bytes).hexdigest(),
                "phase24k_bytes_sha256": sha256(phase24k).hexdigest(),
                "phase24m_bytes_sha256": sha256(phase24m).hexdigest(),
                "submissions_retrieved_at": receipt.get("checked_at")},
            "administrative_joins_verified": len(rows),
            "public_dissemination_verified": 0,
            "historical_provider_arrivals_verified": 0,
            "canonical_pit_versions": 0,
            "s16c_features_accepted": 0,
            "rows": rows}
