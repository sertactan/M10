from __future__ import annotations

from dataclasses import dataclass


PHASE9_ACCEPTANCE_ITEMS = (
    "Desktop shell",
    "Global header",
    "V1.2 tab",
    "V1.4 tab",
    "Compare tab",
    "Canonical stock header",
    "Phase 6 backtest card",
    "Phase 8 forecast card",
    "Historical price chart",
    "Analysis-date marker",
    "Market Scanner dialog",
    "Scanner sort/filter/export",
    "Background analysis worker",
    "Background scanner worker",
    "Loading/progress/error states",
    "Responsive minimum layout",
    "No mock production results",
    "V1.4 canonical execution",
)


@dataclass(frozen=True)
class UIAcceptanceItem:
    name: str
    passed: bool
    evidence: str


def require_phase9_complete(items: list[UIAcceptanceItem]) -> None:
    expected = set(PHASE9_ACCEPTANCE_ITEMS)
    actual = {item.name for item in items}
    if actual != expected:
        raise ValueError(
            f"Phase 9 acceptance matrix mismatch; missing={sorted(expected-actual)} "
            f"unexpected={sorted(actual-expected)}"
        )
    failed = [item for item in items if not item.passed]
    if failed:
        details = "; ".join(f"{item.name}: {item.evidence}" for item in failed)
        raise RuntimeError(f"Phase 9 acceptance is not complete: {details}")
