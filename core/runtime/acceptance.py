from __future__ import annotations

from dataclasses import dataclass


PHASE12_ACCEPTANCE_ITEMS = (
    "Windows executable build",
    "Windows installer build",
    "Rotating logging",
    "Global error handling",
    "Persistent settings",
    "Update manifest system",
    "Writable production data path",
)


@dataclass(frozen=True)
class ProductionAcceptanceItem:
    name: str
    passed: bool
    evidence: str


def require_phase12_complete(items: list[ProductionAcceptanceItem]) -> None:
    expected = set(PHASE12_ACCEPTANCE_ITEMS)
    actual = {item.name for item in items}
    if actual != expected:
        raise ValueError(
            f"Phase 12 acceptance matrix mismatch; missing={sorted(expected-actual)} "
            f"unexpected={sorted(actual-expected)}"
        )
    failed = [item for item in items if not item.passed]
    if failed:
        details = "; ".join(f"{item.name}: {item.evidence}" for item in failed)
        raise RuntimeError(f"Phase 12 acceptance is not complete: {details}")
