from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.models.s153_v141 import (
    V141_FORMULA_VERSION,
    _rc,
    assumption_burden,
    route_purity,
)


def _v12(**overrides):
    base = dict(
        primary_route="F10",
        secondary_route="R10",
        routes={"F10": 80.0, "R10": 65.0},
        components={
            "ETRQ": 80.0,
            "RER": 70.0,
            "V": 75.0,
            "EXEC": 80.0,
            "T10": 70.0,
        },
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_v141_version_is_frozen() -> None:
    assert V141_FORMULA_VERSION == "S15.3_V1.4.1_CANONICAL_COMPLETION_2026-10-07"


def test_route_purity_margin_mapping() -> None:
    assert route_purity(_v12()) == pytest.approx(80.0)
    assert route_purity(_v12(secondary_route=None)) == pytest.approx(100.0)


def test_route_confidence_frozen_arithmetic() -> None:
    rc = _rc({
        "V14_RC_DC": 90.0,
        "V14_RC_EQ": 85.0,
        "V14_RC_RP": 80.0,
        "V14_RC_ST": 75.0,
        "V14_RC_PIT": 95.0,
    })
    assert rc == pytest.approx(85.25)


def test_assumption_burden_frozen_arithmetic() -> None:
    ab, stretches, missing = assumption_burden(
        features={"PIR_VAL": 40.0},
        control_factors={
            "MCR": 80.0,
            "TAMMC": 70.0,
            "GP": 75.0,
            "RPS": 65.0,
            "FPS": 70.0,
        },
        v12=_v12(),
    )
    assert missing == ()
    assert stretches["V141_GROWTH_STRETCH"] == pytest.approx(26.0)
    assert stretches["V141_MARGIN_STRETCH"] == pytest.approx(20.0)
    assert stretches["V141_MULTIPLE_STRETCH"] == pytest.approx(34.0)
    assert stretches["V141_FUNDING_STRETCH"] == pytest.approx(25.0)
    assert stretches["V141_EXECUTION_STRETCH"] == pytest.approx(24.0)
    assert ab == pytest.approx(25.95)


def test_assumption_burden_fails_closed_without_multiple_evidence() -> None:
    ab, _stretches, missing = assumption_burden(
        features={},
        control_factors={
            "MCR": 80.0,
            "TAMMC": 70.0,
            "GP": 75.0,
            "RPS": 65.0,
            "FPS": 70.0,
        },
        v12=_v12(),
    )
    assert ab is None
    assert "V141_MULTIPLE_STRETCH" in missing
