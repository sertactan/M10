from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.config.loader import load_yaml
from core.config.models import ModelConfig
from core.features.s153_v12_input_loader import S153V12InputLoader
from core.models.s153_v12 import S153V12Model
from core.models.s153_v12_contracts import S153V12Input
from core.routes.s153_v12 import route_scores
from core.scoring.s153_v12_final import (
    core153,
    final_s153,
    horizon_penalty,
    magnitude_gap,
    near_miss_penalty,
)
from data.database.sqlite_store import SQLiteStore
from data.repositories.model_feature_repository import ModelFeatureRepository


ROOT = Path(__file__).resolve().parents[1]
AS_OF = datetime(2025, 5, 5, 23, 59, tzinfo=timezone.utc)


def _control(value: float = 90.0) -> dict[str, float]:
    return {
        "MCR": value, "TAMMC": value, "GP": value, "RPS": value,
        "FPS": value, "DIL": value, "IROIC": value, "ORG": value,
        "UE": value, "MOAT": value, "CAPINT": value, "CONC": value,
    }


def _full_features() -> dict[str, float]:
    f: dict[str, float] = {}

    # S1-S3 router / history / risk
    f.update({
        "SG":90,"RR":90,"OL_ROUTER":90,"MOAT_ROUTER":90,"PSC":90,"BS_ROUTER":90,
        "GA_ROUTER":90,"MI_ROUTER":90,"CAT_ROUTER":90,"UE_ROUTER":90,"MSG":90,
        "CR":60,"CP":60,"NEP":60,
        "WINNER_SIM":90,"CONTROL_SIM":30,
        "DPF":10,"GD":10,"ONE":10,"CYCLE":10,"INV":10,"PRICE_NORM_RISK":10,
        "DNR":10,"GDR":10,"DILR":10,"AQR":10,"PPR":10,"VR":10,
    })

    # S14 / company quality
    f.update({
        "B_Q":90,"S6":90,"S7":90,"S8":90,"S9":90,"S10":90,
        "S11":90,"S12":90,"S13":100,
    })

    # U / ETRQ / FCVX / RER
    f.update({
        "OL_Q":90,"MI_Q":90,"FCFI_Q":90,"EPSL_Q":90,
        "FLOATSIZE":90,"TURNACC":90,"SCARCITY":90,
        "MEDIAN_DOLLAR_VOLUME_20":10_000_000,
        "PROFITSHIFT":90,"MODELSHIFT":90,"BSSHIFT":90,"MULTGAP":90,
        "OPT":90,
    })

    # Catalyst / market / regime / viability
    f.update({
        "TIME":90,"MAG":90,"EVID":90,"STACK":90,"ASYM":90,
        "RS":90,"H52":90,"BREAK":90,"STAGE2":90,"VCP":90,"PVACC":90,
        "MR":90,"SRS":90,"TB":90,"UA":90,"LIQ":90,
        "CASH":90,"BS_V":90,"FUND":90,"MAT":90,"CONT":90,
    })

    # Acceleration + S15.2 X
    f.update({
        "RBACC":90,"DNAACC":90,"REVACC":90,"PROFACC":90,
        "MOMACC":90,"VOLACC":90,"GROWACC":90,
        "RBV3":90,"RBV6":90,"CATACC":90,"REGACC":90,
    })

    # Historical / rarity / destination / PIR
    f.update({
        "H10":90,"XR":99,"HMG5":90,"HMG10":90,
        "SUPPORTED_MC_12_FI":1200,
        "PLAUSIBLE_CEILING_MC":1200,
        "PIR_VAL":10,"PIR_EXT":10,"PIR_DEC":10,"PIR_CROWD":10,"PIR_USED":10,
    })

    # T10/T15
    f.update({
        "CT":90,"CT15":90,
        "RSACC":90,"BREADTH":90,"VOLCOMP":90,"GAP":90,
        "EPS_BREADTH":90,"EPS_MAGNITUDE":90,"REVENUE_BREADTH":90,"TARGET_ACCELERATION":90,
        "SECTOR_RS_ACCEL":90,"THEME_BREADTH_ACCEL":90,"UNDERLYING_ASSET_ACCEL":90,
        "DOLLAR_VOLUME_ACCEL":90,"POSITIONING":90,
        "CASH_RUNWAY":90,"FUNDING_READINESS":90,"MILESTONE_READINESS":90,
        "CAPACITY_READINESS":90,"DEPENDENCY_QUALITY":90,
        "EXEC15_CASH_RUNWAY":90,"EXEC15_FUNDING_READINESS":90,
        "EXEC15_MILESTONE_READINESS":90,"EXEC15_CAPACITY_READINESS":90,
        "EXEC15_DEPENDENCY_QUALITY":90,
    })

    # Keep special routes below the generic F/I routes.
    f.update({
        "DEBT_IMPROVEMENT":25,"FCF_INFLECTION":25,"MARGIN_RECOVERY":25,
        "COST_RESET":25,"DEMAND_RECOVERY":25,
        "REFINANCING":25,"RESTRUCTURING":25,"ASSET_SALE":25,
        "DEBT_EXCHANGE":25,"BANKRUPTCY_EXIT":25,"MAJOR_COST_REDUCTION":25,
        "LIQUIDITY_IMPROVEMENT":25,"DEBT_MATURITY_IMPROVEMENT":25,
        "FUNDING_ACCESS_D":25,"CONTINUITY_D":25,
        "RNPVMC":25,"INDICATION_TAMMC":25,"PLATFORM_OPTIONALITY":25,
        "CLINICAL_EVIDENCE":25,"TRIAL_PROGRESS":25,"PARTNER_VALIDATION":25,
        "EVIDENCE_MOMENTUM":25,"C_B":25,
        "CASH_RUNWAY_B":25,"FUNDING_ACCESS_B":25,"DILUTION_QUALITY_B":25,
        "EXECUTION_READINESS_B":25,
        "SIF":25,"DTC":25,"FLOAT_Q":25,"MOM_Q":25,"CAT_Q":25,
    })

    # Exact confidence formula inputs.
    f.update({
        "DATA_COVERAGE":90,"SOURCE_QUALITY":90,"PIT_INTEGRITY":90,"MODEL_FIT":90,
    })
    return f


