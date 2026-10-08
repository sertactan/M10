from __future__ import annotations

import json
import sqlite3
from pathlib import Path
import pytest
from core.learning_v2.journal import connect,learn_backtest,audit,backup


def _event(ticker="INOD",completed=True,source="2024-01-02"):
    return {"ticker":ticker,"model_version":"TEST_V1","signal_date":"2024-01-02",
       "source_as_of":source,"horizon_sessions":21,"completed":completed,
       "terminal_return":0.75 if completed else None,
       "hit_10x":False if completed else None}


def _json(tmp_path, events):
    p=tmp_path/"backtest.json"
    p.write_text(json.dumps({"metadata":{"as_of":"2024-12-31","pit_verified":False},
       "events":events}),encoding="utf8")
    return p


def test_learning_v2_import_idempotent_and_censored(tmp_path):
    db=tmp_path/"private.sqlite3"
    src=_json(tmp_path,[_event(),_event("TMDX",False)])
    first=learn_backtest(db,src,"2026-10-08")
    second=learn_backtest(db,src,"2026-10-08")
    assert first["status"]=="IMPORTED"
    assert second["status"]=="DUPLICATE"
    assert first["n_completed"]==1
    assert first["n_censored"]==1
    state=audit(db)
    assert state["sources"]==1 and state["events"]==2
    assert state["canonical_models_modified"] is False


def test_learning_v2_rejects_future_source(tmp_path):
    db=tmp_path/"private.sqlite3"
    src=_json(tmp_path,[_event(source="2024-01-03")])
    with pytest.raises(ValueError,match="lookahead"):
        learn_backtest(db,src,"2026-10-08")
    c=connect(db)
    assert c.execute("SELECT COUNT(*) FROM learning_v2_sources").fetchone()[0]==0
    c.close()


def test_learning_v2_online_backup_is_consistent(tmp_path):
    db=tmp_path/"private.sqlite3"
    c=connect(db);c.close()
    data=backup(db,tmp_path/"backups")
    assert data["integrity"]=="ok"
    assert data["storage_status"]=="LOCAL_BACKUP_ONLY_NOT_UPLOADED"
    original=sqlite3.connect(db)
    copy=sqlite3.connect(data["file"])
    assert copy.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
    assert original.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
    original.close()
    copy.close()
