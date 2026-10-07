from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from core.backtest.wf5_schedule import monthly_snapshot_dates
from core.backtest.wf5_replay import WF5WholeMarketReplay
from core.backtest.wf6_walk_forward import WF6WalkForwardEngine
from core.backtest.wf7_validation import WF7ValidationCalibrationEngine
from core.backtest.wf8_hardening import WF8ProductionHardeningAuditor
from core.backtest.wf8_reproducibility import WF8ReproducibilityManifestService
from core.backtest.wf8_activation import WF8ProductionActivationService
from core.research.walkforward_readiness import WalkForwardReadinessAuditor


@dataclass(frozen=True)
class WF9PreflightReport:
    start_date: date
    end_date: date
    requested_snapshot_dates: int
    existing_snapshot_dates: int
    exact_pit_dates: int
    any_adjusted_price_dates: int
    total_universe_observations: int
    total_price_covered: int
    blockers: tuple[str,...]
    warnings: tuple[str,...]

    @property
    def ready(self) -> bool:
        return not self.blockers


@dataclass(frozen=True)
class WF9ExecutionReport:
    status: str
    preflight: WF9PreflightReport
    wf5_run_id: str | None = None
    wf6_run_id: str | None = None
    wf7_run_id: str | None = None
    hardening_id: str | None = None
    manifest_id: str | None = None
    activation_id: str | None = None


class WF9ExecutionBlocked(RuntimeError):
    pass


class WF9FullHistoricalExecution:
    """End-to-end evidence generation on one local canonical PIT database."""

    def __init__(self, app) -> None:
        self.app=app
        self.readiness=WalkForwardReadinessAuditor(app.sqlite)

    def preflight(self, *, start_date: date, end_date: date) -> WF9PreflightReport:
        requested=monthly_snapshot_dates(start_date,end_date)
        available=set(self.readiness.available_snapshot_dates())
        rows=[
            self.readiness.audit(d)
            for d in requested
            if d in available
        ]

        exact=sum(row.exact_pit_universe for row in rows)
        any_price=sum(row.price_covered > 0 for row in rows)
        total_universe=sum(row.universe_members for row in rows)
        total_price=sum(row.price_covered for row in rows)

        blockers: list[str]=[]
        warnings: list[str]=[]
        if len(rows) != len(requested):
            blockers.append(
                f"MISSING_PIT_SNAPSHOT_DATES:{len(rows)}/{len(requested)}"
            )
        if exact != len(requested):
            blockers.append(
                f"NON_EXACT_PIT_DATES:{exact}/{len(requested)}"
            )
        if any_price == 0:
            blockers.append("NO_CANONICAL_ADJUSTED_BACKTEST_PRICE")
        elif total_price < total_universe:
            warnings.append(
                f"PARTIAL_ADJUSTED_PRICE_COVERAGE:{total_price}/{total_universe}"
            )

        return WF9PreflightReport(
            start_date=start_date,
            end_date=end_date,
            requested_snapshot_dates=len(requested),
            existing_snapshot_dates=len(rows),
            exact_pit_dates=exact,
            any_adjusted_price_dates=any_price,
            total_universe_observations=total_universe,
            total_price_covered=total_price,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
        )

    def run(
        self,
        *,
        start_date: date,
        end_date: date,
        code_identity: str,
        first_test_year: int=2018,
        last_test_year: int=2024,
    ) -> WF9ExecutionReport:
        preflight=self.preflight(start_date=start_date,end_date=end_date)
        if not preflight.ready:
            return WF9ExecutionReport(
                status="PREFLIGHT_BLOCKED",
                preflight=preflight,
            )

        wf5=WF5WholeMarketReplay(self.app).run_range(
            start_date=start_date,
            end_date=end_date,
        )
        if wf5.status != "COMPLETE":
            return WF9ExecutionReport(
                status=f"WF5_{wf5.status}",
                preflight=preflight,
                wf5_run_id=wf5.run_id,
            )

        wf6=WF6WalkForwardEngine(self.app.sqlite).run(
            source_wf5_run_id=wf5.run_id,
            reference_start_year=start_date.year,
            first_test_year=first_test_year,
            last_test_year=last_test_year,
        )
        if wf6.status != "COMPLETE":
            return WF9ExecutionReport(
                status=f"WF6_{wf6.status}",
                preflight=preflight,
                wf5_run_id=wf5.run_id,
                wf6_run_id=wf6.run_id,
            )

        wf7_engine=WF7ValidationCalibrationEngine(self.app.sqlite)
        wf7_run_id=wf7_engine.run(wf6_run_id=wf6.run_id)

        hardening=WF8ProductionHardeningAuditor(self.app.sqlite).audit(
            wf7_run_id=wf7_run_id,
            persist=True,
        )
        if hardening.status != "PRODUCTION_EVIDENCE_READY":
            return WF9ExecutionReport(
                status="WF8_PRODUCTION_BLOCKED",
                preflight=preflight,
                wf5_run_id=wf5.run_id,
                wf6_run_id=wf6.run_id,
                wf7_run_id=wf7_run_id,
                hardening_id=hardening.hardening_id,
            )

        manifest=WF8ReproducibilityManifestService(self.app.sqlite).create(
            hardening_id=hardening.hardening_id,
            code_identity=code_identity,
        )
        activation=WF8ProductionActivationService(self.app.sqlite).activate(
            manifest_id=manifest.manifest_id,
            model_version="S15.3_V1.4.1",
            reason="WF9 full historical evidence promotion",
        )
        return WF9ExecutionReport(
            status="COMPLETE_AND_ACTIVATED",
            preflight=preflight,
            wf5_run_id=wf5.run_id,
            wf6_run_id=wf6.run_id,
            wf7_run_id=wf7_run_id,
            hardening_id=hardening.hardening_id,
            manifest_id=manifest.manifest_id,
            activation_id=activation.activation_id,
        )
