from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from core.backtest.wf5_replay import WF5WholeMarketReplay
from core.backtest.wf6_walk_forward import WF6WalkForwardEngine
from core.backtest.wf7_validation import WF7ValidationCalibrationEngine
from core.backtest.wf8_activation import WF8ProductionActivationService
from core.backtest.wf8_hardening import WF8ProductionHardeningAuditor
from core.backtest.wf8_reproducibility import WF8ReproducibilityManifestService
from core.research.walkforward_readiness import WalkForwardReadinessAuditor


@dataclass(frozen=True)
class EvidencePreflight:
    requested_start: date
    requested_end: date
    snapshot_dates: int
    exact_pit_dates: int
    dates_with_backtest_price_coverage: int
    blocked_dates: tuple[str, ...]
    status: str


@dataclass(frozen=True)
class ProductionEvidenceChainReport:
    status: str
    preflight: EvidencePreflight
    wf5_run_id: str | None = None
    wf6_run_id: str | None = None
    wf7_run_id: str | None = None
    hardening_id: str | None = None
    manifest_id: str | None = None
    activation_id: str | None = None
    details: dict[str, Any] | None = None


class ProductionEvidenceChainBlocked(RuntimeError):
    pass


class ProductionEvidenceChain:
    """One-command production evidence chain.

    This orchestrator never weakens fail-closed rules. Historical PIT universe
    and canonical BACKTEST/BACKTEST_ADJUSTED price evidence must already exist.
    """

    def __init__(self, app) -> None:
        self.app = app
        self.readiness = WalkForwardReadinessAuditor(app.sqlite)

    def preflight(self, *, start_date: date, end_date: date) -> EvidencePreflight:
        dates = [
            d for d in self.readiness.available_snapshot_dates()
            if start_date <= d <= end_date
        ]
        rows = self.readiness.audit_many(dates)

        exact = sum(1 for row in rows if row.exact_pit_universe)
        price_ready = sum(
            1
            for row in rows
            if row.universe_members > 0 and row.price_covered > 0
        )

        blockers: list[str] = []
        if not rows:
            blockers.append("NO_PIT_SNAPSHOT_DATES_IN_REQUESTED_WINDOW")
        for row in rows:
            if not row.exact_pit_universe:
                blockers.append(f"{row.as_of_date}:UNIVERSE_NOT_EXACT_PIT")
            if row.universe_members <= 0:
                blockers.append(f"{row.as_of_date}:EMPTY_UNIVERSE")
            elif row.price_covered <= 0:
                blockers.append(f"{row.as_of_date}:NO_CANONICAL_BACKTEST_PRICE_COVERAGE")

        return EvidencePreflight(
            requested_start=start_date,
            requested_end=end_date,
            snapshot_dates=len(rows),
            exact_pit_dates=exact,
            dates_with_backtest_price_coverage=price_ready,
            blocked_dates=tuple(blockers),
            status="READY" if not blockers else "BLOCKED",
        )

    def run(
        self,
        *,
        start_date: date,
        end_date: date,
        code_identity: str,
        reference_start_year: int = 2013,
        first_test_year: int = 2018,
        last_test_year: int = 2024,
        activate: bool = False,
    ) -> ProductionEvidenceChainReport:
        preflight = self.preflight(start_date=start_date, end_date=end_date)
        if preflight.status != "READY":
            return ProductionEvidenceChainReport(
                status="BLOCKED_PREFLIGHT",
                preflight=preflight,
                details={
                    "next_action": (
                        "Populate exact PIT historical universe snapshots and "
                        "canonical BACKTEST/BACKTEST_ADJUSTED price evidence."
                    )
                },
            )

        wf5 = WF5WholeMarketReplay(self.app).run_range(
            start_date=start_date,
            end_date=end_date,
        )
        if wf5.status != "COMPLETE":
            return ProductionEvidenceChainReport(
                status="BLOCKED_WF5",
                preflight=preflight,
                wf5_run_id=wf5.run_id,
                details={"wf5": asdict(wf5)},
            )

        wf6 = WF6WalkForwardEngine(self.app.sqlite).run(
            source_wf5_run_id=wf5.run_id,
            reference_start_year=reference_start_year,
            first_test_year=first_test_year,
            last_test_year=last_test_year,
        )
        if wf6.status != "COMPLETE":
            return ProductionEvidenceChainReport(
                status="BLOCKED_WF6",
                preflight=preflight,
                wf5_run_id=wf5.run_id,
                wf6_run_id=wf6.run_id,
                details={"wf5": asdict(wf5), "wf6": asdict(wf6)},
            )

        wf7_engine = WF7ValidationCalibrationEngine(self.app.sqlite)
        wf7_run_id = wf7_engine.run(wf6_run_id=wf6.run_id)

        hardening = WF8ProductionHardeningAuditor(self.app.sqlite).audit(
            wf7_run_id=wf7_run_id,
            persist=True,
        )
        if hardening.status != "PRODUCTION_EVIDENCE_READY":
            return ProductionEvidenceChainReport(
                status="BLOCKED_WF8",
                preflight=preflight,
                wf5_run_id=wf5.run_id,
                wf6_run_id=wf6.run_id,
                wf7_run_id=wf7_run_id,
                hardening_id=hardening.hardening_id,
                details={
                    "wf5": asdict(wf5),
                    "wf6": asdict(wf6),
                    "hardening": asdict(hardening),
                },
            )

        manifest = WF8ReproducibilityManifestService(self.app.sqlite).create(
            hardening_id=hardening.hardening_id,
            code_identity=code_identity,
        )

        activation_id = None
        if activate:
            activation = WF8ProductionActivationService(self.app.sqlite).activate(
                manifest_id=manifest.manifest_id,
                model_version="S15.3_V1.4.1",
                reason="production evidence orchestrator activation",
            )
            activation_id = activation.activation_id

        return ProductionEvidenceChainReport(
            status="PRODUCTION_ACTIVE" if activate else "PRODUCTION_EVIDENCE_READY",
            preflight=preflight,
            wf5_run_id=wf5.run_id,
            wf6_run_id=wf6.run_id,
            wf7_run_id=wf7_run_id,
            hardening_id=hardening.hardening_id,
            manifest_id=manifest.manifest_id,
            activation_id=activation_id,
            details={
                "wf5": asdict(wf5),
                "wf6": asdict(wf6),
                "hardening": asdict(hardening),
                "manifest_chain_hash": manifest.chain_hash,
            },
        )
