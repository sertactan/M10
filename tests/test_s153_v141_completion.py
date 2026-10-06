from __future__ import annotations

from types import SimpleNamespace

import pytest

from datetime import datetime, timezone

from core.models.s153_v14_contracts import S153V14Input
from core.models.s153_v141 import (
    V141_FORMULA_VERSION,
    _rc,
    assumption_burden,
    generate_v141_features,
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



def _v141_input(*, features=None, control_factors=None):
    return S153V14Input(
        security_id="SEC_TEST",
        ticker="TEST",
        as_of=datetime(2026, 10, 7, tzinfo=timezone.utc),
        discovery_factors={},
        control_factors=control_factors or {
            "MCR": 80.0,
            "TAMMC": 70.0,
            "GP": 75.0,
            "RPS": 65.0,
            "FPS": 70.0,
        },
        features=features or {},
        current_price=10.0,
        current_market_cap=100.0,
    )


def test_v141_scenario_market_caps_destination_factors_and_route_gap() -> None:
    features = {
        "DATA_COVERAGE": 90.0,
        "SOURCE_QUALITY": 85.0,
        "MODEL_FIT": 75.0,
        "PIT_INTEGRITY": 95.0,
        "PIR_VAL": 40.0,
        "SUPPORTED_MC_12_FI": 1000.0,
        "SUPPORTED_MC_12_R": 800.0,
        "PLAUSIBLE_CEILING_MC": 1200.0,
    }
    generated, diagnostics, missing, status = generate_v141_features(
        data=_v141_input(features=features),
        v12=_v12(score=80.0),
    )
    assert missing == ()
    assert status is None
    assert diagnostics["V141_ROUTE_CONFIDENCE"] == pytest.approx(85.25)
    assert diagnostics["V141_SCENARIO_WIDTH_PCT"] == pytest.approx(20.1625)
    assert generated["V14_MC_BASE"] == pytest.approx(1000.0)
    assert generated["V14_MC_BEAR"] == pytest.approx(798.375)
    assert generated["V14_MC_BULL"] == pytest.approx(1200.0)
    assert generated["V14_DF_B"] == pytest.approx(79.8375)
    assert generated["V14_DF_M"] == pytest.approx(100.0)
    assert generated["V14_DF_U"] == pytest.approx(100.0)
    assert generated["V14_ROUTE_GAP"] == pytest.approx(20.0)
    assert generated["V14_AB"] == pytest.approx(25.95)


def test_v141_primary_q10_fails_closed() -> None:
    generated, diagnostics, missing, status = generate_v141_features(
        data=_v141_input(
            features={
                "DATA_COVERAGE": 90.0,
                "SOURCE_QUALITY": 90.0,
                "MODEL_FIT": 90.0,
                "PIT_INTEGRITY": 90.0,
                "PIR_VAL": 20.0,
            }
        ),
        v12=_v12(
            score=80.0,
            primary_route="Q10",
            secondary_route=None,
            routes={"Q10": 85.0},
        ),
    )
    assert generated == {}
    assert diagnostics == {}
    assert missing
    assert status == "INCONCLUSIVE_V1_4_1_Q_ROUTE"
