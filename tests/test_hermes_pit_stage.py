import json
import sqlite3

from core.hermes_team.pit_stage import audit_stage


def _fixture(tmp_path):
    root = tmp_path / "research_pit_fixture"
    root.mkdir()
    database = root / "research_pit.sqlite"
    with sqlite3.connect(database) as con:
        con.execute("CREATE TABLE monthly_research_membership(month_end TEXT)")
        con.execute("CREATE TABLE source_daily_price(trade_date TEXT)")
        con.execute("CREATE TABLE candidate_gate(canonical_approved INTEGER)")
        con.executemany("INSERT INTO monthly_research_membership VALUES(?)",
                        [(f"2025-{m:02d}-01",) for m in range(1, 13)]
                        + [(f"2024-{m:02d}-01",) for m in range(4, 13)])
        con.execute("INSERT INTO source_daily_price VALUES('2025-01-01')")
        con.executemany("INSERT INTO candidate_gate VALUES(0)", [()] * 133)
    data = {
        "schema": "MERIDYEN_PHASE25Q_VERSIONED_RESEARCH_STAGING_V1",
        "status": "RESEARCH_ONLY_NOT_CANONICAL_PIT",
        "month_end_snapshots": 21,
        "phase25k_research_gate_rows": 133,
        "independent_PIT_identity_certs": 0,
        "independent_adjusted_price_certs": 0,
        "backtest_eligible_securities": 0,
        "canonical_ready": False,
        "WF9_executed": False,
        "Learning_V3_executed": False,
        "monthly_membership_rows": 21,
        "source_daily_valid_price_rows": 1,
        "staging_version": "fixture_only",
    }
    (root / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    return root


def test_independent_private_fixture_is_readonly(tmp_path):
    root = _fixture(tmp_path)
    result = audit_stage(root)
    assert result["status"] == "SOURCE_STAGING_VERIFIED_RESEARCH_ONLY"
    assert result["months"] == 21
    assert result["counts"]["research_gates"] == 133
    assert result["canonical_pit"] is False


def test_manifest_mismatch_fails_closed(tmp_path):
    root = _fixture(tmp_path)
    manifest = root / "manifest.json"
    data = json.loads(manifest.read_text())
    data["canonical_ready"] = True
    manifest.write_text(json.dumps(data))
    assert audit_stage(root)["status"] == "INCONCLUSIVE"


def test_stage_missing_blocks(tmp_path):
    assert audit_stage(tmp_path / "missing")["reason"] == "RESEARCH_STAGE_MISSING"
