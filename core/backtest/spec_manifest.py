from __future__ import annotations

from dataclasses import dataclass


REQUIRED_BACKTEST_SOURCES = (
    "Historical Backtest Specification",
    "Point-in-Time Controls Specification",
    "Corporate Action Adjustment Specification",
    "Trading Calendar Specification",
    "Benchmark Specification",
    "Golden Backtest Test Cases",
)

# Source coverage actually available in the project/library at Phase 6 start.
# Do not upgrade PARTIAL to BOUND without the authoritative artifact.
SOURCE_COVERAGE = {
    "Historical Backtest Specification": "BOUND: Meridyen_10X_Historical_Dataset_Matched_Control_Spec_v1.0.md",
    "Point-in-Time Controls Specification": "BOUND: matched-control spec + master prompt PIT rules",
    "Corporate Action Adjustment Specification": "PARTIAL: matched-control spec defines censoring/terminal-value audit only",
    "Trading Calendar Specification": "PARTIAL: matched-control spec defines anchor_session and next-252-session semantics",
    "Benchmark Specification": "MISSING",
    "Golden Backtest Test Cases": "MISSING",
}


@dataclass(frozen=True)
class Phase6SpecificationBinding:
    historical_backtest_specification: str | None = None
    pit_controls_specification: str | None = None
    corporate_action_adjustment_specification: str | None = None
    trading_calendar_specification: str | None = None
    benchmark_specification: str | None = None
    golden_backtest_test_cases: str | None = None

    def missing(self) -> tuple[str, ...]:
        values = (
            self.historical_backtest_specification,
            self.pit_controls_specification,
            self.corporate_action_adjustment_specification,
            self.trading_calendar_specification,
            self.benchmark_specification,
            self.golden_backtest_test_cases,
        )
        return tuple(
            name
            for name, value in zip(REQUIRED_BACKTEST_SOURCES, values, strict=True)
            if not value
        )

    @property
    def complete(self) -> bool:
        return not self.missing()
