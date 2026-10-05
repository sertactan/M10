from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.config.loader import load_yaml
from core.config.models import ModelConfig
from core.models.s153_v14 import (
    REQUIRED_CANONICAL_SOURCES,
    S153V14Model,
    V14CanonicalSpecificationMissing,
)
from core.models.s153_v14_contracts import S153V14Input


ROOT = Path(__file__).resolve().parents[1]


def _input() -> S153V14Input:
    return S153V14Input(
        security_id="SEC_TEST",
        ticker="TEST",
        as_of=datetime(2025, 5, 5, tzinfo=timezone.utc),
        discovery_factors={},
        control_factors={},
        features={
            # Even plausible-looking V1.4 labels must not trigger invented logic.
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
