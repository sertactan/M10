from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from core.features.s153_v12_input_loader import S153V12InputLoader
from data.database.sqlite_store import SQLiteStore
from data.repositories.model_feature_repository import ModelFeatureRepository


AS_OF=datetime(2026,8,20,23,59,tzinfo=timezone.utc)


def _save(repo: ModelFeatureRepository, key: str, value: float) -> None:
    repo.save_feature(
        security_id="SEC_TEST",feature_key=key,value=value,
        feature_as_of=AS_OF,available_at=AS_OF,
        source_phase="DERIVED_CANONICAL",source_ref="test",
        quality_status="CANONICAL_DERIVED",computation_version="test",evidence={},
    )


def test_v12_loader_excludes_raw_and_peer_evidence_but_keeps_destination_inputs(tmp_path: Path) -> None:
    store=SQLiteStore(tmp_path/"loader.sqlite"); store.initialize()
    try:
        repo=ModelFeatureRepository(store)
        for key,value in {
            "RAW_CURRENT_PRICE":10.0,
            "RAW_CURRENT_MARKET_CAP":100.0,
            "RAW_EV_TO_SALES_TTM":250.0,
            "PEER_P90_SALES_MULTIPLE":150.0,
            "ROUTE_PEER_P99_MARKET_CAP":5000.0,
            "EVIDENCE_BACKED_COMPARABLE_MC":4000.0,
            "SUPPORTED_MC_12_FI":900.0,
            "PLAUSIBLE_CEILING_MC":5000.0,
            "DATA_COVERAGE":90.0,
        }.items():
            _save(repo,key,value)

        data=S153V12InputLoader(repo).load(
            security_id="SEC_TEST",ticker="TEST",as_of=AS_OF
        )
        assert "RAW_EV_TO_SALES_TTM" not in data.features
        assert "PEER_P90_SALES_MULTIPLE" not in data.features
        assert "ROUTE_PEER_P99_MARKET_CAP" not in data.features
        assert "EVIDENCE_BACKED_COMPARABLE_MC" not in data.features
        assert data.features["SUPPORTED_MC_12_FI"] == 900.0
        assert data.features["PLAUSIBLE_CEILING_MC"] == 5000.0
        assert data.features["DATA_COVERAGE"] == 90.0
    finally:
        store.close()
