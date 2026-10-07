from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from core.backtest.wf8_reproducibility import (
    WF8ReproducibilityError,
    WF8ReproducibilityManifestService,
)


ACTIVATION_POLICY_VERSION = "WF8D_ACTIVATION_POLICY_V1_2026-10-07"


class WF8ActivationError(RuntimeError):
    pass


@dataclass(frozen=True)
class WF8ProductionActivation:
    activation_id: str
    model_version: str
    manifest_id: str
    hardening_id: str
    status: str
    previous_activation_id: str | None
    activated_at: str
    reason: str | None


class WF8ProductionActivationService:
    """Rollback-safe activation for hardened/reproducible production evidence.

    Candidate manifests are verified before cutover. The previous active
    activation becomes STANDBY only after candidate verification succeeds.
    Active manifests are re-verified on resolve; corruption/tamper triggers
    automatic rollback to the most recent verified standby activation.
    """

    def __init__(self, store) -> None:
        self.store=store
        self.repro=WF8ReproducibilityManifestService(store)

    def _row_to_activation(self, row) -> WF8ProductionActivation:
        return WF8ProductionActivation(
            activation_id=str(row["activation_id"]),
            model_version=str(row["model_version"]),
            manifest_id=str(row["manifest_id"]),
            hardening_id=str(row["hardening_id"]),
            status=str(row["status"]),
            previous_activation_id=(
                None if row["previous_activation_id"] is None
                else str(row["previous_activation_id"])
            ),
            activated_at=str(row["activated_at"]),
            reason=(None if row["reason"] is None else str(row["reason"])),
        )

    def _manifest_model_version(self, manifest_id: str) -> tuple[str,str]:
        row=self.store.connection.execute(
            """
            SELECT m.hardening_id,v.model_version
            FROM wf8_reproducibility_manifests m
            JOIN wf8_hardening_runs h ON h.hardening_id=m.hardening_id
            JOIN wf7_validation_runs v ON v.run_id=h.wf7_run_id
            WHERE m.manifest_id=?
              AND h.status='PRODUCTION_EVIDENCE_READY'
            """,
            (manifest_id,),
        ).fetchone()
        if row is None:
            raise WF8ActivationError(
                "manifest is not attached to a PRODUCTION_EVIDENCE_READY chain"
            )
        return str(row["model_version"]),str(row["hardening_id"])

    def active(self, model_version: str="S15.3_V1.4.1") -> WF8ProductionActivation | None:
        row=self.store.connection.execute(
            """
            SELECT *
            FROM wf8_production_activations
            WHERE model_version=? AND status='ACTIVE'
            ORDER BY activated_at DESC
            LIMIT 1
            """,
            (model_version,),
        ).fetchone()
        return None if row is None else self._row_to_activation(row)

    def activate(
        self,
        *,
        manifest_id: str,
        model_version: str="S15.3_V1.4.1",
        reason: str="validated production promotion",
    ) -> WF8ProductionActivation:
        # Verify candidate before touching the current production pointer.
        try:
            self.repro.verify(manifest_id)
        except WF8ReproducibilityError as exc:
            raise WF8ActivationError(
                f"candidate manifest failed verification: {exc}"
            ) from exc

        manifest_model,hardening_id=self._manifest_model_version(manifest_id)
        if manifest_model != model_version:
            raise WF8ActivationError(
                f"manifest model version mismatch: {manifest_model} != {model_version}"
            )

        current=self.active(model_version)
        if current is not None and current.manifest_id == manifest_id:
            return current

        activation_id=str(uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{ACTIVATION_POLICY_VERSION}|{model_version}|{manifest_id}",
        ))
        now=datetime.now(timezone.utc).isoformat()

        conn=self.store.connection
        try:
            conn.execute("BEGIN IMMEDIATE")
            # Re-read under write lock.
            current_row=conn.execute(
                """
                SELECT *
                FROM wf8_production_activations
                WHERE model_version=? AND status='ACTIVE'
                ORDER BY activated_at DESC
                LIMIT 1
                """,
                (model_version,),
            ).fetchone()
            previous_id=(
                None if current_row is None else str(current_row["activation_id"])
            )
            if current_row is not None:
                conn.execute(
                    """
                    UPDATE wf8_production_activations
                    SET status='STANDBY',deactivated_at=?,reason=?
                    WHERE activation_id=?
                    """,
                    (
                        now,
                        f"superseded by {activation_id}",
                        previous_id,
                    ),
                )

            conn.execute(
                """
                INSERT INTO wf8_production_activations (
                    activation_id,model_version,manifest_id,hardening_id,
                    policy_version,status,previous_activation_id,activated_at,
                    deactivated_at,reason
                ) VALUES (?,?,?,?,?,'ACTIVE',?,?,NULL,?)
                ON CONFLICT(activation_id) DO UPDATE SET
                    status='ACTIVE',
                    previous_activation_id=excluded.previous_activation_id,
                    activated_at=excluded.activated_at,
                    deactivated_at=NULL,
                    reason=excluded.reason
                """,
                (
                    activation_id,model_version,manifest_id,hardening_id,
                    ACTIVATION_POLICY_VERSION,previous_id,now,reason,
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        active=self.active(model_version)
        if active is None:
            raise WF8ActivationError("activation cutover failed")
        return active

    def _standby_candidates(
        self,
        model_version: str,
        *,
        exclude_activation_id: str,
    ):
        return self.store.connection.execute(
            """
            SELECT *
            FROM wf8_production_activations
            WHERE model_version=?
              AND activation_id<>?
              AND status IN ('STANDBY','ROLLED_BACK')
            ORDER BY activated_at DESC
            """,
            (model_version,exclude_activation_id),
        ).fetchall()

    def _quarantine(
        self,
        activation_id: str,
        *,
        reason: str,
    ) -> None:
        now=datetime.now(timezone.utc).isoformat()
        self.store.connection.execute(
            """
            UPDATE wf8_production_activations
            SET status='QUARANTINED',deactivated_at=?,reason=?
            WHERE activation_id=?
            """,
            (now,reason,activation_id),
        )
        self.store.connection.commit()

    def resolve_active(
        self,
        model_version: str="S15.3_V1.4.1",
    ) -> WF8ProductionActivation:
        current=self.active(model_version)
        if current is None:
            raise WF8ActivationError(
                f"no active production activation for {model_version}"
            )

        try:
            self.repro.verify(current.manifest_id)
            return current
        except WF8ReproducibilityError as exc:
            failure_reason=f"active manifest verification failed: {exc}"

        # Find a previously active manifest that still verifies.
        selected=None
        for row in self._standby_candidates(
            model_version,
            exclude_activation_id=current.activation_id,
        ):
            candidate=self._row_to_activation(row)
            try:
                self.repro.verify(candidate.manifest_id)
                selected=candidate
                break
            except WF8ReproducibilityError:
                continue

        if selected is None:
            self._quarantine(current.activation_id,reason=failure_reason)
            raise WF8ActivationError(
                "active production manifest is invalid and no verified LKG standby exists"
            )

        now=datetime.now(timezone.utc).isoformat()
        conn=self.store.connection
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                UPDATE wf8_production_activations
                SET status='QUARANTINED',deactivated_at=?,reason=?
                WHERE activation_id=?
                """,
                (now,failure_reason,current.activation_id),
            )
            conn.execute(
                """
                UPDATE wf8_production_activations
                SET status='ACTIVE',deactivated_at=NULL,reason=?
                WHERE activation_id=?
                """,
                (
                    f"automatic rollback from {current.activation_id}",
                    selected.activation_id,
                ),
            )
            conn.execute(
                """
                INSERT INTO wf8_activation_events (
                    event_id,model_version,event_type,from_activation_id,
                    to_activation_id,reason,created_at
                ) VALUES (?,?,?,?,?,?,?)
                """,
                (
                    str(uuid.uuid4()),model_version,"AUTO_ROLLBACK",
                    current.activation_id,selected.activation_id,
                    failure_reason,now,
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        restored=self.active(model_version)
        if restored is None:
            raise WF8ActivationError("automatic rollback failed")
        return restored
