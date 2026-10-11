"""Offline evidence gates for historical SEC observations and their revisions.

This module validates an evidence envelope, not the truth of a provider's
attestation. A present-day SEC response cannot establish historical arrival.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re


ACCESSION = re.compile(r"\d{10}-\d{2}-\d{6}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")


def clock(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError("INVALID_TIMESTAMP") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("TIMESTAMP_OFFSET_REQUIRED")
    return parsed.astimezone(timezone.utc)


def audit_version(row: dict, *, as_of: str, source_bytes: bytes | None = None) -> dict:
    """Admit only a source version actually available by the decision clock.

    Required clocks have different jobs: SEC acceptance is a lower bound;
    independent public dissemination is the first public event; historical
    provider capture is the first demonstrated feature availability. The local
    observation time may be later and can never be backdated to acceptance.
    """
    if not isinstance(row, dict) or not ACCESSION.fullmatch(str(row.get("accession", ""))):
        raise ValueError("ACCESSION_REQUIRED")
    decision = clock(as_of)
    if decision is None:
        raise ValueError("AS_OF_REQUIRED")
    accepted = clock(row.get("accepted_at"))
    public = clock(row.get("first_public_at"))
    provider = clock(row.get("first_provider_available_at"))
    captured = clock(row.get("captured_at"))
    period_end = clock(row.get("period_end_at"))
    errors: list[str] = []
    if accepted is None:
        errors.append("SEC_ACCEPTANCE_MISSING")
    if public is None or row.get("public_time_basis") != "INDEPENDENT_SOURCE_CAPTURE":
        errors.append("FIRST_PUBLICATION_UNVERIFIED")
    if provider is None or row.get("provider_time_basis") != "HISTORICAL_CAPTURE_LOG":
        errors.append("HISTORICAL_PROVIDER_ARRIVAL_UNVERIFIED")
    if captured is None or row.get("capture_time_basis") != "CONTEMPORANEOUS_ARCHIVE":
        errors.append("CONTEMPORANEOUS_CAPTURE_UNVERIFIED")
    if period_end is None:
        errors.append("PERIOD_END_MISSING")
    if not row.get("issuer_mapping_source") or not row.get("issuer_mapping_valid_at_as_of"):
        errors.append("HISTORICAL_ISSUER_MAPPING_UNVERIFIED")
    if row.get("revision_kind") not in ("ORIGINAL", "AMENDMENT"):
        errors.append("REVISION_KIND_UNVERIFIED")
    if row.get("revision_kind") == "AMENDMENT" and not ACCESSION.fullmatch(str(row.get("amends_accession", ""))):
        errors.append("AMENDMENT_PARENT_UNVERIFIED")
    expected = row.get("source_sha256")
    if not isinstance(expected, str) or not SHA.fullmatch(expected):
        errors.append("SOURCE_HASH_MISSING")
    elif source_bytes is None or sha256(source_bytes).hexdigest() != expected:
        errors.append("SOURCE_BYTES_NOT_REPLAYED")
    if period_end and accepted and period_end > accepted:
        errors.append("PERIOD_AFTER_ACCEPTANCE")
    if accepted and public and public < accepted:
        errors.append("PUBLIC_BEFORE_SEC_ACCEPTANCE")
    if public and provider and provider < public:
        errors.append("PROVIDER_BEFORE_PUBLICATION")
    if provider and captured and captured < provider:
        errors.append("CAPTURE_BEFORE_PROVIDER_ARRIVAL")
    if accepted and accepted > decision:
        errors.append("SEC_ACCEPTANCE_AFTER_AS_OF")
    if provider and provider > decision:
        errors.append("PROVIDER_ARRIVAL_AFTER_AS_OF")
    if captured and captured > decision:
        errors.append("CAPTURE_AFTER_AS_OF")
    return {
        "accession": row["accession"], "as_of": decision.isoformat(),
        "eligible": not errors, "reasons": sorted(set(errors)),
        "accepted_at": accepted.isoformat() if accepted else None,
        "first_public_at": public.isoformat() if public else None,
        "first_provider_available_at": provider.isoformat() if provider else None,
        "captured_at": captured.isoformat() if captured else None,
    }


def select_as_of_version(rows: list[dict], *, as_of: str, source_bytes: dict[str, bytes]) -> dict:
    """Select latest evidenced eligible filing version; no future amendment leak."""
    if not rows:
        return {"selected_accession": None, "eligible": False, "reason": "NO_VERSIONS"}
    identities = {(r.get("cik"), r.get("concept"), r.get("period_end_at")) for r in rows}
    if len(identities) != 1 or None in next(iter(identities)):
        raise ValueError("REVISION_IDENTITY_MISMATCH")
    accessions = {r.get("accession") for r in rows}
    if len(accessions) != len(rows):
        raise ValueError("DUPLICATE_ACCESSION")
    original = [r for r in rows if r.get("revision_kind") == "ORIGINAL"]
    if len(original) != 1:
        raise ValueError("EXACTLY_ONE_ORIGINAL_REQUIRED")
    for row in rows:
        if row.get("revision_kind") == "AMENDMENT" and row.get("amends_accession") not in accessions:
            raise ValueError("AMENDMENT_PARENT_NOT_IN_CHAIN")
    reviewed = [audit_version(r, as_of=as_of, source_bytes=source_bytes.get(r["accession"])) for r in rows]
    eligible = [r for r in reviewed if r["eligible"]]
    selected = max(eligible, key=lambda r: (r["first_provider_available_at"], r["accepted_at"])) if eligible else None
    return {"selected_accession": selected["accession"] if selected else None,
            "eligible": selected is not None, "versions": reviewed}


def audit_sec_submissions(raw: bytes, receipt: dict, accessions: list[str], *, as_of: str) -> dict:
    """Replay exact real SEC Submissions bytes, while refusing to infer PIT."""
    if sha256(raw).hexdigest() != receipt.get("sha256") or len(raw) != receipt.get("bytes"):
        raise ValueError("SEC_RECEIPT_HASH_OR_LENGTH_MISMATCH")
    payload = json.loads(raw)
    if str(payload.get("cik", "")).zfill(10) != str(receipt.get("cik", "")).zfill(10):
        raise ValueError("SEC_CIK_MISMATCH")
    recent = payload["filings"]["recent"]
    keys = ("accessionNumber", "acceptanceDateTime", "form", "filingDate", "reportDate")
    if len({len(recent[k]) for k in keys}) != 1:
        raise ValueError("SEC_PARALLEL_ARRAYS_INVALID")
    index = {accession: i for i, accession in enumerate(recent["accessionNumber"])}
    if len(index) != len(recent["accessionNumber"]):
        raise ValueError("SEC_DUPLICATE_ACCESSION")
    rows = []
    for accession in accessions:
        if accession not in index:
            raise ValueError("SEC_ACCESSION_NOT_IN_RESPONSE")
        i = index[accession]
        row = {"accession": accession, "accepted_at": recent["acceptanceDateTime"][i],
               "form": recent["form"][i], "filing_date": recent["filingDate"][i],
               "period_end_at": recent["reportDate"][i] + "T23:59:59+00:00" if recent["reportDate"][i] else None,
               "first_public_at": None, "first_provider_available_at": None,
               "captured_at": receipt.get("checked_at"),
               "source_sha256": receipt["sha256"], "cik": receipt["cik"],
               "revision_kind": "AMENDMENT" if str(recent["form"][i]).endswith("/A") else "ORIGINAL"}
        review = audit_version(row, as_of=as_of, source_bytes=raw)
        rows.append({"form": row["form"], "filing_date": row["filing_date"], **review})
    return {"source_sha256": receipt["sha256"], "cik": receipt["cik"],
            "source_retrieved_at": receipt.get("checked_at"), "rows": rows,
            "accepted_pit_versions": sum(row["eligible"] for row in rows),
            "canonical_s16c_features": 0, "s16ea_verified_alerts": 0}
