from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from core.features.destination_materializer import DestinationFeatureMaterializer
from data.database.sqlite_store import SQLiteStore
from data.repositories.model_feature_repository import ModelFeatureRepository


ROOT = Path(__file__).resolve().parents[1]
AS_OF = datetime(2026, 8, 20, 23, 59, tzinfo=timezone.utc)


def _store(tmp_path: Path) -> tuple[SQLiteStore, ModelFeatureRepository]:
    store = SQLiteStore(tmp_path / "dest.sqlite")
    store.initialize(ROOT / "data" / "database" / "schema.sql")
    now = AS_OF.isoformat()
    store.connection.execute(
        """
        INSERT INTO security_master
        (security_id,ticker,name,exchange,market,active,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        ("SEC_TEST","TEST","Test","NASDAQ","US",1,now,now),
    )
    store.connection.commit()
    return store, ModelFeatureRepository(store)


def _save(repo: ModelFeatureRepository, key: str, value: float) -> None:
    repo.save_feature(
        security_id="SEC_TEST",
        feature_key=key,
        value=value,
        feature_as_of=AS_OF,
        available_at=AS_OF,
        source_phase="DERIVED_CANONICAL",
        source_ref="RAW_TEST",
        quality_status="CANONICAL_DERIVED",
        computation_version="raw-test",
        evidence={},
    )


def test_destination_materializer_writes_supported_mc_and_ceiling(tmp_path: Path) -> None:
    store, repo = _store(tmp_path)
    try:
        raw = {
            "RAW_FWD_REVENUE_12": 100.0,
            "RAW_FWD_EBITDA_12": 20.0,
            "RAW_FWD_FCF_12": 10.0,
            "RAW_NET_DEBT": 100.0,
            "PEER_P90_SALES_MULTIPLE": 12.0,
            "PEER_MEDIAN_SALES_MULTIPLE": 5.0,
            "PEER_P90_EBITDA_MULTIPLE": 30.0,
            "PEER_MEDIAN_EBITDA_MULTIPLE": 20.0,
            "PEER_P90_FCF_MULTIPLE": 40.0,
            "PEER_MEDIAN_FCF_MULTIPLE": 25.0,
            "ROUTE_PEER_P99_MARKET_CAP": 5000.0,
            "ROUTE_PEER_N": 30.0,
            "EVIDENCE_BACKED_COMPARABLE_MC": 4200.0,
        }
        for key, value in raw.items():
            _save(repo, key, value)

        written = DestinationFeatureMaterializer(repo).materialize(
            security_id="SEC_TEST",
            as_of=AS_OF,
        )
        assert set(written) == {"SUPPORTED_MC_12_FI", "PLAUSIBLE_CEILING_MC"}
        rows = repo.load_as_of("SEC_TEST", AS_OF)
        # Sales multiple capped to 10 -> 900 equity;
        # EBITDA=600-100=500; FCF=400; median=500.
        assert rows["SUPPORTED_MC_12_FI"]["value"] == 500.0
        assert rows["PLAUSIBLE_CEILING_MC"]["value"] == 5000.0
    finally:
        store.close()


def test_destination_materializer_fails_closed_without_peer_or_forward_evidence(tmp_path: Path) -> None:
    store, repo = _store(tmp_path)
    try:
        written = DestinationFeatureMaterializer(repo).materialize(
            security_id="SEC_TEST",
            as_of=AS_OF,
        )
        assert written == {}
    finally:
        store.close()



def test_destination_materializer_writes_distressed_and_biotech_supported_mc(tmp_path: Path) -> None:
    store, repo = _store(tmp_path)
    try:
        raw = {
            "RAW_NORMALIZED_EBITDA_12": 100.0,
            "RAW_DISTRESSED_PEER_MULTIPLE": 8.0,
            "RAW_POST_RESTRUCTURING_NET_DEBT": 200.0,
            "RAW_RESTRUCTURING_EVIDENCE_FACTOR": 0.80,
            "RAW_RNPV_PIPELINE": 750.0,
            "RAW_NET_CASH": 250.0,
        }
        for key, value in raw.items():
            _save(repo, key, value)

        written = DestinationFeatureMaterializer(repo).materialize(
            security_id="SEC_TEST",
            as_of=AS_OF,
        )
        assert "SUPPORTED_MC_12_D" in written
        assert "SUPPORTED_MC_12_B" in written
        rows = repo.load_as_of("SEC_TEST", AS_OF)
        assert rows["SUPPORTED_MC_12_D"]["value"] == 480.0
        assert rows["SUPPORTED_MC_12_B"]["value"] == 1000.0
    finally:
        store.close()