def test_canonical_true_10x_example() -> None:
    c = core153(89, 88, 84)
    gap = magnitude_gap(92, 88)
    nmp = near_miss_penalty(gap)
    hp = horizon_penalty(84)
    final = final_s153(c, nmp, hp)
    assert c == pytest.approx(87.4259028849784)
    assert gap == 4
    assert nmp == 0
    assert hp == 0
    assert final == pytest.approx(87.4259028849784)


def test_canonical_near_miss_example() -> None:
    c = core153(84, 68, 76)
    gap = magnitude_gap(92, 68)
    nmp = near_miss_penalty(gap)
    hp = horizon_penalty(76)
    final = final_s153(c, nmp, hp)
    assert c == pytest.approx(76.89210505094425)
    assert gap == 24
    assert nmp == 8
    assert hp == 0
    assert final == pytest.approx(68.89210505094425)


def test_canonical_horizon_false_positive_example() -> None:
    c = core153(81, 73, 62)
    gap = magnitude_gap(94, 73)
    nmp = near_miss_penalty(gap)
    hp = horizon_penalty(62)
    final = final_s153(c, nmp, hp)
    assert c == pytest.approx(73.43668072626647)
    assert gap == 21
    assert nmp == 6.5
    assert hp == pytest.approx(1.2)
    assert final == pytest.approx(65.73668072626647)


def test_route_formula_uses_canonical_f10_weights() -> None:
    f = {"U":80,"A":70,"C":60,"M":50,"G":40,"V":30,
         "S8":90,"S9":90,"S10":90,"S12":90,"S14":90}
    routes = route_scores(f)
    expected = (
        0.22*80 + 0.22*70 + 0.16*60 + 0.15*50
        + 0.08*40 + 0.10*30 + 0.07*90
    )
    assert routes["F10"] == pytest.approx(expected)


