from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from core.features.peer_cohort import (
    PeerObservation,
    evaluate_exact_peer_cohort,
)
from data.database.sqlite_store import SQLiteStore
from data.repositories.destination_peer_repository import DestinationPeerRepository


AS_OF=datetime(2024,6,30,23,59,tzinfo=timezone.utc)


def _obs(i: int, *, sales=5.0, ebitda=15.0, fcf=25.0, mc=1_000.0):
    return PeerObservation(
        security_id=f"SEC_{i}",
        as_of_month="2024-06",
        route="F10",
        sector="Technology",
        industry="Software",
        market_cap_bucket="BUCKET_A",
        profitability_state="STATE_A",
        market_cap=mc+i,
        sales_multiple=sales+i/100.0,
        ebitda_multiple=(None if ebitda is None else ebitda+i/100.0),
        fcf_multiple=(None if fcf is None else fcf+i/100.0),
    )


def test_exact_peer_cohort_normal_at_50_and_excludes_target() -> None:
    target=_obs(999)
    peers=[_obs(i) for i in range(50)]
    result=evaluate_exact_peer_cohort(target,peers+[target])
    assert result.cohort_n == 50
    assert result.cohort_status == "NORMAL"
    assert result.sales.n == 50
    assert result.sales.median is not None
    assert result.sales.p90 is not None
    assert result.market_cap.p99 is not None
    assert result.blockers == ()


def test_exact_peer_cohort_30_to_49_is_low_confidence() -> None:
    result=evaluate_exact_peer_cohort(_obs(999),[_obs(i) for i in range(35)])
    assert result.cohort_n == 35
    assert result.cohort_status == "LOW_CONFIDENCE_N_30_49"
    assert result.sales.status == "LOW_CONFIDENCE_N_30_49"


def test_peer_n_under_30_fails_closed_without_invented_expansion() -> None:
    result=evaluate_exact_peer_cohort(_obs(999),[_obs(i) for i in range(29)])
    assert result.cohort_status == "EXPANSION_REQUIRED_RULE_UNSPECIFIED"
    assert result.sales.p90 is None
    assert "PEER_EXPANSION_RULE_UNSPECIFIED" in result.blockers


def test_metric_specific_n_must_reach_30() -> None:
    peers=[
        _obs(i,ebitda=(15.0 if i < 29 else None))
        for i in range(50)
    ]
    result=evaluate_exact_peer_cohort(_obs(999),peers)
    assert result.cohort_n == 50
    assert result.sales.p90 is not None
    assert result.ebitda.n == 29
    assert result.ebitda.p90 is None
    assert "EBITDA_MULTIPLE_PEER_N_LT_30" in result.blockers


def test_destination_peer_repository_preserves_pit_and_classifications(tmp_path: Path) -> None:
    store=SQLiteStore(tmp_path/"peer.sqlite")
    store.initialize()
    try:
        now=AS_OF.isoformat()
        store.connection.execute(
            """
            INSERT INTO security_master
            (security_id,ticker,name,exchange,market,active,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            ("SEC_1","AAA","AAA","NASDAQ","US",1,now,now),
        )
        store.connection.commit()
        repo=DestinationPeerRepository(store)
        repo.save(
            security_id="SEC_1",as_of_month="2024-06",route="F10",
            sector="Technology",industry="Software",
            market_cap_bucket="BUCKET_A",profitability_state="STATE_A",
            market_cap=1000.0,sales_multiple=5.0,ebitda_multiple=15.0,
            fcf_multiple=25.0,feature_as_of=AS_OF,available_at=AS_OF,
            source_ref="test",computation_version="wf3-test",
        )
        rows=repo.load_month(as_of_month="2024-06",as_of=AS_OF)
        assert len(rows)==1
        assert rows[0].sales_multiple == 5.0
        assert rows[0].market_cap_bucket == "BUCKET_A"
    finally:
        store.close()
