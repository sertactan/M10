from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone


WF8_POLICY_VERSION = "WF8_PRODUCTION_HARDENING_V1_2026-10-07"

WF8_ACCEPTANCE_ITEMS = (
    "WF5 replay complete",
    "WF6 walk-forward complete",
    "WF6 source chain integrity",
    "WF6 leakage policy locked",
    "WF6 folds materialized",
    "WF6 READY OOS evidence",
    "WF7 validation complete",
    "WF7 source chain integrity",
    "WF7 summary available",
    "WF7 threshold matrix complete",
    "WF7 calibration bucket matrix complete",
    "Calibration release fail-closed",
)

REQUIRED_THRESHOLD_SELECTORS = {
    "SCORE_GE_65",
    "SCORE_GE_75",
    "SCORE_GE_80",
    "SCORE_GE_85",
    "TOP20",
    "TOP50",
}

REQUIRED_BUCKETS = {
    "<55",
    "55-64",
    "65-74",
    "75-79",
    "80-84",
    "85+",
}


@dataclass(frozen=True)
class WF8AcceptanceItem:
    name: str
    passed: bool
    evidence: str
    blocking: bool = True


@dataclass(frozen=True)
class WF8HardeningReport:
    hardening_id: str
    wf5_run_id: str
    wf6_run_id: str
    wf7_run_id: str
    status: str
    blockers: tuple[str,...]
    warnings: tuple[str,...]
    items: tuple[WF8AcceptanceItem,...]


def require_wf8_acceptance_matrix(items: list[WF8AcceptanceItem]) -> None:
    expected=set(WF8_ACCEPTANCE_ITEMS)
    actual={item.name for item in items}
    if actual != expected:
        raise ValueError(
            f"WF8 acceptance matrix mismatch; missing={sorted(expected-actual)} "
            f"unexpected={sorted(actual-expected)}"
        )


def release_status(items: list[WF8AcceptanceItem]) -> tuple[str,tuple[str,...],tuple[str,...]]:
    require_wf8_acceptance_matrix(items)
    blockers=tuple(
        f"{item.name}: {item.evidence}"
        for item in items
        if item.blocking and not item.passed
    )
    warnings=tuple(
        f"{item.name}: {item.evidence}"
        for item in items
        if (not item.blocking) and (not item.passed)
    )
    return (
        "PRODUCTION_EVIDENCE_READY" if not blockers else "PRODUCTION_BLOCKED",
        blockers,
        warnings,
    )


