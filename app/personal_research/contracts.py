"""Strict evidence metadata and unambiguous personal analysis labels."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

EVIDENCE_CLASSES = frozenset({
    "SOURCE_EXACT", "SOURCE_DERIVED", "AI_ACCOUNTING_INTERPRETATION",
    "SCENARIO_ASSUMPTION", "UNRESOLVED", "EXPERT_REVIEWED",
})
QUALITY_LABELS = frozenset({
    "EXACT_SOURCE_BACKED", "DERIVED_FROM_EXACT_SOURCES", "AI_INTERPRETED",
    "SCENARIO_ONLY", "PARTIAL_INPUTS", "UNRESOLVED", "EXPERT_REVIEWED",
})
NUMERIC_TYPES = frozenset({"EXACT", "SCENARIO", "UNQUANTIFIABLE"})
HASH = re.compile(r"[0-9a-f]{64}\Z", re.I)
ACCESSION = re.compile(r"\d{10}-\d\d-\d{6}\Z")


def digest(data) -> str:
    """Stable SHA over reproducible JSON; rejects NaN and infinity."""
    return hashlib.sha256(json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False, default=str,
    ).encode("utf-8")).hexdigest()


def stamp(value):
    if not isinstance(value, str):
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except ValueError:
        return None


def validate_source(row: dict, *, ticker: str | None = None) -> list[str]:
    """No valid-looking URL/hash is presented as proof of source bytes."""
    problems = []
    if not isinstance(row, dict):
        return ["ROW_NOT_MAPPING"]
    fields = ("ticker", "cik", "period_end", "accession", "form_type",
              "source_ref", "source_locator", "source_sha256", "accepted_at",
              "captured_at", "unit", "evidence_class")
    problems.extend("MISSING_" + field.upper() for field in fields if not row.get(field))
    if ticker and row.get("ticker") != ticker:
        problems.append("ISSUER_MISMATCH")
    if row.get("evidence_class") not in EVIDENCE_CLASSES:
        problems.append("INVALID_EVIDENCE_CLASS")
    if not HASH.fullmatch(str(row.get("source_sha256", ""))):
        problems.append("INVALID_SOURCE_SHA")
    if not ACCESSION.fullmatch(str(row.get("accession", ""))):
        problems.append("INVALID_ACCESSION")
    try:
        u = urlsplit(str(row.get("source_ref", "")))
        if not (u.scheme == "https" and u.netloc.lower() in
                {"sec.gov", "www.sec.gov", "data.sec.gov"}):
            problems.append("NOT_OFFICIAL_SEC_URL")
    except ValueError:
        problems.append("INVALID_SOURCE_URL")
    accepted, captured = stamp(row.get("accepted_at")), stamp(row.get("captured_at"))
    if not accepted or not captured or captured < accepted:
        problems.append("INVALID_SOURCE_TIMELINE")
    if row.get("historical_provider_available_at_verified") is True:
        if not stamp(row.get("provider_available_at")):
            problems.append("PIT_PROOF_TIME_MISSING")
    if row.get("evidence_class") == "SOURCE_EXACT" and row.get("body_hash_checked") is not True:
        problems.append("SOURCE_BODY_HASH_NOT_CHECKED")
    return problems


def personal_result(model: str, *, score=None, numeric_result_type="UNQUANTIFIABLE",
                    original_status="N/A", missing=(), components=None,
                    evidence=None, status=None) -> dict:
    if numeric_result_type not in NUMERIC_TYPES:
        raise ValueError("Unsupported result type")
    if score is None and numeric_result_type != "UNQUANTIFIABLE":
        raise ValueError("Numeric type demands a score")
    if score is not None and numeric_result_type == "UNQUANTIFIABLE":
        raise ValueError("Unquantifiable cannot have a score")
    payload = {
        "model": model, "status": status or ("SCENARIO_ONLY" if score is not None
                                              and numeric_result_type == "SCENARIO"
                                              else "EXACT_SOURCE_BACKED" if score is not None
                                              else "PARTIAL_INPUTS"),
        "score": score, "numeric_result_type": numeric_result_type,
        "original_status": original_status, "original_score": None,
        "missing": sorted(set(missing)), "components": components or {},
        "evidence": evidence or [], "method_version": "PERSONAL_RESEARCH_V1",
        "canonical_accepted": False, "historical_pit_accepted": False,
        "scope": "PERSONAL_AI_ASSESSED_RESEARCH_ONLY",
    }
    payload["receipt_sha256"] = digest(payload)
    return payload
