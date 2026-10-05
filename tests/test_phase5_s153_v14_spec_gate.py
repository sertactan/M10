from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.config.loader import load_yaml
from core.config.models import ModelConfig
from core.models.s153_v14 import (
    S153V14Model,
    V14CanonicalSpecificationMissing,
)
from core.models.s153_v14_contracts import S153V14Input
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
