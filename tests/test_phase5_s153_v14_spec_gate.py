from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

import pytest

from core.config.loader import load_yaml
from core.config.models import ModelConfig
from core.models.s153_v14 import (
    S153V14Model,
    V14CanonicalSpecificationMissing,
)
from core.models.s153_v14_contracts import S153V14Input
from core.models.s153_v14_spec_bundle import V14SpecBundleError, load_verified_bundle
from core.models.s153_v14_spec_manifest import (
    FORBIDDEN_TO_INVENT_OR_MODIFY,
    MASTER_PROMPT_SHA256,
    REQUIRED_CANONICAL_SOURCES,
    V14SpecificationBinding,
)


ROOT = Path(__file__).resolve().parents[1]


def _input() -> S153V14Input:
    return S153V14Input(
        security_id="SEC_TEST",
        ticker="TEST",
        as_of=datetime(2025, 5, 5, tzinfo=timezone.utc),
        discovery_factors={},
        control_factors={},
        features={
            "DUAL_MAGNITUDE": 90.0,
            "ACCELERATION": 95.0,
            "LARGE_WINNER_PROBABILITY": 88.0,
        },
    )


def test_v14_config_stays_disabled_until_canonical_binding() -> None:
    config = load_yaml(ROOT / "config" / "s153_v14.yaml", ModelConfig)
    assert config.enabled is False
    assert config.status == "BLOCKED_CANONICAL_V1_4_SPEC_REQUIRED"
    assert config.weights == {}
    assert config.thresholds == {}


def test_v14_model_fails_closed_without_authoritative_spec() -> None:
    with pytest.raises(V14CanonicalSpecificationMissing) as exc:
        S153V14Model().analyze(_input())
    message = str(exc.value)
    for source in REQUIRED_CANONICAL_SOURCES:
        assert source in message
    for item in FORBIDDEN_TO_INVENT_OR_MODIFY:
        assert item in message


def test_binding_requires_all_five_authoritative_artifacts() -> None:
    binding = V14SpecificationBinding(canonical_specification="spec")
    assert binding.complete is False
    assert len(binding.missing()) == 4


def test_complete_manifest_still_does_not_activate_unbound_math() -> None:
    binding = V14SpecificationBinding(
        canonical_specification="spec",
        factor_dna_definitions="dna",
        router_gate_specification="router",
        dual_magnitude_destination_specification="destination",
        golden_test_cases="golden",
    )
    assert binding.complete is True
    with pytest.raises(V14CanonicalSpecificationMissing, match="formula binding"):
        S153V14Model(binding).analyze(_input())


def test_master_prompt_reference_hash_is_pinned() -> None:
    assert MASTER_PROMPT_SHA256 == (
        "9c90dea8b44a22a6d8f006a1040eb235a4ba78145fa3fd5a8c9c94b607c94e74"
    )


def test_v14_rejects_naive_as_of_before_spec_gate() -> None:
    data = S153V14Input(
        security_id="SEC_TEST",
        ticker="TEST",
        as_of=datetime(2025, 5, 5),
        discovery_factors={},
        control_factors={},
        features={},
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        S153V14Model().analyze(data)


def _write_verified_bundle(tmp_path: Path) -> Path:
    names = list(REQUIRED_CANONICAL_SOURCES)
    artifacts = []
    for index, name in enumerate(names, start=1):
        filename = f"artifact_{index}.md"
        body = f"# {name}\n\nauthoritative-test-content-{index}\n"
        path = tmp_path / filename
        path.write_text(body, encoding="utf-8")
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
    binding = bundle.to_binding()
    assert binding.complete is True
    assert all("#sha256=" in value for value in (
        binding.canonical_specification,
        binding.factor_dna_definitions,
        binding.router_gate_specification,
        binding.dual_magnitude_destination_specification,
        binding.golden_test_cases,
    ))


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


def test_manifest_template_cannot_activate_phase5() -> None:
    with pytest.raises(V14SpecBundleError):
        load_verified_bundle(ROOT / "specs" / "s153_v14")