class WF8ProductionHardeningAuditor:
    """Fail-closed release gate for the WF5 -> WF6 -> WF7 evidence chain.

    WF8 does not tune model weights, thresholds or probabilities. It verifies
    that production evidence is real, out-of-sample, traceable and sufficiently
    materialized before downstream activation.
    """

    def __init__(self, store) -> None:
        self.store=store

    def audit(self, *, wf7_run_id: str, persist: bool=True) -> WF8HardeningReport:
        wf7=self.store.connection.execute(
            "SELECT * FROM wf7_validation_runs WHERE run_id=?",
            (wf7_run_id,),
        ).fetchone()
        if wf7 is None:
            raise ValueError("unknown WF7 validation run")

        wf6_run_id=str(wf7["wf6_run_id"])
        wf6=self.store.connection.execute(
            "SELECT * FROM wf6_walk_forward_runs WHERE run_id=?",
            (wf6_run_id,),
        ).fetchone()
        if wf6 is None:
            raise ValueError("WF7 source WF6 run does not exist")

        wf5_run_id=str(wf6["source_wf5_run_id"])
        wf5=self.store.connection.execute(
            "SELECT * FROM wf5_replay_runs WHERE run_id=?",
            (wf5_run_id,),
        ).fetchone()
        if wf5 is None:
            raise ValueError("WF6 source WF5 run does not exist")

        folds=self.store.connection.execute(
            "SELECT * FROM wf6_walk_forward_folds WHERE run_id=? ORDER BY fold_index",
            (wf6_run_id,),
        ).fetchall()
        summary=self.store.connection.execute(
            "SELECT * FROM wf7_validation_summary WHERE run_id=?",
            (wf7_run_id,),
        ).fetchone()
        thresholds=self.store.connection.execute(
            "SELECT selector FROM wf7_threshold_metrics WHERE run_id=?",
            (wf7_run_id,),
        ).fetchall()
        buckets=self.store.connection.execute(
            "SELECT bucket_label,status,sample_size FROM wf7_calibration_buckets WHERE run_id=?",
            (wf7_run_id,),
        ).fetchall()

        threshold_names={str(row["selector"]) for row in thresholds}
        bucket_names={str(row["bucket_label"]) for row in buckets}
        ready_buckets=[
            row for row in buckets
            if str(row["status"])=="READY" and int(row["sample_size"])>=30
        ]

        fold_count=len(folds)
        complete_folds=sum(str(row["status"])=="COMPLETE" for row in folds)
        ready_oos=sum(int(row["ready_outcomes"]) for row in folds)
        censored_oos=sum(int(row["censored_outcomes"]) for row in folds)

        summary_ok=summary is not None
        probability_status=(
            str(summary["probability_head_status"]) if summary is not None else "MISSING"
        )

        items=[
            WF8AcceptanceItem(
                "WF5 replay complete",
                str(wf5["status"])=="COMPLETE",
                f"status={wf5['status']}",
            ),
            WF8AcceptanceItem(
                "WF6 walk-forward complete",
                str(wf6["status"])=="COMPLETE",
                f"status={wf6['status']}",
            ),
            WF8AcceptanceItem(
                "WF6 source chain integrity",
                bool(wf6["source_wf5_run_id"]) and str(wf6["source_wf5_run_id"])==wf5_run_id,
                f"wf5={wf5_run_id}; wf6.source={wf6['source_wf5_run_id']}",
            ),
            WF8AcceptanceItem(
                "WF6 leakage policy locked",
                str(wf6["leakage_policy"])=="WF6_LEAKAGE_POLICY_V1_2026-10-07",
                f"policy={wf6['leakage_policy']}",
            ),
            WF8AcceptanceItem(
                "WF6 folds materialized",
                fold_count > 0 and complete_folds==fold_count,
                f"complete={complete_folds}/{fold_count}",
            ),
            WF8AcceptanceItem(
                "WF6 READY OOS evidence",
                ready_oos > 0,
                f"ready={ready_oos}; censored={censored_oos}",
            ),
            WF8AcceptanceItem(
                "WF7 validation complete",
                str(wf7["status"])=="COMPLETE",
                f"status={wf7['status']}",
            ),
            WF8AcceptanceItem(
                "WF7 source chain integrity",
                str(wf7["wf6_run_id"])==wf6_run_id,
                f"wf6={wf6_run_id}; wf7.source={wf7['wf6_run_id']}",
            ),
            WF8AcceptanceItem(
                "WF7 summary available",
                summary_ok and int(summary["ready_oos_n"]) > 0,
                (
                    f"ready_oos={summary['ready_oos_n']}; "
                    f"scored_ready={summary['scored_ready_n']}"
                    if summary is not None else "summary missing"
                ),
            ),
            WF8AcceptanceItem(
                "WF7 threshold matrix complete",
                threshold_names==REQUIRED_THRESHOLD_SELECTORS,
                f"selectors={sorted(threshold_names)}",
            ),
            WF8AcceptanceItem(
                "WF7 calibration bucket matrix complete",
                bucket_names==REQUIRED_BUCKETS,
                f"buckets={sorted(bucket_names)}",
            ),
            WF8AcceptanceItem(
                "Calibration release fail-closed",
                (
                    probability_status=="NOT_AVAILABLE_SCORE_IS_NOT_PROBABILITY"
                    and len(ready_buckets) > 0
                ),
                (
                    f"probability_head={probability_status}; "
                    f"usable_empirical_buckets={len(ready_buckets)}"
                ),
            ),
        ]

        status,blockers,warnings=release_status(items)
        hardening_id=str(uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{WF8_POLICY_VERSION}|{wf5_run_id}|{wf6_run_id}|{wf7_run_id}",
        ))
        report=WF8HardeningReport(
            hardening_id=hardening_id,
            wf5_run_id=wf5_run_id,
            wf6_run_id=wf6_run_id,
            wf7_run_id=wf7_run_id,
            status=status,
            blockers=blockers,
            warnings=warnings,
            items=tuple(items),
        )
        if persist:
            self._persist(report)
        return report

    def _persist(self, report: WF8HardeningReport) -> None:
        now=datetime.now(timezone.utc).isoformat()
        self.store.connection.execute(
            """
            INSERT INTO wf8_hardening_runs (
                hardening_id,wf5_run_id,wf6_run_id,wf7_run_id,policy_version,
                status,blockers_json,warnings_json,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(hardening_id) DO UPDATE SET
                status=excluded.status,
                blockers_json=excluded.blockers_json,
                warnings_json=excluded.warnings_json,
                created_at=excluded.created_at
            """,
            (
                report.hardening_id,report.wf5_run_id,report.wf6_run_id,
                report.wf7_run_id,WF8_POLICY_VERSION,report.status,
                json.dumps(report.blockers),json.dumps(report.warnings),now,
            ),
        )
        self.store.connection.execute(
            "DELETE FROM wf8_hardening_checks WHERE hardening_id=?",
            (report.hardening_id,),
        )
        for item in report.items:
            self.store.connection.execute(
                """
                INSERT INTO wf8_hardening_checks (
                    hardening_id,check_name,passed,blocking,evidence,created_at
                ) VALUES (?,?,?,?,?,?)
                """,
                (
                    report.hardening_id,item.name,int(item.passed),
                    int(item.blocking),item.evidence,now,
                ),
            )
        self.store.connection.commit()
