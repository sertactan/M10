"""Offline SEC source-bound research availability; never infers historical PIT."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

SCHEMA = "M10_V4_SEC_SOURCE_CLOCKS_V1"


def _clock(value):
    stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("OFFSET_AWARE_CLOCK_REQUIRED")
    return stamp.astimezone(timezone.utc)


def audit_source_clocks(submissions_raw: bytes, submissions_receipt: dict,
                        documents: list[tuple[bytes, dict]], *, as_of: str) -> dict:
    """Require both sources observed by as-of, preserving all three clock meanings.

    Receipt times are local collection assertions, not independently certified
    provider availability. A match permits current research use only. Raw body
    and submissions integrity plus SEC exact document identity are necessary.
    """
    clock = _clock(as_of)
    if (submissions_receipt.get("sha256") != sha256(submissions_raw).hexdigest()
            or submissions_receipt.get("bytes") != len(submissions_raw)
            or submissions_receipt.get("provider") != "SEC_SUBMISSIONS"
            or submissions_receipt.get("http_status") != 200):
        raise ValueError("SUBMISSIONS_RECEIPT_MISMATCH")
    observed = _clock(submissions_receipt["checked_at"])
    payload = json.loads(submissions_raw)
    cik = str(int(payload["cik"]))
    if str(int(submissions_receipt["cik"])) != cik:
        raise ValueError("SUBMISSIONS_CIK_MISMATCH")
    recent = payload["filings"]["recent"]
    keys = ("accessionNumber", "acceptanceDateTime", "form", "filingDate", "primaryDocument")
    columns = [recent[k] for k in keys]
    if not all(isinstance(c, list) for c in columns) or len({len(c) for c in columns}) != 1:
        raise ValueError("SUBMISSIONS_ARRAYS_MISMATCH")
    indexed = {}
    for accession, accepted, form, filed, primary in zip(*columns):
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession) or accession in indexed:
            raise ValueError("INVALID_OR_DUPLICATE_ACCESSION")
        indexed[accession] = (_clock(accepted), form, filed, primary)
    rows, seen = [], set()
    for body, receipt in documents:
        accession = receipt.get("accession")
        if accession in seen:
            raise ValueError("DUPLICATE_DOCUMENT_RECEIPT")
        seen.add(accession)
        reasons = []
        source = indexed.get(accession)
        retrieved = _clock(receipt["retrieved_at"])
        digest = sha256(body).hexdigest()
        if (receipt.get("schema") != "M10_V3_PRIVATE_SEC_HTML_CACHE_RECEIPT_V1"
                or receipt.get("sha256") != digest or receipt.get("bytes") != len(body)):
            reasons.append("BODY_RECEIPT_MISMATCH")
        if source is None:
            reasons.append("ACCESSION_NOT_IN_SUBMISSIONS")
        else:
            accepted, form, filed, primary = source
            expected = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{primary}"
            if receipt.get("source_ref") != expected:
                reasons.append("SEC_PRIMARY_DOCUMENT_URL_MISMATCH")
            if receipt.get("form") != form:
                reasons.append("SEC_FORM_MISMATCH")
            if retrieved < accepted or observed < accepted:
                reasons.append("SOURCE_OBSERVED_BEFORE_ACCEPTANCE")
            if accepted > clock:
                reasons.append("ACCEPTED_AFTER_AS_OF")
        if retrieved > clock:
            reasons.append("BODY_OBSERVED_AFTER_AS_OF")
        if observed > clock:
            reasons.append("SUBMISSIONS_OBSERVED_AFTER_AS_OF")
        rows.append({"accession": accession, "form": receipt.get("form"),
                     "source_ref": receipt.get("source_ref"), "body_sha256": digest,
                     "receipt_sha256": sha256(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                     "accepted_at": source[0].isoformat() if source else None,
                     "filing_date": source[2] if source else None,
                     "body_locally_observed_at": retrieved.isoformat(),
                     "submissions_locally_observed_at": observed.isoformat(),
                     "research_evidence_available_at": max(retrieved, observed).isoformat(),
                     "current_research_eligible": not reasons, "reasons": sorted(set(reasons)),
                     "first_public_dissemination_at": None,
                     "historical_provider_available_at": None,
                     "historical_pit_accepted": False})
    return {"schema": SCHEMA, "as_of": clock.isoformat(), "cik": cik,
            "submissions_sha256": sha256(submissions_raw).hexdigest(),
            "document_count": len(rows),
            "research_eligible_count": sum(r["current_research_eligible"] for r in rows),
            "historical_pit_accepted_count": 0, "full_model_scores_added": 0,
            "observation_clock_basis": "LOCAL_CACHE_RECEIPT_NOT_INDEPENDENT_PROVIDER_ATTESTATION",
            "canonical": False, "rows": rows}


def audit_cache(submissions_path: Path, receipt_path: Path, cache: Path, *, as_of: str) -> dict:
    documents = []
    for path in sorted(cache.glob("*.htm.receipt.json")):
        body_path = path.with_name(path.name.removesuffix(".receipt.json"))
        if path.is_symlink() or body_path.is_symlink():
            raise ValueError("SYMLINK_SOURCE_REJECTED")
        documents.append((body_path.read_bytes(), json.loads(path.read_text(encoding="utf8"))))
    if not documents:
        raise ValueError("NO_CACHED_DOCUMENTS")
    return audit_source_clocks(submissions_path.read_bytes(),
                              json.loads(receipt_path.read_text(encoding="utf8")),
                              documents, as_of=as_of)
