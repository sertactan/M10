from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from core.backtest.wf7_metrics import (
    CANONICAL_THRESHOLDS,
    POLICY_VERSION,
    ValidationRow,
    calibration_bins,
    pr_auc_average_precision,
    threshold_metrics,
    top_n_metrics,
)


class WF7ValidationEngine:
    """Evaluate WF6 OOS rows only. No threshold fitting on final holdout."""

    def __init__(self, store) -> None:
        self.store=store

    def _rows(self, wf6_run_id: str) -> list[ValidationRow]:
        rows=self.store.connection.execute(
            """
            SELECT v141_score,fm252,outcome_status,time_to_10x_sessions,
                   max_multiple_observed,primary_route
            FROM wf6_oos_observations o
            JOIN wf6_walk_forward_folds f ON f.fold_id=o.fold_id
            WHERE f.run_id=?
            ORDER BY o.as_of_date,o.security_id
            """,
            (wf6_run_id,),
        ).fetchall()
        return [
            ValidationRow(
                score=row["v141_score"],fm252=row["fm252"],
                outcome_status=str(row["outcome_status"]),
                time_to_10x_sessions=row["time_to_10x_sessions"],
                max_multiple_observed=row["max_multiple_observed"],
                route=row["primary_route"],
            )
            for row in rows
        ]

    def evaluate(self, *, wf6_run_id: str) -> str:
        run=self.store.connection.execute(
            "SELECT * FROM wf6_walk_forward_runs WHERE run_id=?",
            (wf6_run_id,),
        ).fetchone()
        if run is None:
            raise ValueError("unknown WF6 run")

        rows=self._rows(wf6_run_id)
        validation_id=str(uuid.uuid4())
        now=datetime.now(timezone.utc).isoformat()
        metrics={
            "thresholds":{
                str(int(t)):asdict(threshold_metrics(rows,t))
                for t in CANONICAL_THRESHOLDS
            },
            "top20":asdict(top_n_metrics(rows,20)),
            "top50":asdict(top_n_metrics(rows,50)),
            "pr_auc":pr_auc_average_precision(rows),
            "calibration_bins":calibration_bins(rows),
        }
        ready_n=sum(r.outcome_status=="READY" and r.score is not None and r.fm252 is not None for r in rows)
        self.store.connection.execute(
            """
            INSERT INTO wf7_validation_runs
            (validation_id,wf6_run_id,policy_version,ready_n,metrics_json,status,created_at)
            VALUES (?,?,?,?,?,'COMPLETE',?)
            """,
            (
                validation_id,wf6_run_id,POLICY_VERSION,ready_n,
                json.dumps(metrics,sort_keys=True,separators=(",",":")),now,
            ),
        )
        self.store.connection.commit()
        return validation_id
