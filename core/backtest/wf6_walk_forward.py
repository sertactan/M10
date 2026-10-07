from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone

from core.backtest.wf6_policy import LEAKAGE_POLICY_VERSION
from core.models.s153_v12 import S153V12Model
from core.models.s153_v141 import S153V141Model


@dataclass(frozen=True)
class WalkForwardFold:
    index: int
    reference_start: date
    reference_end: date
    test_start: date
    test_end: date


@dataclass(frozen=True)
class WF6FoldReport:
    fold_id: str
    test_year: int
    oos_observations: int
    ready_outcomes: int
    censored_outcomes: int
    v141_ready: int
    same_security_overlap: int
    status: str


@dataclass(frozen=True)
class WF6RunReport:
    run_id: str
    folds: int
    completed_folds: int
    oos_observations: int
    ready_outcomes: int
    censored_outcomes: int
    status: str


def expanding_folds(
    *,
    reference_start_year: int = 2013,
    first_test_year: int = 2018,
    last_test_year: int = 2024,
) -> tuple[WalkForwardFold,...]:
    if first_test_year <= reference_start_year:
        raise ValueError("first_test_year must be after reference_start_year")
    if last_test_year < first_test_year:
        raise ValueError("last_test_year must be >= first_test_year")
    return tuple(
        WalkForwardFold(
            index=i,
            reference_start=date(reference_start_year,1,1),
            reference_end=date(year-1,12,31),
            test_start=date(year,1,1),
            test_end=date(year,12,31),
        )
        for i,year in enumerate(range(first_test_year,last_test_year+1),start=1)
    )


