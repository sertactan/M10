from datetime import datetime,timezone,timedelta
from pathlib import Path

from core.historical.wf4_controls import WF4HistoricalControlEngine
from core.historical.wf4_vector_policy import VECTOR_VERSION
from data.database.sqlite_store import SQLiteStore
from data.repositories.s153_historical_control_repository import S153HistoricalControlRepository


NOW=datetime(2024,1,1,tzinfo=timezone.utc)


def _store(tmp_path: Path):
    store=SQLiteStore(tmp_path/"wf4.sqlite"); store.initialize()
    now=NOW.isoformat()
    for i in range(3):
        store.connection.execute(
            "INSERT INTO security_master (security_id,ticker,name,exchange,market,active,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (f"SEC_{i}",f"T{i}",f"T{i}","NASDAQ","US",1,now,now),
        )
    store.connection.commit()
    return store


def test_future_label_is_excluded_until_label_available_at(tmp_path: Path) -> None:
    store=_store(tmp_path)
    try:
        repo=S153HistoricalControlRepository(store)
        common=dict(
            primary_route="F10",
            vector_version=VECTOR_VERSION,
            source_run_id="R1",
        )
        repo.save(
            observation_id="W",security_id="SEC_0",as_of_date="2022-01-01",
            feature_vector={"DNA60":90.0},magnitude_vector={"DF10":90.0},
            fm252=10.5,outcome_class="TRUE_10X",
            label_available_at=NOW-timedelta(days=1),**common,
        )
        repo.save(
            observation_id="N",security_id="SEC_1",as_of_date="2022-01-01",
            feature_vector={"DNA60":70.0},magnitude_vector={"DF10":70.0},
            fm252=8.0,outcome_class="NEAR_MISS_10X",
            label_available_at=NOW-timedelta(days=1),**common,
        )
        repo.save(
            observation_id="FUTURE_HARD",security_id="SEC_2",as_of_date="2023-12-01",
            feature_vector={"DNA60":10.0},magnitude_vector={"DF10":10.0},
            fm252=1.2,outcome_class="FAILURE",
            label_available_at=NOW+timedelta(days=100),**common,
        )
        result=WF4HistoricalControlEngine(repo).compute(
            as_of=NOW,
            broad_target={"DNA60":88.0},
            magnitude10_target={"DF10":88.0},
        )
        assert result["WF4_TRUE10_N"] == 1.0
        assert result["WF4_HARD_N"] == 0.0
        assert result["H10"] is None
        assert result["HMG10"] is None
    finally:
        store.close()
