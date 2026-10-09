"""Read-only M10 model interfaces; reject unproven or missing canonical inputs."""
from __future__ import annotations

from dataclasses import fields
from datetime import datetime
from typing import Any

from core.hermes_team.contracts import financial_result
from core.models.s16 import S16V1Model
from core.models.s16_contracts import S16Input

_METADATA = {"security_id", "ticker", "as_of", "route"}
REQUIRED_FEATURES = tuple(f.name for f in fields(S16Input) if f.name not in _METADATA)


def canonical_s16_from_verified_features(payload: dict[str, Any]) -> dict[str, Any]:
    """Only trust deterministic, externally verified PIT feature bundles.

    The caller must independently verify evidence references and PIT lineage.
    No LLM-originated feature value is admissible as canonical evidence.
    """
    if payload.get("feature_origin") != "M10_VERIFIED_PIT_PIPELINE":
        return financial_result(payload)
    if payload.get("canonical_evidence_verified") is not True:
        return financial_result(payload)
    features = payload.get("features")
    if not isinstance(features, dict) or any(k not in features or features[k] is None
                                            for k in REQUIRED_FEATURES):
        return financial_result({**payload, "canonical_evidence_verified": False})
    try:
        date = datetime.fromisoformat(str(payload["price_timestamp"]).replace("Z", "+00:00"))
        if date.tzinfo is None:
            raise ValueError("timezone required")
        contract = S16Input(security_id=str(payload["security_id"]),
                            ticker=str(payload["symbol"]), as_of=date,
                            **{k: features[k] for k in REQUIRED_FEATURES})
        result = S16V1Model().analyze(contract)
    except (ValueError, TypeError, KeyError, OverflowError):
        return financial_result({**payload, "canonical_evidence_verified": False})
    # This is the frozen genuine M10 formula, not an LLM estimate.
    return financial_result({**payload, "s16_c": result.explosive_score,
                             "canonical_evidence_verified": True})
