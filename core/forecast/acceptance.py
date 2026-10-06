from __future__ import annotations

from dataclasses import dataclass


PHASE8_ACCEPTANCE_ITEMS = (
    "Current-date mode",
    "12M horizon",
    "V1.2 canonical scoring",
    "V1.4 canonical scoring",
    "Market Prevalence calibration",
    "Walk-forward audit",
    "Leakage audit",
    "Survivorship audit",
    "Calibration cutoff firewall",
    "Probability bounds",
    "Probability monotonicity",
    "Scenario ordering",
    "Explicit forecast disclosure",
    "Calibration evidence hash",
    "Data snapshot hash",
    "Model config hash",
    "Deterministic reproducibility",
)


@dataclass(frozen=True)
class ForecastAcceptanceItem:
    name: str
    passed: bool
    evidence: str


def require_phase8_complete(items: list[ForecastAcceptanceItem]) -> None:
    expected = set(PHASE8_ACCEPTANCE_ITEMS)
    actual = {item.name for item in items}
    if actual != expected:
        raise ValueError(
            f"Phase 8 acceptance matrix mismatch; missing={sorted(expected-actual)} "
            f"unexpected={sorted(actual-expected)}"
        )
    failed = [item for item in items if not item.passed]
    if failed:
        details = "; ".join(f"{item.name}: {item.evidence}" for item in failed)
        raise RuntimeError(f"Phase 8 acceptance is not complete: {details}")
