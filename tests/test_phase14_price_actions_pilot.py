from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
import sqlite3
from types import SimpleNamespace

import pytest

from core.prices.models import (
    AdjustmentStatus, DividendEvent, PriceQualityStatus, SourcePriceBar,
    SplitEvent,
)
from data.database.sqlite_store import SQLiteStore
import scripts.phase14_price_actions_pilot as m

NOW=datetime(2026,10,8,tzinfo=timezone.utc)
START=date(2013,1,1)
END=date(2015,1,31)


def setup_db(tmp_path, monkeypatch):
    repo=tmp_path/"repo"
    repo.mkdir()
    runtime=tmp_path/"installed"
    db=runtime/"data/runtime/operational.db"
    store=SQLiteStore(db)
    store.initialize()
    store.connection.execute(
        """INSERT INTO security_master
           (security_id,ticker,name,exchange,market,active,created_at,updated_at)
           VALUES ('S','INOD','Innodata Inc','NASDAQ','US',1,?,?)""",
        (NOW.isoformat(),NOW.isoformat())
    )
    store.connection.commit()
    store.close()

    class FakeApp:
        def __init__(self, root):
            self.sqlite=SQLiteStore(db)
            self.app_config=SimpleNamespace(
                database=SimpleNamespace(parquet_root="data/runtime/parquet"))
        def initialize(self):
            self.sqlite.initialize(recover_corrupt=False)
        def close(self):
            self.sqlite.close()
        def resolve_data_path(self, path):
            return runtime / path

    monkeypatch.setattr(m,"AppContainer",FakeApp)
    monkeypatch.setattr(m,"load_local_env",lambda p:None)
    return repo,runtime,db


def price():
    return SourcePriceBar(
        security_id="S",source="MASSIVE",source_symbol="INOD",
        trade_date=date(2013,1,31),open=12,high=13,low=11,
        raw_close=12,adjusted_close=6,volume=1000,retrieved_at=NOW,
        quality_status=PriceQualityStatus.PRIMARY,
        adjustment_status=AdjustmentStatus.DUAL_RAW_ADJUSTED,
    )


class FakeMassive:
    configured=True
    async def get_history(self,sec,start,end):
        return [price()]
    async def get_splits(self,sec,start,end):
        return [SplitEvent("S","MASSIVE","INOD",date(2014,1,1),1,2,
                           NOW,PriceQualityStatus.PRIMARY)]
    async def get_dividends(self,sec,start,end):
        return [DividendEvent("S","MASSIVE","INOD",date(2014,2,1),0.1,
                              "USD",NOW,PriceQualityStatus.PRIMARY)]


def run(repo,runtime,execute=False):
    return asyncio.run(m.pilot(
        runtime_root=runtime,repo_root=repo,ticker="INOD",
        start=START,end=END,provider_name="MASSIVE",execute=execute
    ))


def test_preview_read_only_and_never_requests_provider(tmp_path,monkeypatch):
    repo,runtime,db=setup_db(tmp_path,monkeypatch)
    class Deny(FakeMassive):
        async def get_history(self,*a):
            raise AssertionError("Preview must not make API requests")
    monkeypatch.setattr(m,"make_provider",lambda x:Deny())
    monkeypatch.setattr(m,"MassivePriceProvider",Deny)
    result=run(repo,runtime)
    assert result["status"]=="READ_ONLY_PREVIEW"
    assert not list(runtime.rglob("*.parquet"))
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM canonical_price_selection").fetchone()[0]==0


def test_execute_saves_price_split_dividend_without_wf9_activation(tmp_path,monkeypatch):
    repo,runtime,db=setup_db(tmp_path,monkeypatch)
    monkeypatch.setattr(m,"make_provider",lambda name:FakeMassive())
    monkeypatch.setattr(m,"MassivePriceProvider",FakeMassive)
    result=run(repo,runtime,execute=True)
    assert result["status"]=="PARTIAL_IMPORTED_DELISTING_AND_PIT_UNVERIFIED"
    assert result["adjusted_price_bars_saved"]==1
    assert result["splits_saved"]==1
    assert result["dividends_saved"]==1
    assert result["delisting_consideration_status"]=="NOT_AVAILABLE_UNVERIFIED"
    assert result["wf9_activated"] is False
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM split_events_source").fetchone()[0]==1
        assert conn.execute("SELECT COUNT(*) FROM dividend_events_source").fetchone()[0]==1
        row=conn.execute("SELECT purpose FROM canonical_price_selection").fetchone()
        assert row[0]=="PHASE14_ADJUSTED_PILOT_UNVERIFIED"
        assert conn.execute("SELECT COUNT(*) FROM price_series_registry").fetchone()[0]==1
    assert list(runtime.rglob("*.parquet"))


def test_missing_actions_provider_refuses_all_writes(tmp_path,monkeypatch):
    repo,runtime,db=setup_db(tmp_path,monkeypatch)
    monkeypatch.setattr(m,"make_provider",lambda name:FakeMassive())
    class NoActions(FakeMassive):
        configured=False
    monkeypatch.setattr(m,"MassivePriceProvider",NoActions)
    with pytest.raises(ValueError,match="Massive corporate actions"):
        run(repo,runtime,execute=True)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM canonical_price_selection").fetchone()[0]==0


def test_raw_price_rejected_before_all_writes(tmp_path,monkeypatch):
    repo,runtime,db=setup_db(tmp_path,monkeypatch)
    class Raw(FakeMassive):
        async def get_history(self,sec,start,end):
            from dataclasses import replace
            return [replace(price(),adjustment_status=AdjustmentStatus.RAW_ONLY)]
    monkeypatch.setattr(m,"make_provider",lambda name:Raw())
    monkeypatch.setattr(m,"MassivePriceProvider",FakeMassive)
    with pytest.raises(ValueError,match="Raw-only"):
        run(repo,runtime,execute=True)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM canonical_price_selection").fetchone()[0]==0
        assert conn.execute("SELECT COUNT(*) FROM split_events_source").fetchone()[0]==0


def test_ticker_reuse_is_not_auto_merged(tmp_path,monkeypatch):
    repo,runtime,db=setup_db(tmp_path,monkeypatch)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """INSERT INTO security_master
               (security_id,ticker,name,exchange,market,active,created_at,updated_at)
               VALUES ('S-OLD','INOD','Other issuer','NYSE','US',0,?,?)""",
            (NOW.isoformat(),NOW.isoformat()),
        )
    with pytest.raises(ValueError,match="Multiple historical security IDs"):
        run(repo,runtime)
    assert not list(runtime.rglob("*.parquet"))


def test_db_missing_fails_without_creation(tmp_path):
    with pytest.raises(ValueError,match="Existing M10"):
        asyncio.run(m.pilot(
            runtime_root=tmp_path/"missing",repo_root=tmp_path,
            ticker="INOD",start=START,end=END,provider_name="MASSIVE",
        ))
