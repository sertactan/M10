from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timezone

from core.backtest.outcomes import CanonicalForwardOutcomeEngine
from core.backtest.wf5_schedule import monthly_snapshot_dates
from core.features.wf3_bulk import WF3WholeUniverseMaterializer
from core.features.wf3_peer_policy import market_cap_bucket
from core.historical.wf4_materializer import WF4HistoricalFeatureMaterializer
from core.historical.wf4_observation_builder import WF4HistoricalObservationBuilder
from core.models.s153_v12 import S153V12Model
from core.models.s153_v141 import S153V141Model
from core.research.walkforward_readiness import WalkForwardReadinessAuditor
from core.scanner.production import CanonicalDualModelScorer, RepositoryCandidateSource
from data.repositories.backtest_repository import (
    BacktestRepository,
    CanonicalBacktestPriceUnavailable,
)
from data.repositories.model_feature_repository import ModelFeatureRepository
from data.repositories.s153_historical_control_repository import S153HistoricalControlRepository
from data.repositories.security_repository import SecurityRepository
from data.storage.parquet_price_store import ParquetPriceStore


@dataclass(frozen=True)
class WF5ScorePhaseReport:
    run_id: str
    snapshot_date: date
    universe_count: int
    scored_count: int
    ready_count: int
    inconclusive_count: int
    error_count: int
    status: str


@dataclass(frozen=True)
class WF5OutcomePhaseReport:
    run_id: str
    snapshot_date: date
    observation_count: int
    ready_count: int
    censored_count: int
    error_count: int
    historical_controls_written: int
    status: str


@dataclass(frozen=True)
class WF5RunReport:
    run_id: str
    requested_dates: int
    score_complete_dates: int
    outcome_complete_dates: int
    blocked_dates: int
    status: str


def _replay_outcome_status(status: str) -> str:
    if status == "READY":
        return "READY"
    if status in {"PARTIAL", "CENSORED"}:
        return "CENSORED"
    return status


def _label_available_at(bars, outcome) -> datetime | None:
    """When the 252-session label first becomes knowable.

    Terminal-consideration early completion is not used by WF5 until a
    dedicated terminal-event source is wired into the replay.
    """
    if outcome.outcome_status != "READY" or outcome.anchor_session is None:
        return None
    forward=[bar for bar in bars if bar.trade_date > outcome.anchor_session][:252]
    if len(forward) < 252:
        return None
    return datetime.combine(forward[-1].trade_date,time.max,tzinfo=timezone.utc)


