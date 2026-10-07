from datetime import datetime,timezone
from pathlib import Path

from core.historical.wf4_vector_policy import VECTOR_VERSION
from data.database.sqlite_store import SQLiteStore
from data.repositories.s153_historical_control_repository import S153HistoricalControlRepository


NOW=datetime(2024,1,1,tzinfo=timezone.utc)


def test_wf6_excludes_target_security_from_historical_controls(tmp_path: Path) -> None:
    store=SQLiteStore(tmp_path/"leakage.sqlite")
    store.initialize()
    try:
        now=NOW.isoformat()
        for sid in ("SEC_TARGET","SEC_OTHER"):
            store.connection.execute(
                "INSERT INTO security_master (security_id,ticker,name,exchange,market,active,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (sid,sid,sid,"NASDAQ","US",1,now,now),
            )
        store.connection.commit()
        repo=S153HistoricalControlRepository(store)
        for sid in ("SEC_TARGET","SEC_OTHER"):
            repo.save(
                observation_id=sid,
                security_id=sid,
                as_of_date="2022-01-01",
                primary_route="F10",
                feature_vector={"DNA60":80.0},
                magnitude_vector={"DF10":80.0},
                magnitude5_vector={"DF5":80.0},
                fm252=10.5,
                outcome_class="TRUE_10X",
                label_available_at=datetime(2023,1,1,tzinfo=timezone.utc),
                vector_version=VECTOR_VERSION,
            )

        rows=repo.eligible_before(
            NOW,
            vector_version=VECTOR_VERSION,
            exclude_security_id="SEC_TARGET",
        )
        assert [row["security_id"] for row in rows] == ["SEC_OTHER"]
    finally:
        store.close()
