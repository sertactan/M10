from __future__ import annotations

from dataclasses import dataclass


MASTER_PROMPT_FILENAME = "S15.3_Desktop_Stock_Analysis_Backtest_Master_Prompt(1).md"
MASTER_PROMPT_SHA256 = "9c90dea8b44a22a6d8f006a1040eb235a4ba78145fa3fd5a8c9c94b607c94e74"

REQUIRED_CANONICAL_SOURCES = (
    "S15.3 V1.4 Canonical Specification",
    "V1.4 Factor / DNA Definitions",
    "V1.4 Router and Gate Specification",
    "Dual-Magnitude / Destination Specification",
    "Golden Test Cases",
)

FORBIDDEN_TO_INVENT_OR_MODIFY = (
    "formulas",
    "factor weights",
    "thresholds",
    "routes",
    "gates",
    "penalties",
    "probability mappings",
    "destination rules",
    "magnitude buckets",
    "confidence rules",
    "missing-data treatment",
)


@dataclass(frozen=True)
class V14SpecificationBinding:
    canonical_specification: str | None = None
    factor_dna_definitions: str | None = None
    router_gate_specification: str | None = None
    dual_magnitude_destination_specification: str | None = None
    golden_test_cases: str | None = None

    def missing(self) -> tuple[str, ...]:
        values = (
            self.canonical_specification,
            self.factor_dna_definitions,
            self.router_gate_specification,
            self.dual_magnitude_destination_specification,
            self.golden_test_cases,
        )
        return tuple(
            name
            for name, value in zip(REQUIRED_CANONICAL_SOURCES, values, strict=True)
            if not value
        )

    @property
    def complete(self) -> bool:
        return not self.missing()
