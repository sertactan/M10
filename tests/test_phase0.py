from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.bootstrap import AppContainer
from core.config.loader import load_yaml
from core.config.models import ModelConfig
from core.models.base import ModelInput, ModelNotImplemented, S153ModelBase
from core.pit.availability import is_available, require_pit_safe
from data.database.sqlite_store import SQLiteStore
from data.repositories.pit_repository import PITRepository


ROOT = Path(__file__).resolve().parents[1]


def test_configs_fail_closed_until_canonical_model_phase() -> None:
    v12 = load_yaml(ROOT / "config" / "s153_v12.yaml", ModelConfig)
    v14 = load_yaml(ROOT / "config" / "s153_v14.yaml", ModelConfig)
    assert v12.enabled is False
    assert v14.enabled is False
    with pytest.raises(ModelNotImplemented):
        S153ModelBase(v12).analyze(
            ModelInput(
                security_id="SEC_TEST",
                ticker="TEST",
                as_of=datetime(2025, 5, 5, tzinfo=timezone.utc),
                factors={},
            )
        )


def test_pit_guard_blocks_future_availability() -> None:
    as_of = datetime(2025, 5, 5, 23, 59, tzinfo=timezone.utc)
    old = datetime(2025, 5, 5, 20, 0, tzinfo=timezone.utc)
    future = datetime(2025, 5, 6, 1, 0, tzinfo=timezone.utc)
    assert is_available(old, as_of)
    assert not is_available(future, as_of)
    with pytest.raises(ValueError, match="LOOK_AHEAD_BLOCKED"):
        require_pit_safe(future, as_of)


def _seed_security(store: SQLiteStore) -> None:
    now = datetime.now(timezone.utc).isoformat()
    store.connection.execute(
        """
        INSERT INTO security_master
        (security_id,ticker,name,exchange,market,active,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        ("SEC_TEST", "TEST", "Test Corp", "NASDAQ", "US", 1, now, now),
    )
    store.connection.commit()


def test_sqlite_schema_initializes(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "operational.db")
    store.initialize(ROOT / "data" / "database" / "schema.sql")
    names = {
        row[0]
        for row in store.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"security_master", "financial_facts", "analysis_runs", "backtest_results"} <= names
    store.close()


def test_financial_fact_query_excludes_future_revision(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "operational.db")
    store.initialize(ROOT / "data" / "database" / "schema.sql")
    _seed_security(store)
    repo = PITRepository(store)
    base = (
        "SEC_TEST", "REVENUE", 100.0, "USD", "Q1", 2025, "2025-03-31",
        "2025-04-30T20:00:00+00:00", "SEC", "10-Q", None,
        "2025-04-30T20:01:00+00:00", json.dumps({})
    )
    future = list(base)
    future[2] = 150.0
    future[7] = "2025-05-06T20:00:00+00:00"
    future[11] = "2025-05-06T20:01:00+00:00"
    insert = """
        INSERT INTO financial_facts
        (fact_id,security_id,fact_key,value,unit,fiscal_period,fiscal_year,period_date,
         filing_date,availability_date,provider,source,source_url,ingested_at,raw_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    store.connection.execute(insert, (str(uuid.uuid4()),) + base[:7] + (base[7],) + base[7:])
    store.connection.execute(insert, (str(uuid.uuid4()),) + tuple(future[:7]) + (future[7],) + tuple(future[7:]))
    store.connection.commit()
    rows = repo.financial_facts_as_of(
        "SEC_TEST", datetime(2025, 5, 5, 23, 59, tzinfo=timezone.utc)
    )
    assert len(rows) == 1
    assert rows[0]["value"] == 100.0
    store.close()


def test_analysis_run_requires_reproducibility_fields(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "operational.db")
    store.initialize(ROOT / "data" / "database" / "schema.sql")
    _seed_security(store)
    repo = PITRepository(store)
    with pytest.raises(ValueError):
        repo.save_analysis_run({"analysis_id": "A1"})

    repo.save_analysis_run({
        "analysis_id": "A1",
        "ticker": "TEST",
        "security_id": "SEC_TEST",
        "analysis_date": "2025-05-05",
        "mode": "HISTORICAL",
        "model_version": "S15.3_V1.2",
        "data_snapshot_hash": "datahash",
        "model_config_hash": "confighash",
        "status": "NOT_IMPLEMENTED",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    row = store.connection.execute(
        "SELECT data_snapshot_hash, model_config_hash FROM analysis_runs WHERE analysis_id='A1'"
    ).fetchone()
    assert row["data_snapshot_hash"] == "datahash"
    assert row["model_config_hash"] == "confighash"
    store.close()


def test_bootstrap_forbids_mock_data(tmp_path: Path) -> None:
    app = AppContainer(ROOT)
    assert app.app_config.allow_mock_data is False
    assert app.app_config.strict_pit is True
