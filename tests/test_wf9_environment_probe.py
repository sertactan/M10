from scripts.wf9_environment_probe import build_probe


def test_environment_probe_exposes_only_capabilities(monkeypatch):
    monkeypatch.setenv("ALPHAVANTAGE_API_KEY","secret-value")
    monkeypatch.delenv("MASSIVE_API_KEY",raising=False)
    monkeypatch.delenv("WINDOWS_CODESIGN_PFX_BASE64",raising=False)
    monkeypatch.delenv("WINDOWS_CODESIGN_PASSWORD",raising=False)
    payload=build_probe()
    assert payload["pit_universe"]["alphavantage_api_key"] is True
    assert payload["pit_universe"]["massive_api_key"] is False
    assert payload["code_signing"]["pfx_base64"] is False
    rendered=str(payload)
    assert "secret-value" not in rendered
