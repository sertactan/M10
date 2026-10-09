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
