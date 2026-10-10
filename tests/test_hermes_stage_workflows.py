from core.hermes_team import evidence_workflows as workflows


def test_missing_stage_is_not_promoted(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    result = workflows._research_stage_status()
    assert result["status"] == "INCONCLUSIVE"
    assert result["reason"] == "NO_PRIVATE_PHASE25Q_STAGE"


def test_ambiguous_stage_does_not_choose_arbitrarily(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    base = tmp_path / "S153ResearchTerminal" / "runtime" / "phase25q" / "staged_datasets"
    (base / "research_pit_a").mkdir(parents=True)
    (base / "research_pit_b").mkdir()
    assert workflows._research_stage_status()["reason"] == "MISSING_OR_AMBIGUOUS_STAGE_VERSION"


def test_real_m10_entrypoint_attaches_readonly_evidence_without_network(monkeypatch):
    """Existing Phase25i output is summarized; no private archive is needed."""
    import json
    from types import SimpleNamespace
    monkeypatch.setattr(workflows.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=0,
        stdout=json.dumps({
            "status": "FULL_CHAIN_REAL_DATA_BLOCKED_NOT_TRAINED",
            "blockers": ["HISTORICAL_IDENTITY_NOT_VERIFIED"],
            "walk_forward_executed": False,
            "Learning_V3_executed": False,
            "db_modified": False,
        }),
    ))
    monkeypatch.setattr(workflows, "_research_stage_status",
                        lambda: {"status": "INCONCLUSIVE", "canonical_pit": False})
    monkeypatch.setattr(workflows, "local_phase25_sources",
                        lambda: {"identity_collisions": {
                            "status": "VERIFIED_EXISTING_SOURCE_REPORT_RESEARCH_ONLY",
                            "canonical_pit": False, "ambiguous_source_rows": 464,
                        }})
    report = workflows.perform_local_evidence_task("learning")
    assert report["status"] == "FULL_CHAIN_REAL_DATA_BLOCKED_NOT_TRAINED"
    assert report["phase25_official_evidence"]["identity_collisions"]["canonical_pit"] is False
    assert report["walk_forward_executed"] is False
    assert report["Learning_V3_executed"] is False
    assert report["llm_called"] is False