class WF5WholeMarketReplay:
    """Chronological PIT whole-market replay with a physical outcome firewall."""

    def __init__(self, app) -> None:
        self.app=app
        self.securities=SecurityRepository(app.sqlite)
        self.features=ModelFeatureRepository(app.sqlite)
        self.readiness=WalkForwardReadinessAuditor(app.sqlite)
        self.candidates=RepositoryCandidateSource(self.securities)
        self.scorer=CanonicalDualModelScorer(self.features)
        self.wf3=WF3WholeUniverseMaterializer(app)

        self.controls_repo=S153HistoricalControlRepository(app.sqlite)
        self.wf4=WF4HistoricalFeatureMaterializer(self.controls_repo,self.features)
        self.wf4_builder=WF4HistoricalObservationBuilder(self.controls_repo)

        parquet=ParquetPriceStore(
            app.resolve_data_path(app.app_config.database.parquet_root)
        )
        self.backtest=BacktestRepository(app.sqlite,parquet)
        self.outcomes=CanonicalForwardOutcomeEngine()

    def create_run(self, *, start_date: date, end_date: date, frequency: str="MONTHLY") -> str:
        if end_date < start_date:
            raise ValueError("end_date must be >= start_date")
        if frequency != "MONTHLY":
            raise ValueError("WF5 currently supports MONTHLY replay only")
        run_id=str(uuid.uuid4())
        now=datetime.now(timezone.utc).isoformat()
        self.app.sqlite.connection.execute(
            """
            INSERT INTO wf5_replay_runs
            (run_id,start_date,end_date,frequency,v12_version,v141_version,status,created_at)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                run_id,start_date.isoformat(),end_date.isoformat(),frequency,
                S153V12Model.canonical_formula_version,
                S153V141Model.canonical_formula_version,
                "ACTIVE",now,
            ),
        )
        self.app.sqlite.connection.commit()
        return run_id

    def _set_checkpoint(
        self,
        *,
        run_id: str,
        snapshot_date: date,
        phase: str,
        status: str,
        universe_count: int=0,
        scored_count: int=0,
        ready_count: int=0,
        inconclusive_count: int=0,
        censored_count: int=0,
        error_count: int=0,
        message: str | None=None,
        completed: bool=False,
    ) -> None:
        now=datetime.now(timezone.utc).isoformat()
        self.app.sqlite.connection.execute(
            """
            INSERT INTO wf5_replay_checkpoints
            (run_id,snapshot_date,phase,status,universe_count,scored_count,
             ready_count,inconclusive_count,censored_count,error_count,
             started_at,completed_at,message)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(run_id,snapshot_date,phase) DO UPDATE SET
                status=excluded.status,
                universe_count=excluded.universe_count,
                scored_count=excluded.scored_count,
                ready_count=excluded.ready_count,
                inconclusive_count=excluded.inconclusive_count,
                censored_count=excluded.censored_count,
                error_count=excluded.error_count,
                completed_at=excluded.completed_at,
                message=excluded.message
            """,
            (
                run_id,snapshot_date.isoformat(),phase,status,
                universe_count,scored_count,ready_count,inconclusive_count,
                censored_count,error_count,now,(now if completed else None),message,
            ),
        )
        self.app.sqlite.connection.commit()

    def _checkpoint_status(self, run_id: str, snapshot_date: date, phase: str) -> str | None:
        row=self.app.sqlite.connection.execute(
            """
            SELECT status FROM wf5_replay_checkpoints
            WHERE run_id=? AND snapshot_date=? AND phase=?
            """,
            (run_id,snapshot_date.isoformat(),phase),
        ).fetchone()
        return str(row["status"]) if row is not None else None

    def score_date(self, *, run_id: str, snapshot_date: date) -> WF5ScorePhaseReport:
        audit=self.readiness.audit(snapshot_date)
        if not audit.exact_pit_universe:
            self._set_checkpoint(
                run_id=run_id,snapshot_date=snapshot_date,phase="SCORE",
                status="BLOCKED_NON_PIT_UNIVERSE",
                universe_count=audit.universe_members,
                message="exact PIT universe required",completed=True,
            )
            return WF5ScorePhaseReport(
                run_id=run_id,snapshot_date=snapshot_date,
                universe_count=audit.universe_members,scored_count=0,
                ready_count=0,inconclusive_count=0,error_count=0,
                status="BLOCKED_NON_PIT_UNIVERSE",
            )

        self._set_checkpoint(
            run_id=run_id,snapshot_date=snapshot_date,phase="SCORE",
            status="RUNNING",universe_count=audit.universe_members,
        )

        # WF3 destination evidence is materialized from PIT inputs before any score.
        self.wf3.materialize_date(snapshot_date)

        as_of=datetime.combine(snapshot_date,time.max,tzinfo=timezone.utc)
        candidates=self.candidates.historical(as_of)

        # Pass 1: outcome-independent route/components used by WF4 historical controls.
        preliminary={}
        errors=0
        for candidate in candidates:
            try:
                preliminary[candidate.security_id]=self.scorer.score(candidate,as_of)
            except Exception:
                errors+=1

        same_month_rows=[]
        buckets={}
        for candidate in candidates:
            pair=preliminary.get(candidate.security_id)
            if pair is None:
                continue
            v12,_v141=pair
            rows=self.features.load_as_of(candidate.security_id,as_of)
            mc=rows.get("RAW_CURRENT_MARKET_CAP",{}).get("value")
            bucket=market_cap_bucket(float(mc)) if mc is not None else None
            buckets[candidate.security_id]=bucket
            same_month_rows.append({
                "security_id":candidate.security_id,
                "RB":v12.components.get("RB"),
                "route":v12.primary_route,
                "market_cap_bucket":bucket,
            })

        # Materialize H10/HMG5/HMG10/XR using only labels available by target as_of.
        for candidate in candidates:
            pair=preliminary.get(candidate.security_id)
            if pair is None:
                continue
            v12,_v141=pair
            self.wf4.materialize(
                security_id=candidate.security_id,
                as_of=as_of,
                primary_route=v12.primary_route,
                market_cap_bucket=buckets.get(candidate.security_id),
                components=dict(v12.components),
                same_month_rows=same_month_rows,
            )

        # Pass 2: final canonical score after historical controls are available.
        scored=ready=inconclusive=0
        for candidate in candidates:
            if candidate.security_id not in preliminary:
                continue
            try:
                v12,v141=self.scorer.score(candidate,as_of)
                scored+=1
                if v141.score is not None:
                    ready+=1
                else:
                    inconclusive+=1
                observation_id=str(uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{run_id}|{candidate.security_id}|{snapshot_date.isoformat()}",
                ))
                self.app.sqlite.connection.execute(
                    """
                    INSERT INTO wf5_replay_observations
                    (observation_id,run_id,security_id,ticker,as_of_date,primary_route,
                     v12_score,v12_status,v141_score,v141_status,score_created_at,outcome_status)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,'NOT_JOINED')
                    ON CONFLICT(observation_id) DO UPDATE SET
                        primary_route=excluded.primary_route,
                        v12_score=excluded.v12_score,
                        v12_status=excluded.v12_status,
                        v141_score=excluded.v141_score,
                        v141_status=excluded.v141_status,
                        score_created_at=excluded.score_created_at,
                        outcome_status=CASE
                            WHEN wf5_replay_observations.outcome_status='NOT_JOINED'
                            THEN 'NOT_JOINED'
                            ELSE wf5_replay_observations.outcome_status
                        END
                    """,
                    (
                        observation_id,run_id,candidate.security_id,candidate.ticker,
                        snapshot_date.isoformat(),v12.primary_route,
                        v12.score,v12.status,v141.score,v141.status,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
            except Exception:
                errors+=1

        self.app.sqlite.connection.commit()
        status="SCORE_COMPLETE" if errors == 0 else "SCORE_COMPLETE_WITH_ERRORS"
        self._set_checkpoint(
            run_id=run_id,snapshot_date=snapshot_date,phase="SCORE",
            status=status,universe_count=len(candidates),scored_count=scored,
            ready_count=ready,inconclusive_count=inconclusive,error_count=errors,
            completed=True,
        )
        return WF5ScorePhaseReport(
            run_id=run_id,snapshot_date=snapshot_date,
            universe_count=len(candidates),scored_count=scored,
            ready_count=ready,inconclusive_count=inconclusive,
            error_count=errors,status=status,
        )

    def _load_price_path(self, security_id: str, snapshot_date: date):
        last_error=None
        for purpose in ("BACKTEST_ADJUSTED","BACKTEST"):
            try:
                return self.backtest.load_canonical_price_path(
                    security_id=security_id,
                    anchor_date=snapshot_date,
                    purpose=purpose,
                )
            except CanonicalBacktestPriceUnavailable as exc:
                last_error=exc
        raise CanonicalBacktestPriceUnavailable(str(last_error or "price path unavailable"))

    def outcome_join_date(
        self,
        *,
        run_id: str,
        snapshot_date: date,
    ) -> WF5OutcomePhaseReport:
        score_status=self._checkpoint_status(run_id,snapshot_date,"SCORE")
        if score_status not in {"SCORE_COMPLETE","SCORE_COMPLETE_WITH_ERRORS"}:
            raise RuntimeError("WF5 OUTCOME_JOIN requires persisted SCORE phase first")

        rows=self.app.sqlite.connection.execute(
            """
            SELECT * FROM wf5_replay_observations
            WHERE run_id=? AND as_of_date=?
            ORDER BY security_id
            """,
            (run_id,snapshot_date.isoformat()),
        ).fetchall()
        self._set_checkpoint(
            run_id=run_id,snapshot_date=snapshot_date,phase="OUTCOME_JOIN",
            status="RUNNING",universe_count=len(rows),
        )

        as_of=datetime.combine(snapshot_date,time.max,tzinfo=timezone.utc)
        candidates={c.security_id:c for c in self.candidates.historical(as_of)}
        ready=censored=errors=controls_written=0

        for row in rows:
            security_id=str(row["security_id"])
            try:
                bars=self._load_price_path(security_id,snapshot_date)
                outcome=self.outcomes.compute(
                    security_id=security_id,
                    as_of_date_requested=snapshot_date,
                    bars=bars,
                )
                self.backtest.save_forward_outcome(outcome)
                replay_status=_replay_outcome_status(outcome.outcome_status)

                if replay_status=="READY":
                    ready+=1
                elif replay_status=="CENSORED":
                    censored+=1
                else:
                    errors+=1

                self.app.sqlite.connection.execute(
                    """
                    UPDATE wf5_replay_observations
                    SET outcome_status=?,outcome_joined_at=?
                    WHERE observation_id=?
                    """,
                    (
                        replay_status,
                        datetime.now(timezone.utc).isoformat(),
                        row["observation_id"],
                    ),
                )

                if replay_status=="READY":
                    label_at=_label_available_at(bars,outcome)
                    candidate=candidates.get(security_id)
                    if label_at is not None and candidate is not None:
                        v12,_v141=self.scorer.score(candidate,as_of)
                        historical_id=f"{security_id}|{snapshot_date.isoformat()}"
                        if self.wf4_builder.save_ready(
                            observation_id=historical_id,
                            result=v12,
                            outcome=outcome,
                            label_available_at=label_at,
                            source_run_id=run_id,
                        ):
                            controls_written+=1
            except CanonicalBacktestPriceUnavailable:
                censored+=1
                self.app.sqlite.connection.execute(
                    """
                    UPDATE wf5_replay_observations
                    SET outcome_status='CENSORED_NO_CANONICAL_PRICE',outcome_joined_at=?
                    WHERE observation_id=?
                    """,
                    (datetime.now(timezone.utc).isoformat(),row["observation_id"]),
                )
            except Exception:
                errors+=1
                self.app.sqlite.connection.execute(
                    """
                    UPDATE wf5_replay_observations
                    SET outcome_status='OUTCOME_ERROR',outcome_joined_at=?
                    WHERE observation_id=?
                    """,
                    (datetime.now(timezone.utc).isoformat(),row["observation_id"]),
                )

        self.app.sqlite.connection.commit()
        status="OUTCOME_COMPLETE" if errors == 0 else "OUTCOME_COMPLETE_WITH_ERRORS"
        self._set_checkpoint(
            run_id=run_id,snapshot_date=snapshot_date,phase="OUTCOME_JOIN",
            status=status,universe_count=len(rows),ready_count=ready,
            censored_count=censored,error_count=errors,completed=True,
        )
        return WF5OutcomePhaseReport(
            run_id=run_id,snapshot_date=snapshot_date,
            observation_count=len(rows),ready_count=ready,censored_count=censored,
            error_count=errors,historical_controls_written=controls_written,
            status=status,
        )

    def run_range(
        self,
        *,
        start_date: date,
        end_date: date,
        run_id: str | None=None,
    ) -> WF5RunReport:
        run_id=run_id or self.create_run(start_date=start_date,end_date=end_date)
        dates=monthly_snapshot_dates(start_date,end_date)
        score_complete=outcome_complete=blocked=0

        for snapshot_date in dates:
            score_status=self._checkpoint_status(run_id,snapshot_date,"SCORE")
            if score_status != "SCORE_COMPLETE":
                score_report=self.score_date(run_id=run_id,snapshot_date=snapshot_date)
                score_status=score_report.status
            if score_status=="BLOCKED_NON_PIT_UNIVERSE":
                blocked+=1
                continue
            if score_status=="SCORE_COMPLETE":
                score_complete+=1

            outcome_status=self._checkpoint_status(run_id,snapshot_date,"OUTCOME_JOIN")
            if outcome_status != "OUTCOME_COMPLETE":
                outcome_report=self.outcome_join_date(
                    run_id=run_id,snapshot_date=snapshot_date
                )
                outcome_status=outcome_report.status
            if outcome_status=="OUTCOME_COMPLETE":
                outcome_complete+=1

        status=(
            "COMPLETE"
            if score_complete==len(dates) and outcome_complete==len(dates)
            else "COMPLETE_WITH_BLOCKERS"
        )
        self.app.sqlite.connection.execute(
            """
            UPDATE wf5_replay_runs
            SET status=?,completed_at=?
            WHERE run_id=?
            """,
            (status,datetime.now(timezone.utc).isoformat(),run_id),
        )
        self.app.sqlite.connection.commit()
        return WF5RunReport(
            run_id=run_id,requested_dates=len(dates),
            score_complete_dates=score_complete,
            outcome_complete_dates=outcome_complete,
            blocked_dates=blocked,status=status,
        )
