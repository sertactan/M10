from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


WF8C_MANIFEST_VERSION = "WF8C_REPRO_MANIFEST_V1_2026-10-07"


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _sha(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class WF8ReproducibilityManifest:
    manifest_id: str
    hardening_id: str
    wf5_run_id: str
    wf6_run_id: str
    wf7_run_id: str
    code_identity: str
    wf5_hash: str
    wf6_hash: str
    wf7_hash: str
    wf8_hash: str
    chain_hash: str
    status: str


class WF8ReproducibilityError(RuntimeError):
    pass


class WF8ReproducibilityManifestService:
    """Deterministically hash the persisted WF5->WF8 evidence chain."""

    def __init__(self, store) -> None:
        self.store=store

    def _one(self, sql: str, params: tuple) -> dict:
        row=self.store.connection.execute(sql,params).fetchone()
        if row is None:
            raise WF8ReproducibilityError("required reproducibility row is missing")
        return dict(row)

    def _many(self, sql: str, params: tuple) -> list[dict]:
        return [
            dict(row)
            for row in self.store.connection.execute(sql,params).fetchall()
        ]

    def _resolve_chain(self, hardening_id: str) -> tuple[dict,dict,dict,dict]:
        wf8=self._one(
            "SELECT hardening_id,wf5_run_id,wf6_run_id,wf7_run_id,policy_version,status,blockers_json,warnings_json "
            "FROM wf8_hardening_runs WHERE hardening_id=?",
            (hardening_id,),
        )
        if wf8["status"] != "PRODUCTION_EVIDENCE_READY":
            raise WF8ReproducibilityError(
                f"hardening chain is not production ready: {wf8['status']}"
            )
        wf5=self._one(
            "SELECT run_id,start_date,end_date,frequency,v12_version,v141_version,status "
            "FROM wf5_replay_runs WHERE run_id=?",
            (wf8["wf5_run_id"],),
        )
        wf6=self._one(
            "SELECT run_id,source_wf5_run_id,reference_start_year,first_test_year,last_test_year,"
            "v12_version,v141_version,leakage_policy,status "
            "FROM wf6_walk_forward_runs WHERE run_id=?",
            (wf8["wf6_run_id"],),
        )
        wf7=self._one(
            "SELECT run_id,wf6_run_id,model_version,validation_policy,status "
            "FROM wf7_validation_runs WHERE run_id=?",
            (wf8["wf7_run_id"],),
        )
        if wf6["source_wf5_run_id"] != wf5["run_id"]:
            raise WF8ReproducibilityError("WF6->WF5 source link mismatch")
        if wf7["wf6_run_id"] != wf6["run_id"]:
            raise WF8ReproducibilityError("WF7->WF6 source link mismatch")
        return wf5,wf6,wf7,wf8

    def _wf5_payload(self, wf5: dict) -> dict:
        run_id=str(wf5["run_id"])
        checkpoints=self._many(
            """
            SELECT snapshot_date,phase,status,universe_count,scored_count,
                   ready_count,inconclusive_count,censored_count,error_count,message
            FROM wf5_replay_checkpoints
            WHERE run_id=?
            ORDER BY snapshot_date,phase
            """,
            (run_id,),
        )
        observations=self._many(
            """
            SELECT security_id,ticker,as_of_date,primary_route,v12_score,v12_status,
                   v141_score,v141_status,outcome_status
            FROM wf5_replay_observations
            WHERE run_id=?
            ORDER BY as_of_date,security_id,observation_id
            """,
            (run_id,),
        )
        return {"run":wf5,"checkpoints":checkpoints,"observations":observations}

    def _wf6_payload(self, wf6: dict) -> dict:
        run_id=str(wf6["run_id"])
        folds=self._many(
            """
            SELECT fold_id,fold_index,reference_start_date,reference_end_date,
                   test_start_date,test_end_date,status,oos_observations,
                   ready_outcomes,censored_outcomes,v141_ready,same_security_overlap
            FROM wf6_walk_forward_folds
            WHERE run_id=?
            ORDER BY fold_index,fold_id
            """,
            (run_id,),
        )
        oos=self._many(
            """
            SELECT o.fold_id,o.source_observation_id,o.security_id,o.ticker,
                   o.as_of_date,o.primary_route,o.v12_score,o.v12_status,
                   o.v141_score,o.v141_status,o.outcome_status,o.fm252,
                   o.outcome_class,o.time_to_2x_sessions,o.time_to_5x_sessions,
                   o.time_to_10x_sessions,o.max_multiple_observed,o.repeated_security
            FROM wf6_oos_observations o
            JOIN wf6_walk_forward_folds f ON f.fold_id=o.fold_id
            WHERE f.run_id=?
            ORDER BY o.fold_id,o.as_of_date,o.security_id,o.source_observation_id
            """,
            (run_id,),
        )
        return {"run":wf6,"folds":folds,"oos":oos}

    def _wf7_payload(self, wf7: dict) -> dict:
        run_id=str(wf7["run_id"])
        summary=self._one(
            """
            SELECT ready_oos_n,scored_ready_n,score_coverage_pct,true10_count,
                   base_rate_10x_pct,pr_auc_average_precision,probability_head_status
            FROM wf7_validation_summary
            WHERE run_id=?
            """,
            (run_id,),
        )
        thresholds=self._many(
            """
            SELECT selector,threshold,selected_n,true10_n,precision_10x_pct,
                   recall_10x_pct,lift_vs_base,near_miss_rate_pct,
                   magnitude_fp_rate_pct,strong_winner_fp_rate_pct,hard_fp_rate_pct,
                   median_fm252,median_time_to_10x_sessions
            FROM wf7_threshold_metrics
            WHERE run_id=?
            ORDER BY selector
            """,
            (run_id,),
        )
        buckets=self._many(
            """
            SELECT bucket_label,score_low,score_high,sample_size,true10_count,
                   p2_plus_pct,p5_plus_pct,p7_plus_pct,p10_plus_pct,
                   median_fm252,sample_quality,status
            FROM wf7_calibration_buckets
            WHERE run_id=?
            ORDER BY score_low,bucket_label
            """,
            (run_id,),
        )
        routes=self._many(
            """
            SELECT route,sample_size,true10_count,p10_plus_pct,p5_plus_pct,median_fm252
            FROM wf7_route_metrics
            WHERE run_id=?
            ORDER BY route
            """,
            (run_id,),
        )
        return {
            "run":wf7,
            "summary":summary,
            "thresholds":thresholds,
            "buckets":buckets,
            "routes":routes,
        }

    def _wf8_payload(self, wf8: dict) -> dict:
        checks=self._many(
            """
            SELECT check_name,passed,blocking,evidence
            FROM wf8_hardening_checks
            WHERE hardening_id=?
            ORDER BY check_name
            """,
            (wf8["hardening_id"],),
        )
        return {"run":wf8,"checks":checks}

    def compute(
        self,
        *,
        hardening_id: str,
        code_identity: str,
    ) -> WF8ReproducibilityManifest:
        code_identity=code_identity.strip()
        if not code_identity:
            raise WF8ReproducibilityError("code_identity is required")
        wf5,wf6,wf7,wf8=self._resolve_chain(hardening_id)

        wf5_hash=_sha(self._wf5_payload(wf5))
        wf6_hash=_sha(self._wf6_payload(wf6))
        wf7_hash=_sha(self._wf7_payload(wf7))
        wf8_hash=_sha(self._wf8_payload(wf8))
        chain_payload={
            "manifest_version":WF8C_MANIFEST_VERSION,
            "code_identity":code_identity,
            "hardening_id":hardening_id,
            "wf5_run_id":wf5["run_id"],
            "wf6_run_id":wf6["run_id"],
            "wf7_run_id":wf7["run_id"],
            "wf5_hash":wf5_hash,
            "wf6_hash":wf6_hash,
            "wf7_hash":wf7_hash,
            "wf8_hash":wf8_hash,
        }
        chain_hash=_sha(chain_payload)
        manifest_id=str(uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{WF8C_MANIFEST_VERSION}|{chain_hash}",
        ))
        return WF8ReproducibilityManifest(
            manifest_id=manifest_id,
            hardening_id=hardening_id,
            wf5_run_id=str(wf5["run_id"]),
            wf6_run_id=str(wf6["run_id"]),
            wf7_run_id=str(wf7["run_id"]),
            code_identity=code_identity,
            wf5_hash=wf5_hash,
            wf6_hash=wf6_hash,
            wf7_hash=wf7_hash,
            wf8_hash=wf8_hash,
            chain_hash=chain_hash,
            status="VERIFIED",
        )

    def create(
        self,
        *,
        hardening_id: str,
        code_identity: str,
    ) -> WF8ReproducibilityManifest:
        manifest=self.compute(
            hardening_id=hardening_id,
            code_identity=code_identity,
        )
        now=datetime.now(timezone.utc).isoformat()
        self.store.connection.execute(
            """
            INSERT INTO wf8_reproducibility_manifests (
                manifest_id,hardening_id,wf5_run_id,wf6_run_id,wf7_run_id,
                code_identity,manifest_version,wf5_hash,wf6_hash,wf7_hash,wf8_hash,
                chain_hash,status,created_at,verified_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(manifest_id) DO UPDATE SET
                status=excluded.status,
                verified_at=excluded.verified_at
            """,
            (
                manifest.manifest_id,manifest.hardening_id,manifest.wf5_run_id,
                manifest.wf6_run_id,manifest.wf7_run_id,manifest.code_identity,
                WF8C_MANIFEST_VERSION,manifest.wf5_hash,manifest.wf6_hash,
                manifest.wf7_hash,manifest.wf8_hash,manifest.chain_hash,
                manifest.status,now,now,
            ),
        )
        self.store.connection.commit()
        return manifest

    def verify(self, manifest_id: str) -> WF8ReproducibilityManifest:
        stored=self._one(
            "SELECT * FROM wf8_reproducibility_manifests WHERE manifest_id=?",
            (manifest_id,),
        )
        current=self.compute(
            hardening_id=str(stored["hardening_id"]),
            code_identity=str(stored["code_identity"]),
        )
        fields=("wf5_hash","wf6_hash","wf7_hash","wf8_hash","chain_hash")
        mismatches=[
            field
            for field in fields
            if str(stored[field]) != str(getattr(current,field))
        ]
        if mismatches:
            self.store.connection.execute(
                "UPDATE wf8_reproducibility_manifests SET status='TAMPERED',verified_at=? WHERE manifest_id=?",
                (datetime.now(timezone.utc).isoformat(),manifest_id),
            )
            self.store.connection.commit()
            raise WF8ReproducibilityError(
                "reproducibility hash mismatch: " + ", ".join(mismatches)
            )
        self.store.connection.execute(
            "UPDATE wf8_reproducibility_manifests SET status='VERIFIED',verified_at=? WHERE manifest_id=?",
            (datetime.now(timezone.utc).isoformat(),manifest_id),
        )
        self.store.connection.commit()
        return current
