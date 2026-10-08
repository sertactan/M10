from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

import scripts.pit_daily_sync as daily


def fixture_runtime(tmp_path, monkeypatch):
    root = tmp_path / "runtime"
    db = root / "data" / "runtime" / "operational.db"
    db.parent.mkdir(parents=True)
    with sqlite3.connect(db) as con:
        con.execute("""CREATE TABLE universe_snapshot_membership(
            snapshot_date TEXT,security_id TEXT,ticker TEXT,exchange TEXT,source TEXT)""")
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "config" / "app.yaml").write_text("fixture-only")
    monkeypatch.setenv("S153_RUNTIME_ROOT", str(root))
    class FakeApp:
        def __init__(self, project_root):
            self.sqlite = SimpleNamespace(connection=sqlite3.connect(db))
        def initialize(self):
            pass
        def close(self):
            self.sqlite.connection.close()
    class FakeRepository:
        def __init__(self, store):
            self.conn = store.connection
        def universe_as_of(self, day):
            return list(self.conn.execute(
                "SELECT security_id FROM universe_snapshot_membership WHERE snapshot_date=?",
                (day.isoformat(),)))
        def bulk_upsert_historical_snapshot(self, records, *, snapshot_date):
            for ticker in records:
                self.conn.execute(
                    "INSERT INTO universe_snapshot_membership VALUES (?,?,?,?,?)",
                    (snapshot_date.isoformat(), ticker,ticker,"NASDAQ","ALPHAVANTAGE_PIT"))
            self.conn.commit()
            return len(records)
    monkeypatch.setattr(daily, "AppContainer", FakeApp)
    monkeypatch.setattr(daily, "SecurityRepository", FakeRepository)
    monkeypatch.setattr(daily, "AlphaVantagePitUniverseProvider",
                        lambda: SimpleNamespace(configured=True))
    monkeypatch.setattr(daily, "MassiveUniverseProvider", lambda: object())
    return root,db,repo


def at(day):
    return datetime.fromisoformat(day+"T00:30:00+00:00")


def test_daily_cap_no_duplicate_requests_and_resume_next_utc_day(tmp_path,monkeypatch):
    root,db,repo=fixture_runtime(tmp_path,monkeypatch)
    calls=[]
    async def provider(*,as_of,mode,alpha,massive):
        calls.append(as_of.isoformat())
        return [f"SEC-{as_of.isoformat()}"],"ALPHAVANTAGE_PIT"
    monkeypatch.setattr(daily,"_load_snapshot",provider)
    kw=dict(start=date(2013,1,1),end=date(2013,4,30),
            daily_limit=2,repo_root=repo)
    a=asyncio.run(daily.run_daily(root,current_time=at("2026-10-08"),**kw))
    assert a["status"]=="DAILY_REQUEST_BUDGET_REACHED"
    assert a["snapshots_downloaded_this_run"]==2
    assert a["monthly_snapshots_present"]==2
    assert a["monthly_snapshots_missing"]==2
    assert a["api_requests_recorded_today_by_this_tool"]==2
    b=asyncio.run(daily.run_daily(root,current_time=at("2026-10-08"),**kw))
    assert b["snapshots_downloaded_this_run"]==0
    assert calls==["2013-01-31","2013-02-28"]
    c=asyncio.run(daily.run_daily(root,current_time=at("2026-10-09"),**kw))
    assert c["status"]=="COMPLETE_LISTINGS_NOT_PIT_CERTIFIED"
    assert c["monthly_snapshots_present"]==4
    assert c["snapshots_downloaded_this_run"]==2
    assert c["api_requests_recorded_today_by_this_tool"]==2
    assert calls==["2013-01-31","2013-02-28","2013-03-31","2013-04-30"]
    assert c["pit_corporate_actions_fundamentals_prices_certified"] is False
    assert c["wf9_activated"] is False
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM universe_snapshot_membership").fetchone()[0]==4


