"""Load offline SEC evidence bundles and check bodies before trusting locators.

The caller supplies source bytes and accession details. There is deliberately
no unattended SEC crawl, no companyfacts concepts guessed to be absent zeros.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .contracts import validate_source


def load_evidence_packet(path: str | Path) -> dict:
    path = Path(path)
    if path.suffix.lower() != ".json" or not path.is_file():
        raise ValueError("A local evidence JSON packet is required")
    packet = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(packet, dict) or not packet.get("ticker") or not packet.get("cik"):
        raise ValueError("Evidence packet must include ticker and CIK")
    if not isinstance(packet.get("rows", []), list):
        raise ValueError("Evidence rows must be a list")
    packet["_packet_path"] = str(path.resolve())
    return packet


def verify_source_rows(packet: dict) -> tuple[list[dict], list[dict]]:
    """Only local-byte-verified SEC facts can become SOURCE_EXACT.

    Body paths are resolved relative to packet, then SHA and literal excerpt
    are checked. Source locator is recorded as a reproducible character offset.
    A caller's unchecked body_hash_checked flag never counts as proof.
    """
    accepted, rejected = [], []
    base = Path(packet.get("_packet_path", ".")).parent.resolve()
    for input_row in packet.get("rows", []):
        row = dict(input_row)
        row["body_hash_checked"] = False
        row.setdefault("reported_line", None)
        row.setdefault("scale", None)
        row.setdefault("currency", row.get("unit"))
        row.setdefault("historical_provider_available_at_verified", False)
        row.setdefault("ai_accounting_rationale", None)
        row.setdefault("alternative_interpretations", [])
        row.setdefault("missing_information", [])
        row.setdefault("reviewer_actor_type", "DETERMINISTIC_SOURCE_VALIDATOR")
        row.setdefault("model_version", "PERSONAL_RESEARCH_V1")
        reasons = []
        if row.get("evidence_class") == "SOURCE_EXACT":
            body = row.get("local_body")
            if not body:
                reasons.append("LOCAL_BODY_NOT_PROVIDED")
            else:
                file = Path(body)
                file = file if file.is_absolute() else base / file
                if not file.is_file() or file.is_symlink():
                    reasons.append("LOCAL_BODY_MISSING")
                else:
                    raw = file.read_bytes()
                    actual = hashlib.sha256(raw).hexdigest()
                    if actual != str(row.get("source_sha256", "")).lower():
                        reasons.append("SOURCE_BODY_SHA_MISMATCH")
                    else:
                        excerpt = row.get("source_excerpt")
                        if not isinstance(excerpt, str) or not excerpt.strip():
                            reasons.append("EXACT_EXCERPT_REQUIRED")
                        elif excerpt.encode("utf-8") not in raw:
                            reasons.append("SOURCE_EXCERPT_NOT_IN_BODY")
                        elif str(row.get("value", "")).replace(",", "") not in (
                                excerpt.replace(",", "").replace(" ", "")):
                            # A correct hash with an unrelated real paragraph
                            # cannot authenticate a fabricated numeric value.
                            reasons.append("AMOUNT_NOT_IN_SOURCE_EXCERPT")
                        else:
                            position = raw.index(excerpt.encode("utf-8"))
                            row["source_locator"] = "byte:" + str(position)
                            row["body_hash_checked"] = True
        reasons.extend(validate_source(row, ticker=packet["ticker"]))
        if reasons:
            rejected.append({"metric": row.get("metric"), "reason": sorted(set(reasons)),
                             "accession": row.get("accession")})
        else:
            accepted.append(row)
    return accepted, rejected
