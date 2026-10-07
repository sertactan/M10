from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timezone

from core.features.wf3_bulk import WF3WholeUniverseMaterializer
from core.models.s153_v12 import S153V12Model
from core.models.s153_v141 import S153V141Model
from core.research.walkforward_readiness import WalkForwardReadinessAuditor
from core.scanner.production import (
    CanonicalDualModelScorer,
    RepositoryCandidateSource,
)
from data.repositories.model_feature_repository import ModelFeatureRepository
from data.repositories.security_repository import SecurityRepository


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


class WF5WholeMarketReplay:
    """Score-phase replay. Future outcomes are intentionally not joined here."""

    def __init__(self, app) -> None:
        self.app=app
        self.securities=SecurityRepository(app.sqlite)
        self.features=ModelFeatureRepository(app.sqlite)
        self.readiness=WalkForwardReadinessAuditor(app.sqlite)
        self.candidates=RepositoryCandidateSource(self.securities)
        self.scorer=CanonicalDualModelScorer(self.features)
        self.wf3=WF3WholeUniverseMaterializer(app)

    def create_run(self, *, start_date: date, end_date: date, frequency: str="MONTHLY") -> str:
        if end_date < start_date:
            raise ValueError("end_date must be >= start_date")
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

    def score_date(self, *, run_id: str, snapshot_date: date) -> WF5ScorePhaseReport:
        audit=self.readiness.audit(snapshot_date)
        if not audit.exact_pit_universe:
            return WF5ScorePhaseReport(
                run_id=run_id,snapshot_date=snapshot_date,
                universe_count=audit.universe_members,scored_count=0,
                ready_count=0,inconclusive_count=0,error_count=0,
                status="BLOCKED_NON_PIT_UNIVERSE",
            )

        now=datetime.now(timezone.utc).isoformat()
        self.app.sqlite.connection.execute(
            """
            INSERT INTO wf5_replay_checkpoints
            (run_id,snapshot_date,phase,status,started_at)
            VALUES (?,?,?,?,?)
            ON CONFLICT(run_id,snapshot_date,phase) DO UPDATE SET
                status=excluded.status,started_at=excluded.started_at,message=NULL
            """,
            (run_id,snapshot_date.isoformat(),"SCORE","RUNNING",now),
        )
        self.app.sqlite.connection.commit()

        # Destination/peer evidence is materialized before scoring, using PIT-only inputs.
        self.wf3.materialize_date(snapshot_date)

        as_of=datetime.combine(snapshot_date,time.max,tzinfo=timezone.utc)
        candidates=self.candidates.historical(as_of)
        scored=ready=inconclusive=errors=0

        for candidate in candidates:
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
                        score_created_at=excluded.score_created_at
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

        status="SCORE_COMPLETE" if errors == 0 else "SCORE_COMPLETE_WITH_ERRORS"
        self.app.sqlite.connection.execute(
            """
            UPDATE wf5_replay_checkpoints
            SET status=?,universe_count=?,scored_count=?,ready_count=?,
                inconclusive_count=?,error_count=?,completed_at=?
            WHERE run_id=? AND snapshot_date=? AND phase='SCORE'
            """,
            (
                status,len(candidates),scored,ready,inconclusive,errors,
                datetime.now(timezone.utc).isoformat(),
                run_id,snapshot_date.isoformat(),
            ),
        )
        self.app.sqlite.connection.commit()
        return WF5ScorePhaseReport(
            run_id=run_id,snapshot_date=snapshot_date,
            universe_count=len(candidates),scored_count=scored,
            ready_count=ready,inconclusive_count=inconclusive,
            error_count=errors,status=status,
        )