def test_full_canonical_input_can_reach_precision_confirmed() -> None:
    result = S153V12Model().analyze(S153V12Input(
        security_id="SEC_TEST",ticker="TEST",as_of=AS_OF,
        discovery_factors={i:85.0 for i in range(1,49)},
        control_factors=_control(),
        features=_full_features(),
        current_price=10.0,current_market_cap=100.0,
    ))
    assert result.primary_route == "F10"
    assert result.route_gate is True
    assert result.score is not None and result.score >= 80
    assert result.components["M10"] is not None and result.components["M10"] >= 70
    assert result.components["T10"] is not None and result.components["T10"] >= 70
    assert result.precision_confirmed is True
    assert result.status == "PRECISION_CONFIRMED_12M_10X"


def test_missing_canonical_inputs_fail_closed_inconclusive() -> None:
    result = S153V12Model().analyze(S153V12Input(
        security_id="SEC_TEST",ticker="TEST",as_of=AS_OF,
        discovery_factors={i:None for i in range(1,49)},
        control_factors={k:None for k in _control()},
        features={},
        current_price=None,current_market_cap=None,
    ))
    assert result.score is None
    assert result.status == "INCONCLUSIVE"
    assert "S15.2" in result.missing_requirements


def _seed_security(store: SQLiteStore) -> None:
    now=datetime.now(timezone.utc).isoformat()
    store.connection.execute(
        """
        INSERT INTO security_master
        (security_id,ticker,name,exchange,market,active,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        ("SEC_TEST","TEST","Test Corp","NASDAQ","US",1,now,now),
    )
    store.connection.commit()


def test_feature_repository_rejects_noncanonical_provider_phase(tmp_path: Path) -> None:
    store=SQLiteStore(tmp_path/"op.db")
    store.initialize(ROOT/"data"/"database"/"schema.sql")
    _seed_security(store)
    repo=ModelFeatureRepository(store)
    with pytest.raises(ValueError,match="forbids non-canonical source phase"):
        repo.save_feature(
            security_id="SEC_TEST",feature_key="D01",value=80,
            feature_as_of=AS_OF,available_at=AS_OF,
            source_phase="FINNHUB",source_ref="direct-api",
            quality_status="SECONDARY",computation_version="test",
        )
    store.close()


def test_feature_loader_excludes_future_snapshot(tmp_path: Path) -> None:
    store=SQLiteStore(tmp_path/"op.db")
    store.initialize(ROOT/"data"/"database"/"schema.sql")
    _seed_security(store)
    repo=ModelFeatureRepository(store)
    earlier=AS_OF-timedelta(days=1)
    later=AS_OF+timedelta(days=1)
    repo.save_feature(
        security_id="SEC_TEST",feature_key="D01",value=70,
        feature_as_of=earlier,available_at=earlier,
        source_phase="DERIVED_CANONICAL",source_ref="old",
        quality_status="GOOD",computation_version="v1",
    )
    repo.save_feature(
        security_id="SEC_TEST",feature_key="D01",value=99,
        feature_as_of=later,available_at=later,
        source_phase="DERIVED_CANONICAL",source_ref="future",
        quality_status="GOOD",computation_version="v1",
    )
    loaded=S153V12InputLoader(repo).load(
        security_id="SEC_TEST",ticker="TEST",as_of=AS_OF
    )
    assert loaded.discovery_factors[1] == 70
    store.close()


def test_v12_config_is_enabled_and_bound_to_canonical_spec() -> None:
    cfg=load_yaml(ROOT/"config"/"s153_v12.yaml",ModelConfig)
    assert cfg.enabled is True
    assert cfg.canonical_formula_version == "MERIDYEN_S15.3_CANONICAL_FINAL_v1.0"
    assert cfg.weights["core_s152"] == pytest.approx(0.45)
    assert cfg.weights["core_m10"] == pytest.approx(0.30)
    assert cfg.weights["core_t10"] == pytest.approx(0.25)
    assert cfg.thresholds["precision_score"] == pytest.approx(80)
    assert cfg.thresholds["precision_xr"] == pytest.approx(99)