def test_vendor_failure_stops_without_hammering_and_counts_attempt(tmp_path,monkeypatch):
    root,db,repo=fixture_runtime(tmp_path,monkeypatch)
    calls=[]
    async def rate_limit(*,as_of,mode,alpha,massive):
        calls.append(as_of)
        raise RuntimeError("SECRET-DO-NOT-PRINT vendor limit")
    monkeypatch.setattr(daily,"_load_snapshot",rate_limit)
    kw=dict(start=date(2013,1,1),end=date(2013,3,31),
            daily_limit=1,repo_root=repo)
    result=asyncio.run(daily.run_daily(root,current_time=at("2026-10-08"),**kw))
    assert result["status"]=="PROVIDER_STOPPED_REVIEW_ACCOUNT_OR_QUOTA"
    assert result["first_missing_or_failed_date"]=="2013-01-31"
    assert result["provider_failure_class"]=="RuntimeError"
    assert result["api_requests_recorded_today_by_this_tool"]==1
    assert result["monthly_snapshots_present"]==0
    state=(root/"data/runtime/pit_daily_sync/latest_status.json").read_text()
    assert "SECRET-DO-NOT-PRINT" not in state
    again=asyncio.run(daily.run_daily(root,current_time=at("2026-10-08"),**kw))
    assert again["status"]=="DAILY_REQUEST_BUDGET_REACHED"
    assert len(calls)==1


def test_exclusive_lock_avoids_two_simultaneous_jobs(tmp_path,monkeypatch):
    root,db,repo=fixture_runtime(tmp_path,monkeypatch)
    lock=root/"data/runtime/pit_daily_sync/daily.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("other-owner")
    with pytest.raises(ValueError,match="Another PIT sync"):
        asyncio.run(daily.run_daily(root,repo_root=repo))
    assert lock.read_text()=="other-owner"


def test_corrupt_budget_blocks_all_network_access(tmp_path,monkeypatch):
    root,db,repo=fixture_runtime(tmp_path,monkeypatch)
    state=root/"data/runtime/pit_daily_sync/utc_request_budget.json"
    state.parent.mkdir(parents=True)
    state.write_text('{"schema":"MERIDYEN_DAILY_PIT_SYNC_V1","utc_date":"2026-10-08","attempts":999}')
    requested=[]
    async def impossible(**kwargs):
        requested.append(1)
        raise AssertionError("must not reach provider")
    monkeypatch.setattr(daily,"_load_snapshot",impossible)
    with pytest.raises(ValueError,match="Invalid quota"):
        asyncio.run(daily.run_daily(root,repo_root=repo,current_time=at("2026-10-08")))
    assert not requested
    assert state.exists()


def test_missing_database_refuses_creation(tmp_path,monkeypatch):
    root=tmp_path/"runtime"
    with pytest.raises(ValueError,match="refusing to create"):
        asyncio.run(daily.run_daily(root))
    assert not (root/"data/runtime/operational.db").exists()


def test_daily_cap_is_strictly_bounded():
    today="2026-10-08"
    with pytest.raises(ValueError,match="Daily cap"):
        asyncio.run(daily.run_daily(Path("/nonexistent"),daily_limit=25))


def test_budget_rollover_does_not_allow_clock_rewind(tmp_path):
    p=tmp_path/"quota.json"
    p.write_text(json.dumps({"schema":daily.SCHEMA,"utc_date":"2026-10-10","attempts":5}))
    with pytest.raises(ValueError,match="backwards"):
        daily._read_budget(p,"2026-10-08")
    assert daily._read_budget(p,"2026-10-11")["attempts"]==0


def test_no_pit_canonical_claim_from_synthetic_counts(tmp_path,monkeypatch):
    root,db,repo=fixture_runtime(tmp_path,monkeypatch)
    async def provider(*,as_of,mode,alpha,massive):
        return ["XYZ"],"ALPHAVANTAGE_PIT"
    monkeypatch.setattr(daily,"_load_snapshot",provider)
    result=asyncio.run(daily.run_daily(root,repo_root=repo,daily_limit=1,
                                       start=date(2013,1,1),end=date(2013,1,31),
                                       current_time=at("2026-10-08")))
    assert result["monthly_snapshots_present"]==1
    assert result["status"]=="COMPLETE_LISTINGS_NOT_PIT_CERTIFIED"
    assert result["pit_corporate_actions_fundamentals_prices_certified"] is False
