from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core.config.loader import config_hash
from core.models.s153_v12_contracts import S153V12Input, S153V12Result
from data.database.sqlite_store import SQLiteStore


def _stable_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


class ModelRunRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def feature_snapshot_hash(self, security_id: str, as_of: datetime) -> str:
        rows = self.store.connection.execute(
            """
            SELECT feature_key,value,feature_as_of,available_at,source_phase,source_ref,
                   quality_status,computation_version,evidence_json
            FROM canonical_model_features
            WHERE security_id=? AND feature_as_of<=? AND available_at<=?
            ORDER BY feature_key,feature_as_of,available_at,source_phase,source_ref
            """,
            (security_id,as_of.isoformat(),as_of.isoformat()),
        ).fetchall()
        payload=[dict(r) for r in rows]
        return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()

    def save_v12(
        self,
        data: S153V12Input,
        result: S153V12Result,
        *,
        config_path: str | Path,
    ) -> str:
        analysis_id=str(uuid.uuid4())
        now=datetime.now(timezone.utc).isoformat()
        data_hash=self.feature_snapshot_hash(data.security_id,data.as_of)
        cfg_hash=config_hash(config_path)
        self.store.connection.execute(
            """
            INSERT INTO analysis_runs (
                analysis_id,ticker,security_id,analysis_date,mode,model_version,
                data_snapshot_hash,model_config_hash,score,route,destination,
                prediction,status,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                analysis_id,data.ticker,data.security_id,data.as_of.isoformat(),
                "HISTORICAL" if data.as_of < datetime.now(timezone.utc) else "FORWARD",
                "S15.3_V1.2",data_hash,cfg_hash,result.score,result.primary_route,
                result.verdict,result.verdict,result.status,now,
            ),
        )
        for key,value in result.components.items():
            self.store.connection.execute(
                """
                INSERT INTO model_scores (
                    analysis_id,factor_key,factor_value,availability,evidence_json
                ) VALUES (?,?,?,?,?)
                """,
                (
                    analysis_id,key,value,"AVAILABLE" if value is not None else "N/A",
                    _stable_json({"canonical_model":"S15.3_V1.2"}),
                ),
            )
        for key,value in result.routes.items():
            self.store.connection.execute(
                """
                INSERT INTO model_scores (
                    analysis_id,factor_key,factor_value,availability,evidence_json
                ) VALUES (?,?,?,?,?)
                """,
                (
                    analysis_id,f"ROUTE_{key}",value,"AVAILABLE" if value is not None else "N/A",
                    _stable_json({"canonical_model":"S15.3_V1.2","route":key}),
                ),
            )
        for key,value in result.flags.items():
            self.store.connection.execute(
                """
                INSERT INTO model_scores (
                    analysis_id,factor_key,factor_value,availability,evidence_json
                ) VALUES (?,?,?,?,?)
                """,
                (
                    analysis_id,f"FLAG_{key}",1.0 if value else 0.0,"AVAILABLE",
                    _stable_json({"canonical_model":"S15.3_V1.2","boolean":True}),
                ),
            )
        self.store.connection.commit()
        return analysis_id
