from __future__ import annotations

from dataclasses import dataclass


PHASE11_ACCEPTANCE_ITEMS = (
    "Cache layer",
    "DuckDB analytical path",
    "Parquet optimization",
    "Parallel scanning",
    "Deterministic results",
    "Worker-local database isolation",
)


@dataclass(frozen=True)
class OptimizationAcceptanceItem:
    name: str
    passed: bool
    evidence: str


def require_phase11_complete(items: list[OptimizationAcceptanceItem]) -> None:
    expected = set(PHASE11_ACCEPTANCE_ITEMS)
    actual = {item.name for item in items}
    if actual != expected:
        raise ValueError(
            f"Phase 11 acceptance matrix mismatch; missing={sorted(expected-actual)} "
            f"unexpected={sorted(actual-expected)}"
        )
    failed = [item for item in items if not item.passed]
    if failed:
        details = "; ".join(f"{item.name}: {item.evidence}" for item in failed)
        raise RuntimeError(f"Phase 11 acceptance is not complete: {details}")
