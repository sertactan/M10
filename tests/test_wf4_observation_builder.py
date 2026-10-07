from datetime import date,datetime,timezone
from pathlib import Path

from core.backtest.contracts import ForwardOutcome
from core.historical.wf4_observation_builder import WF4HistoricalObservationBuilder
from core.historical.wf4_vector_policy import VECTOR_VERSION
from core.models.s153_v12_contracts import S153V12Result
from data.database.sqlite_store import SQLiteStore
from data.repositories.s153_historical_control_repository import S153HistoricalControlRepository


AS_OF=datetime(2022,1,31,23,59,tzinfo=timezone.utc)


def _result():
    return S153V12Result(
        security_id="SEC_TEST",ticker="TEST",as_of=AS_OF,
        score=80,status="HIGH_SCORE_NOT_CONFIRMED",verdict=None,
        primary_route="F10",secondary_route="I10",route_gate=True,
        confidence=80,precision_confirmed=False,strong_watch=True,discovery=True,
        components={
            "DNA60":80.0,"RB":82.0,"U":70.0,"A":75.0,"C":80.0,"M":65.0,
            "G":60.0,"V":90.0,"ETRQ":75.0,"RER":70.0,"CMAG":80.0,"FCVX":60.0,
            "DF5":90.0,"MCH5":85.0,"DF10":70.0,"MCH10":65.0,
        },
        routes={"F10":85.0},flags={},missing_requirements=(),
    )


def _outcome(status="READY"):
    return ForwardOutcome(
        security_id="SEC_TEST",
        as_of_date_requested=AS_OF.date(),
        anchor_session=AS_OF.date(),
        anchor_lag_calendar_days=0,
        entry_adjusted_close=10.0,
        horizon_sessions_available=252,
        fm252=10.5 if status=="READY" else None,
        max_multiple_observed=10.5 if status=="READY" else 2.0,
        outcome_class="TRUE_10X" if status=="READY" else None,
        outcome_status=status,
        diagnostics={},
    )


def test_wf4_observation_builder_persists_distinct_5x_and_10x_vectors(tmp_path: Path) -> None:
    store=SQLiteStore(tmp_path/"wf4-builder.sqlite"); store.initialize()
    try:
        now=AS_OF.isoformat()
        store.connection.execute(
            "INSERT INTO security_master (security_id,ticker,name,exchange,market,active,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
            ("SEC_TEST","TEST","Test","NASDAQ","US",1,now,now),
        )
        store.connection.commit()
        repo=S153HistoricalControlRepository(store)
        ok=WF4HistoricalObservationBuilder(repo).save_ready(
            observation_id="OBS1",result=_result(),outcome=_outcome(),
            label_available_at=datetime(2023,1,31,tzinfo=timezone.utc),
            source_run_id="RUN1",
        )
        assert ok is True
        rows=repo.eligible_before(datetime(2024,1,1,tzinfo=timezone.utc),vector_version=VECTOR_VERSION)
        assert len(rows)==1
        assert rows[0]["magnitude5_vector"]["DF5"] == 90.0
        assert rows[0]["magnitude_vector"]["DF10"] == 70.0
    finally:
        store.close()


def test_wf4_observation_builder_rejects_nonready_outcome(tmp_path: Path) -> None:
    store=SQLiteStore(tmp_path/"wf4-builder2.sqlite"); store.initialize()
    try:
        now=AS_OF.isoformat()
        store.connection.execute(
            "INSERT INTO security_master (security_id,ticker,name,exchange,market,active,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
            ("SEC_TEST","TEST","Test","NASDAQ","US",1,now,now),
        )
        store.connection.commit()
        repo=S153HistoricalControlRepository(store)
        ok=WF4HistoricalObservationBuilder(repo).save_ready(
            observation_id="OBS1",result=_result(),outcome=_outcome("PARTIAL"),
            label_available_at=datetime(2023,1,31,tzinfo=timezone.utc),
        )
        assert ok is False
        assert repo.eligible_before(datetime(2024,1,1,tzinfo=timezone.utc),vector_version=VECTOR_VERSION)==[]
    finally:
        store.close()
