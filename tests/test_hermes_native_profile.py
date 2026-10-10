"""Validate official Hermes isolated-profile template without provider/network calls.

These are static checks only; a passing test does not certify the installed
Hermes version, native child execution, user account quota, or cloud billing.
"""
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "hermes_native_profile.safe.example.yaml"


def test_native_profile_stays_isolated_and_unconfigured():
    raw = CONFIG.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    assert data["terminal"]["cwd"].casefold() == "e:\\m10"
    assert data["terminal"]["home_mode"] == "profile"
    assert data["terminal"]["env_passthrough"] == []
    assert data["delegation"]["max_concurrent_children"] == 1
    assert data["delegation"]["max_spawn_depth"] == 1
    assert data["delegation"]["orchestrator_enabled"] is False
    assert data["skills"]["write_approval"] is True
    assert data["memory"]["write_approval"] is True
    assert data["gateway"]["allow_all_users"] is False
    assert "model" not in data
    assert "provider_routing" not in data
    assert "api_key" not in raw.lower()
    assert "bot_token" not in raw.lower()
    assert "__bindings" not in raw


def test_only_minimal_native_toolsets():
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    actual = set(data["toolsets"])
    assert actual == {
        "skills", "terminal", "delegation", "cronjob",
        "session_search", "code_execution",
    }
    assert not ({"browser", "messaging", "image_gen", "all", "web"} & actual)


def test_six_official_project_skills_exist():
    skills_dir = ROOT / ".agents" / "skills"
    names = [
        "meridyen-chief-strategist", "meridyen-market-discovery",
        "meridyen-fundamentals", "meridyen-catalyst",
        "meridyen-risk", "meridyen-learning",
    ]
    for name in names:
        target = skills_dir / name / "SKILL.md"
        assert target.is_file(), name
        text = target.read_text(encoding="utf-8")
        assert text.startswith("---\nname: ")
        assert f"name: {name}" in text
