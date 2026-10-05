from __future__ import annotations

from dataclasses import dataclass


PHASE7_ACCEPTANCE_ITEMS = (
    "Current US scan",
    "Historical US scan",
    "NASDAQ coverage",
    "NYSE coverage",
    "AMEX coverage",
    "V1.2 scoring",
    "V1.4 scoring",
    "PIT filtering",
    "Historical universe",
    "Delisted handling",
    "Sort",
    "Filter",
    "Export",
    "10,000+ securities batch scan",
    "UI remains responsive",
)


@dataclass(frozen=True)
class AcceptanceItem:
    name: str
    passed: bool
    evidence: str


def require_all_pass(items: list[AcceptanceItem]) -> None:
    expected = set(PHASE7_ACCEPTANCE_ITEMS)
    actual = {item.name for item in items}
    if actual != expected:
        raise ValueError(
            f"Acceptance matrix mismatch; missing={sorted(expected-actual)} "
            f"unexpected={sorted(actual-expected)}"
        )
    failed = [item for item in items if not item.passed]
    if failed:
        details = "; ".join(f"{item.name}: {item.evidence}" for item in failed)
        raise RuntimeError(f"Phase 7 acceptance is not complete: {details}")