class WF6WalkForwardEngine:
    """Expanding-window OOS validator for frozen S15.3 V1.4.1.

    No weights/thresholds are fitted here. WF5 has already scored each PIT
    observation before outcome join. WF6 only freezes temporal folds, audits
    leakage and copies OOS score/outcome evidence into a reproducible panel.
    """

    def __init__(self, store) -> None:
        self.store=store

    def create_run(
        self,
        *,
        source_wf5_run_id: str,
        reference_start_year: int=2013,
        first_test_year: int=2018,
        last_test_year: int=2024,
    ) -> str:
        source=self.store.connection.execute(
            "SELECT * FROM wf5_replay_runs WHERE run_id=?",
            (source_wf5_run_id,),
        ).fetchone()
        if source is None:
            raise ValueError("unknown WF5 replay run")
        run_id=str(uuid.uuid4())
        now=datetime.now(timezone.utc).isoformat()
        self.store.connection.execute(
            """
            INSERT INTO wf6_walk_forward_runs (
                run_id,source_wf5_run_id,reference_start_year,first_test_year,
                last_test_year,v12_version,v141_version,leakage_policy,status,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                run_id,source_wf5_run_id,reference_start_year,first_test_year,
                last_test_year,S153V12Model.canonical_formula_version,
                S153V141Model.canonical_formula_version,
                LEAKAGE_POLICY_VERSION,"ACTIVE",now,
            ),
        )
        self.store.connection.commit()
        return run_id

    def _reference_security_ids(self, cutoff: date) -> set[str]:
        # Use only historical labels whose availability precedes the OOS year.
        rows=self.store.connection.execute(
            """
            SELECT DISTINCT security_id
            FROM s153_historical_control_observations
            WHERE label_available_at < ?
            """,
            (datetime.combine(cutoff,datetime.min.time(),tzinfo=timezone.utc).isoformat(),),
        ).fetchall()
        return {str(row["security_id"]) for row in rows}

    def run_fold(
        self,
        *,
        run_id: str,
        source_wf5_run_id: str,
        fold: WalkForwardFold,
    ) -> WF6FoldReport:
        fold_id=f"{run_id}:F{fold.index:02d}"
        reference_ids=self._reference_security_ids(fold.test_start)

        rows=self.store.connection.execute(
            """
            SELECT
                w.observation_id,w.security_id,w.ticker,w.as_of_date,w.primary_route,
                w.v12_score,w.v12_status,w.v141_score,w.v141_status,w.outcome_status,
                o.fm252,o.outcome_class,o.time_to_2x_sessions,o.time_to_5x_sessions,
                o.time_to_10x_sessions,o.max_multiple_observed
            FROM wf5_replay_observations w
            LEFT JOIN forward_outcomes o
              ON o.security_id=w.security_id
             AND o.as_of_date_requested=w.as_of_date
            WHERE w.run_id=?
              AND w.as_of_date>=?
              AND w.as_of_date<=?
            ORDER BY w.as_of_date,w.security_id
            """,
            (
                source_wf5_run_id,
                fold.test_start.isoformat(),
                fold.test_end.isoformat(),
            ),
        ).fetchall()

        ready=censored=v141_ready=overlap=0
        now=datetime.now(timezone.utc).isoformat()
        for row in rows:
            outcome_status=str(row["outcome_status"])
            if outcome_status=="READY" and row["fm252"] is not None:
                ready+=1
            else:
                censored+=1
            if row["v141_score"] is not None:
                v141_ready+=1
            repeated=1 if str(row["security_id"]) in reference_ids else 0
            overlap+=repeated
            self.store.connection.execute(
                """
                INSERT INTO wf6_oos_observations (
                    fold_id,source_observation_id,security_id,ticker,as_of_date,
                    primary_route,v12_score,v12_status,v141_score,v141_status,
                    outcome_status,fm252,outcome_class,time_to_2x_sessions,
                    time_to_5x_sessions,time_to_10x_sessions,max_multiple_observed,
                    repeated_security,created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(fold_id,source_observation_id) DO UPDATE SET
                    v12_score=excluded.v12_score,
                    v12_status=excluded.v12_status,
                    v141_score=excluded.v141_score,
                    v141_status=excluded.v141_status,
                    outcome_status=excluded.outcome_status,
                    fm252=excluded.fm252,
                    outcome_class=excluded.outcome_class,
                    repeated_security=excluded.repeated_security,
                    created_at=excluded.created_at
                """,
                (
                    fold_id,row["observation_id"],row["security_id"],row["ticker"],
                    row["as_of_date"],row["primary_route"],row["v12_score"],
                    row["v12_status"],row["v141_score"],row["v141_status"],
                    outcome_status,row["fm252"],row["outcome_class"],
                    row["time_to_2x_sessions"],row["time_to_5x_sessions"],
                    row["time_to_10x_sessions"],row["max_multiple_observed"],
                    repeated,now,
                ),
            )

        status="COMPLETE" if rows else "EMPTY_OOS"
        self.store.connection.execute(
            """
            INSERT INTO wf6_walk_forward_folds (
                fold_id,run_id,fold_index,reference_start_date,reference_end_date,
                test_start_date,test_end_date,status,oos_observations,ready_outcomes,
                censored_outcomes,v141_ready,same_security_overlap,created_at,completed_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(fold_id) DO UPDATE SET
                status=excluded.status,
                oos_observations=excluded.oos_observations,
                ready_outcomes=excluded.ready_outcomes,
                censored_outcomes=excluded.censored_outcomes,
                v141_ready=excluded.v141_ready,
                same_security_overlap=excluded.same_security_overlap,
                completed_at=excluded.completed_at
            """,
            (
                fold_id,run_id,fold.index,fold.reference_start.isoformat(),
                fold.reference_end.isoformat(),fold.test_start.isoformat(),
                fold.test_end.isoformat(),status,len(rows),ready,censored,
                v141_ready,overlap,now,now,
            ),
        )
        self.store.connection.commit()
        return WF6FoldReport(
            fold_id=fold_id,test_year=fold.test_start.year,
            oos_observations=len(rows),ready_outcomes=ready,
            censored_outcomes=censored,v141_ready=v141_ready,
            same_security_overlap=overlap,status=status,
        )

    def run(
        self,
        *,
        source_wf5_run_id: str,
        reference_start_year: int=2013,
        first_test_year: int=2018,
        last_test_year: int=2024,
        run_id: str | None=None,
    ) -> WF6RunReport:
        folds=expanding_folds(
            reference_start_year=reference_start_year,
            first_test_year=first_test_year,
            last_test_year=last_test_year,
        )
        run_id=run_id or self.create_run(
            source_wf5_run_id=source_wf5_run_id,
            reference_start_year=reference_start_year,
            first_test_year=first_test_year,
            last_test_year=last_test_year,
        )

        reports=[
            self.run_fold(
                run_id=run_id,
                source_wf5_run_id=source_wf5_run_id,
                fold=fold,
            )
            for fold in folds
        ]
        completed=sum(r.status=="COMPLETE" for r in reports)
        status="COMPLETE" if completed==len(folds) else "COMPLETE_WITH_BLOCKERS"
        now=datetime.now(timezone.utc).isoformat()
        self.store.connection.execute(
            """
            UPDATE wf6_walk_forward_runs
            SET status=?,completed_at=?
            WHERE run_id=?
            """,
            (status,now,run_id),
        )
        self.store.connection.commit()
        return WF6RunReport(
            run_id=run_id,folds=len(folds),completed_folds=completed,
            oos_observations=sum(r.oos_observations for r in reports),
            ready_outcomes=sum(r.ready_outcomes for r in reports),
            censored_outcomes=sum(r.censored_outcomes for r in reports),
            status=status,
        )
