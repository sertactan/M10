from __future__ import annotations

from core.models.s153_v14_contracts import S153V14Input, S153V14Result


REQUIRED_CANONICAL_SOURCES = (
    "S15.3 V1.4 Canonical Specification",
    "V1.4 Factor / DNA Definitions",
    "V1.4 Router and Gate Specification",
    "Dual-Magnitude / Destination Specification",
    "Golden Test Cases",
)


class V14CanonicalSpecificationMissing(RuntimeError):
    """Raised when Phase 5 would otherwise have to invent model logic."""


class S153V14Model:
    model_id = "S15.3_V1.4"
    canonical_formula_version = "PENDING_AUTHORITATIVE_V1_4_BINDING"

    def analyze(self, data: S153V14Input) -> S153V14Result:
        if data.as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")

        missing = "; ".join(REQUIRED_CANONICAL_SOURCES)
        raise V14CanonicalSpecificationMissing(
            "S15.3 V1.4 is fail-closed because the authoritative Phase 5 "
            "specifications are not available in the project. Required: "
            f"{missing}. No formulas, weights, thresholds, routes, gates, "
            "penalties, probability mappings, destination rules, magnitude "
            "buckets, confidence rules, or missing-data treatment will be invented."
        )
