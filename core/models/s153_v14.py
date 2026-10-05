from __future__ import annotations

from core.models.s153_v14_contracts import S153V14Input, S153V14Result
from core.models.s153_v14_spec_manifest import (
    FORBIDDEN_TO_INVENT_OR_MODIFY,
    REQUIRED_CANONICAL_SOURCES,
    V14SpecificationBinding,
)


class V14CanonicalSpecificationMissing(RuntimeError):
    """Raised when Phase 5 would otherwise have to invent model logic."""


class S153V14Model:
    model_id = "S15.3_V1.4"
    canonical_formula_version = "PENDING_AUTHORITATIVE_V1_4_BINDING"

    def __init__(self, binding: V14SpecificationBinding | None = None) -> None:
        self.binding = binding or V14SpecificationBinding()

    def analyze(self, data: S153V14Input) -> S153V14Result:
        if data.as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")

        missing = self.binding.missing()
        if missing:
            forbidden = ", ".join(FORBIDDEN_TO_INVENT_OR_MODIFY)
            raise V14CanonicalSpecificationMissing(
                "S15.3 V1.4 is fail-closed because authoritative Phase 5 "
                f"specifications are missing: {'; '.join(missing)}. "
                f"Forbidden to invent or modify: {forbidden}."
            )

        # Reaching this point means the binding manifest is complete, but the
        # executable canonical formulas must still be implemented from those
        # exact artifacts and locked by Golden Test Cases before activation.
        raise V14CanonicalSpecificationMissing(
            "S15.3 V1.4 canonical artifacts are declared, but executable "
            "formula binding is not implemented yet. Activation remains blocked "
            "until the exact formulas and Golden Test Cases are encoded."
        )
