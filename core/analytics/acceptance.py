from __future__ import annotations

from dataclasses import dataclass


PHASE10_ACCEPTANCE_ITEMS = (
    "Score buckets",
    "Route performance",
    "False positives",
    "V1.2 vs V1.4 comparison",
    "READY-only evidence",
    "No invented bucket thresholds",
)


@dataclass(frozen=True)
class AnalyticsAcceptanceItem:
    name: str
    passed: bool
    evidence: str


def require_phase10_complete(items: list[AnalyticsAcceptanceItem]) -> None:
    expected = set(PHASE10_ACCEPTANCE_ITEMS)
    actual = {item.name for item in items}
    if actual != expected:
        raise ValueError(
            f"Phase 10 acceptance matrix mismatch; missing={sorted(expected-actual)} "
            f"unexpected={sorted(actual-expected)}"
        )
    failed = [item for item in items if not item.passed]
    if failed:
        details = "; ".join(f"{item.name}: {item.evidence}" for item in failed)
        raise RuntimeError(f"Phase 10 acceptance is not complete: {details}")
