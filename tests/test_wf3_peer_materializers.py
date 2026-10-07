from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from core.features.peer_cohort import PeerObservation
from core.features.peer_stats_materializer import DestinationPeerStatsMaterializer
from core.features.peer_observation_materializer import DestinationPeerObservationMaterializer
from data.database.sqlite_store import SQLiteStore
from data.repositories.destination_peer_repository import DestinationPeerRepository
from data.repositories.model_feature_repository import ModelFeatureRepository


AS_OF=datetime(2024,6,30,23,59,tzinfo=timezone.utc)


def _insert_security(store: SQLiteStore, sid: str, ticker: str = "T") -> None:
    now=AS_OF.isoformat()
    store.connection.execute(
        """
        INSERT INTO security_master
        (security_id,ticker,name,exchange,market,sector,industry,active,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (sid,ticker,ticker,"NASDAQ","US","Technology","Software",1,now,now),
    )
    store.connection.commit()


def _save_feature(repo: ModelFeatureRepository,sid: str,key: str,value: float) -> None:
    repo.save_feature(
        security_id=sid,feature_key=key,value=value,
        feature_as_of=AS_OF,available_at=AS_OF,
        source_phase="DERIVED_CANONICAL",source_ref="test",
        quality_status="CANONICAL_DERIVED",computation_version="test",evidence={},
    )


def test_peer_observation_materializer_requires_explicit_bucket_and_state(tmp_path: Path) -> None:
    store=SQLiteStore(tmp_path/"obs.sqlite"); store.initialize()
    try:
        _insert_security(store,"SEC_T","T")
        features=ModelFeatureRepository(store)
        peers=DestinationPeerRepository(store)
        _save_feature(features,"SEC_T","RAW_CURRENT_MARKET_CAP",1000.0)
        _save_feature(features,"SEC_T","RAW_EV_TO_SALES_TTM",5.0)
        m=DestinationPeerObservationMaterializer(store,features,peers)
        assert m.materialize(security_id="SEC_T",route="F10",as_of=AS_OF,market_cap_bucket="",profitability_state="STATE_A") is None
        oid=m.materialize(security_id="SEC_T",route="F10",as_of=AS_OF,market_cap_bucket="BUCKET_A",profitability_state="STATE_A")
        assert oid is not None
        row=peers.load_month(as_of_month="2024-06",as_of=AS_OF)[0]
        assert row.sales_multiple == 5.0
    finally:
        store.close()


def test_peer_stats_materializer_writes_p90_median_and_route_p99(tmp_path: Path) -> None:
    store=SQLiteStore(tmp_path/"stats.sqlite"); store.initialize()
    try:
        features=ModelFeatureRepository(store)
        peers=DestinationPeerRepository(store)
        for i in range(51):
            sid=f"SEC_{i}"
            _insert_security(store,sid,str(i))
            peers.save(
                security_id=sid,as_of_month="2024-06",route="F10",
                sector="Technology",industry="Software",
                market_cap_bucket="BUCKET_A",profitability_state="STATE_A",
                market_cap=1000+i,sales_multiple=5+i/100,
                ebitda_multiple=15+i/100,fcf_multiple=25+i/100,
                feature_as_of=AS_OF,available_at=AS_OF,
                source_ref="test",computation_version="test",
            )
        target=PeerObservation(
            security_id="SEC_50",as_of_month="2024-06",route="F10",
            sector="Technology",industry="Software",
            market_cap_bucket="BUCKET_A",profitability_state="STATE_A",
        )
        written=DestinationPeerStatsMaterializer(peers,features).materialize(target=target,as_of=AS_OF)
        assert "PEER_P90_SALES_MULTIPLE" in written
        assert "PEER_MEDIAN_SALES_MULTIPLE" in written
        assert "ROUTE_PEER_P99_MARKET_CAP" in written
        assert "ROUTE_PEER_N" in written
        rows=features.load_as_of("SEC_50",AS_OF)
        assert rows["ROUTE_PEER_N"]["value"] == 50.0
    finally:
        store.close()
