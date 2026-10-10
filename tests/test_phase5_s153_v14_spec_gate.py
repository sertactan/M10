from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

import pytest

from core.config.loader import load_yaml
from core.config.models import ModelConfig
from core.models.s153_v14 import S153V14Model
from core.models.s153_v14_contracts import S153V14Input
from core.models.s153_v14_recovered import (
    RECOVERED_FORMULA_VERSION,
    confirmation_magnitude,
    destination_route_gates,
    dual_magnitude_core,
)
from core.models.s153_v14_spec_bundle import V14SpecBundleError, load_verified_bundle
from core.models.s153_v14_spec_manifest import (
    MASTER_PROMPT_SHA256,
    REQUIRED_CANONICAL_SOURCES,
    V14SpecificationBinding,
)


ROOT = Path(__file__).resolve().parents[1]


def _input(*, aware: bool = True) -> S153V14Input:
    tz = timezone.utc if aware else None
    return S153V14Input(
        security_id="SEC_TEST",
        ticker="TEST",
        as_of=datetime(2025, 5, 5, tzinfo=tz),
        discovery_factors={},
        control_factors={},
        features={},
    )


def test_v14_config_is_active_on_recovered_canonical_formula() -> None:
    config = load_yaml(ROOT / "config" / "s153_v14.yaml", ModelConfig)
    assert config.enabled is True
    assert config.status == "ACTIVE_RECOVERED_CANONICAL"
    assert config.canonical_formula_version == RECOVERED_FORMULA_VERSION


def test_repository_v14_bundle_is_bound_and_hash_verified() -> None:
    bundle = load_verified_bundle(ROOT / "specs" / "s153_v14")
    assert bundle.bundle_id == "S153_V14_RECOVERED_2026_10_05"
    assert len(bundle.artifacts) == 5
    assert bundle.to_binding().complete is True


def test_dual_magnitude_golden_g1_confirmation_bonus() -> None:
    dmg, cb, dp, score = dual_magnitude_core(
        v12_score=76.0,
        m10_d=72.0,
        m10_c=70.0,
    )
    assert dmg == pytest.approx(2.0)
    assert cb == pytest.approx(1.5)
    assert dp == pytest.approx(0.0)
    assert score == pytest.approx(77.5)


def test_dual_magnitude_golden_g2_disagreement_penalty() -> None:
    dmg, cb, dp, score = dual_magnitude_core(
        v12_score=78.0,
        m10_d=80.0,
        m10_c=64.0,
    )
    assert dmg == pytest.approx(16.0)
    assert cb == pytest.approx(0.0)
    assert dp == pytest.approx(1.2)
    assert score == pytest.approx(76.8)


def test_v13_robust_destination_golden_g3_g4() -> None:
    features = {
        "V14_DF_B": 40.0,
        "V14_DF_M": 60.0,
        "V14_DF_U": 80.0,
        "V14_MC_BEAR": 80.0,
        "V14_MC_BASE": 100.0,
        "V14_MC_BULL": 140.0,
        "V14_RC_DC": 80.0,
        "V14_RC_EQ": 80.0,
        "V14_RC_RP": 80.0,
        "V14_RC_ST": 80.0,
        "V14_RC_PIT": 80.0,
        "V14_AB": 60.0,
        "V14_ROUTE_GAP": 35.0,
    }
    (
        rdf10,
        rc,
        alpha,
        df10_c,
        du,
        dup,
        abp,
        rdp,
        raw,
        m10_c,
    ) = confirmation_magnitude(
        features=features,
        base_df10=50.0,
        mch10=70.0,
        etrq=70.0,
        rer=70.0,
        cmag=70.0,
        fcvx=70.0,
        hmg10=70.0,
        pir=0.0,
    )
    assert rdf10 == pytest.approx(56.0)
    assert rc == pytest.approx(80.0)
    assert alpha == pytest.approx(0.36)
    assert df10_c == pytest.approx(52.16)
    assert du == pytest.approx(30.0)
    assert dup == pytest.approx(3.0)
    assert abp == pytest.approx(3.0)
    assert rdp == pytest.approx(4.0)
    assert m10_c == pytest.approx(raw - 10.0)


def test_destination_route_gates_use_recovered_thresholds() -> None:
    features = {
        "V14_DEMAND_ACCELERATION": 80.0,
        "V14_SUPPLY_TIGHTNESS": 80.0,
        "V14_ASP_TREND": 70.0,
        "V14_BACKLOG_BOOKBILL": 70.0,
        "V14_MARGIN_TORQUE": 70.0,
        "V14_CAPACITY_LEAD_TIME": 70.0,
    }
    active = destination_route_gates(features)
    assert "CYCLE" in active
    assert active["CYCLE"] >= 65.0


def test_model_returns_inconclusive_not_fabricated_when_v14_inputs_missing() -> None:
    result = S153V14Model().analyze(_input())
    assert result.score is None
    assert result.status == "INCONCLUSIVE_V1_4_INPUTS"
    assert result.large_winner_probability is None
    assert result.risk_adjusted_conviction is None


def test_binding_contract_still_requires_all_five_audit_artifacts() -> None:
    binding = V14SpecificationBinding(canonical_specification="spec")
    assert binding.complete is False
    assert len(binding.missing()) == 4


def test_master_prompt_reference_hash_is_pinned() -> None:
    assert MASTER_PROMPT_SHA256 == (
        "9c90dea8b44a22a6d8f006a1040eb235a4ba78145fa3fd5a8c9c94b607c94e74"
    )


def test_v14_rejects_naive_as_of() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        S153V14Model().analyze(_input(aware=False))


def _write_verified_bundle(tmp_path: Path) -> Path:
    names = list(REQUIRED_CANONICAL_SOURCES)
    artifacts = []
    for index, name in enumerate(names, start=1):
        filename = f"artifact_{index}.md"
        body = f"# {name}\n\nauthoritative-test-content-{index}\n"
        path = tmp_path / filename
        path.write_bytes(body.encode("utf-8"))
        artifacts.append({
            "name": name,
            "path": filename,
            "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        })
    (tmp_path / "manifest.json").write_text(
        json.dumps({
            "bundle_id": "S153_V14_CANONICAL_TEST_BUNDLE",
            "artifacts": artifacts,
        }),
        encoding="utf-8",
    )
    return tmp_path


def test_verified_bundle_requires_all_five_artifacts_and_hashes(tmp_path: Path) -> None:
    bundle = load_verified_bundle(_write_verified_bundle(tmp_path))
    assert bundle.bundle_id == "S153_V14_CANONICAL_TEST_BUNDLE"
    assert len(bundle.artifacts) == 5


def test_verified_bundle_rejects_tampered_artifact(tmp_path: Path) -> None:
    root = _write_verified_bundle(tmp_path)
    (root / "artifact_3.md").write_text("tampered", encoding="utf-8")
    with pytest.raises(V14SpecBundleError, match="hash mismatch"):
        load_verified_bundle(root)


def test_verified_bundle_rejects_incomplete_manifest(tmp_path: Path) -> None:
    root = _write_verified_bundle(tmp_path)
    payload = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    payload["artifacts"] = payload["artifacts"][:-1]
    (root / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(V14SpecBundleError, match="incomplete"):
        load_verified_bundle(root)
