from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from pathlib import Path

import pytest

from core.forecast.acceptance import (
    PHASE8_ACCEPTANCE_ITEMS,
    ForecastAcceptanceItem,
    require_phase8_complete,
)
from core.forecast.calibration import (
    ForecastCalibrationInvalid,
    ForecastCalibrationUnavailable,
)
from core.forecast.contracts import CalibratedForecast
from core.forecast.engine import ForecastEngine, ForecastModeError
from core.forecast.repository_provider import PinnedCalibrationProvider
from data.database.sqlite_store import SQLiteStore
from data.repositories.forecast_calibration_repository import (
    CalibrationEvidenceError,
    CalibrationProfileUnavailable,
    ForecastCalibrationRepository,
)
from data.repositories.forecast_run_repository import (
    ForecastReproducibilityError,
    ForecastRunRepository,
)
from core.scanner.contracts import ScanCandidate


AS_OF = datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc)
TODAY = date(2026, 10, 6)
CANDIDATE = ScanCandidate(
    security_id="SEC_TEST",
    ticker="TEST",
    exchange="NASDAQ",
)


class FakeScorer:
    def score(self, candidate, as_of):
        assert candidate == CANDIDATE
        return (
            SimpleNamespace(score=81.0, status="READY"),
            SimpleNamespace(score=87.0, status="READY"),
        )


class ValidCalibration:
    def calibrate(self, **kwargs):
        return CalibratedForecast(
            calibration_id="CAL-001",
            calibration_source="PHASE6_MARKET_PREVALENCE_WALK_FORWARD",
            calibration_cutoff=AS_OF - timedelta(days=1),
            sample_size=1250,
            bull_return_pct=180.0,
            base_return_pct=65.0,
            bear_return_pct=-35.0,
            probability_positive_return_pct=74.0,
            probability_2x_plus_pct=31.0,
            probability_5x_plus_pct=8.0,
            probability_10x_plus_pct=2.0,
            confidence_pct=82.0,
            risk="MEDIUM",
            metadata={"evidence": "test-only calibration fixture"},
        )


def test_forward_forecast_uses_calibrated_values_and_explicit_disclosure():
    result = ForecastEngine(FakeScorer(), ValidCalibration()).forecast(
        candidate=CANDIDATE,
        as_of=AS_OF,
        current_date=TODAY,
    )
    assert result.horizon_months == 12
    assert result.v12_score == 81.0
    assert result.v14_score == 87.0
    assert result.bull_return_pct == 180.0
    assert result.base_return_pct == 65.0
    assert result.bear_return_pct == -35.0
    assert result.probability_positive_return_pct == 74.0
    assert result.probability_2x_plus_pct == 31.0
    assert result.probability_5x_plus_pct == 8.0
    assert result.probability_10x_plus_pct == 2.0
    assert "not a realized outcome" in result.disclosure


def test_forecast_fails_closed_without_calibration_provider():
    with pytest.raises(ForecastCalibrationUnavailable):
        ForecastEngine(FakeScorer()).forecast(
            candidate=CANDIDATE,
            as_of=AS_OF,
            current_date=TODAY,
        )


def test_forecast_rejects_non_current_analysis_date():
    with pytest.raises(ForecastModeError, match="current date"):
        ForecastEngine(FakeScorer(), ValidCalibration()).forecast(
            candidate=CANDIDATE,
            as_of=AS_OF,
            current_date=date(2026, 10, 5),
        )


def test_forecast_rejects_non_12_month_horizon():
    with pytest.raises(ForecastModeError, match="12-month"):
        ForecastEngine(FakeScorer(), ValidCalibration()).forecast(
            candidate=CANDIDATE,
            as_of=AS_OF,
            current_date=TODAY,
            horizon_months=6,
        )


def test_forecast_rejects_future_calibration_cutoff():
    class FutureCalibration(ValidCalibration):
        def calibrate(self, **kwargs):
            base = super().calibrate(**kwargs)
            return CalibratedForecast(
                **{
                    **base.__dict__,
                    "calibration_cutoff": AS_OF + timedelta(seconds=1),
                }
            )

    with pytest.raises(ForecastCalibrationInvalid, match="later than forecast"):
        ForecastEngine(FakeScorer(), FutureCalibration()).forecast(
            candidate=CANDIDATE,
            as_of=AS_OF,
            current_date=TODAY,
        )


def test_forecast_rejects_non_monotone_magnitude_probabilities():
    class InvalidProbabilities(ValidCalibration):
        def calibrate(self, **kwargs):
            base = super().calibrate(**kwargs)
            return CalibratedForecast(
                **{
                    **base.__dict__,
                    "probability_5x_plus_pct": 40.0,
                }
            )

    with pytest.raises(ForecastCalibrationInvalid, match="monotone"):
        ForecastEngine(FakeScorer(), InvalidProbabilities()).forecast(
            candidate=CANDIDATE,
            as_of=AS_OF,
            current_date=TODAY,
        )


def test_forecast_rejects_misordered_scenarios():
    class InvalidScenarios(ValidCalibration):
        def calibrate(self, **kwargs):
            base = super().calibrate(**kwargs)
            return CalibratedForecast(
                **{
                    **base.__dict__,
                    "bear_return_pct": 100.0,
                }
            )

    with pytest.raises(ForecastCalibrationInvalid, match="bear <= base <= bull"):
        ForecastEngine(FakeScorer(), InvalidScenarios()).forecast(
            candidate=CANDIDATE,
            as_of=AS_OF,
            current_date=TODAY,
        )


def _insert_security(store: SQLiteStore) -> None:
    store.connection.execute(
        """
        INSERT INTO security_master (
            security_id,ticker,name,exchange,market,active,created_at,updated_at
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            "SEC_TEST","TEST","Test Inc.","NASDAQ","US",1,
            AS_OF.isoformat(),AS_OF.isoformat(),
        ),
    )
    store.connection.commit()


def _insert_backtest_run(store: SQLiteStore, *, run_id: str = "RUN-001", status: str = "COMPLETE"):
    store.connection.execute(
        """
        INSERT INTO backtest_run_manifest (
            run_id,created_at,s15_spec_version,backtest_spec_version,
            random_seed,status
        ) VALUES (?,?,?,?,?,?)
        """,
        (
            run_id,
            AS_OF.isoformat(),
            "S15.3_TEST",
            "PHASE6_TEST",
            0,
            status,
        ),
    )
    store.connection.commit()


def _calibration(calibration_id: str = "CAL-001") -> CalibratedForecast:
    return CalibratedForecast(
        calibration_id=calibration_id,
        calibration_source="PHASE6_MARKET_PREVALENCE_WALK_FORWARD",
        calibration_cutoff=AS_OF - timedelta(days=1),
        sample_size=1250,
        bull_return_pct=180.0,
        base_return_pct=65.0,
        bear_return_pct=-35.0,
        probability_positive_return_pct=74.0,
        probability_2x_plus_pct=31.0,
        probability_5x_plus_pct=8.0,
        probability_10x_plus_pct=2.0,
        confidence_pct=82.0,
        risk="MEDIUM",
        metadata={},
    )


def _evidence() -> dict:
    return {
        "walk_forward_pass": True,
        "leakage_audit_pass": True,
        "survivorship_audit_pass": True,
        "future_outcome_in_feature_matrix": False,
    }


def test_calibration_repository_accepts_only_market_prevalence(tmp_path: Path):
    store = SQLiteStore(tmp_path / "calibration.sqlite")
    store.initialize()
    try:
        _insert_backtest_run(store)
        repository = ForecastCalibrationRepository(store)
        with pytest.raises(CalibrationEvidenceError, match="MARKET_PREVALENCE"):
            repository.save_validated_profile(
                run_id="RUN-001",
                model_version="S15.3_TEST",
                horizon_months=12,
                dataset_kind="MATCHED_CHALLENGE",
                calibration_method="TEST",
                calibration=_calibration(),
                evidence=_evidence(),
            )
    finally:
        store.close()


def test_calibration_repository_requires_all_audit_pass_flags(tmp_path: Path):
    store = SQLiteStore(tmp_path / "calibration.sqlite")
    store.initialize()
    try:
        _insert_backtest_run(store)
        repository = ForecastCalibrationRepository(store)
        evidence = _evidence()
        evidence["survivorship_audit_pass"] = False
        with pytest.raises(CalibrationEvidenceError, match="survivorship_audit_pass"):
            repository.save_validated_profile(
                run_id="RUN-001",
                model_version="S15.3_TEST",
                horizon_months=12,
                dataset_kind="MARKET_PREVALENCE",
                calibration_method="UNBIASED_WALK_FORWARD",
                calibration=_calibration(),
                evidence=evidence,
            )
    finally:
        store.close()


def test_calibration_repository_rejects_invalid_backtest_run(tmp_path: Path):
    store = SQLiteStore(tmp_path / "calibration.sqlite")
    store.initialize()
    try:
        _insert_backtest_run(store, status="INVALID_BACKTEST")
        repository = ForecastCalibrationRepository(store)
        with pytest.raises(CalibrationEvidenceError, match="INVALID_BACKTEST"):
            repository.save_validated_profile(
                run_id="RUN-001",
                model_version="S15.3_TEST",
                horizon_months=12,
                dataset_kind="MARKET_PREVALENCE",
                calibration_method="UNBIASED_WALK_FORWARD",
                calibration=_calibration(),
                evidence=_evidence(),
            )
    finally:
        store.close()


def test_pinned_provider_loads_verified_profile_without_refitting(tmp_path: Path):
    store = SQLiteStore(tmp_path / "calibration.sqlite")
    store.initialize()
    try:
        _insert_backtest_run(store)
        repository = ForecastCalibrationRepository(store)
        evidence_hash = repository.save_validated_profile(
            run_id="RUN-001",
            model_version="S15.3_TEST",
            horizon_months=12,
            dataset_kind="MARKET_PREVALENCE",
            calibration_method="UNBIASED_WALK_FORWARD",
            calibration=_calibration(),
            evidence=_evidence(),
        )
        provider = PinnedCalibrationProvider(repository, calibration_id="CAL-001")
        result = provider.calibrate(
            v12=SimpleNamespace(),
            v14=SimpleNamespace(),
            as_of=AS_OF,
            horizon_months=12,
        )
        assert result.calibration_id == "CAL-001"
        assert result.metadata["dataset_kind"] == "MARKET_PREVALENCE"
        assert result.metadata["evidence_hash"] == evidence_hash
        assert result.probability_10x_plus_pct == 2.0
    finally:
        store.close()


def test_calibration_repository_detects_tampered_evidence(tmp_path: Path):
    store = SQLiteStore(tmp_path / "calibration.sqlite")
    store.initialize()
    try:
        _insert_backtest_run(store)
        repository = ForecastCalibrationRepository(store)
        repository.save_validated_profile(
            run_id="RUN-001",
            model_version="S15.3_TEST",
            horizon_months=12,
            dataset_kind="MARKET_PREVALENCE",
            calibration_method="UNBIASED_WALK_FORWARD",
            calibration=_calibration(),
            evidence=_evidence(),
        )
        store.connection.execute(
            """
            UPDATE forecast_calibration_profiles
            SET evidence_json='{"tampered":true}'
            WHERE calibration_id='CAL-001'
            """
        )
        store.connection.commit()
        with pytest.raises(CalibrationEvidenceError, match="hash mismatch"):
            repository.load_validated_profile(
                calibration_id="CAL-001",
                as_of=AS_OF,
            )
    finally:
        store.close()


def test_calibration_profile_after_forecast_as_of_is_unavailable(tmp_path: Path):
    store = SQLiteStore(tmp_path / "calibration.sqlite")
    store.initialize()
    try:
        _insert_backtest_run(store)
        repository = ForecastCalibrationRepository(store)
        future = CalibratedForecast(
            **{
                **_calibration().__dict__,
                "calibration_id": "CAL-FUTURE",
                "calibration_cutoff": AS_OF + timedelta(days=1),
            }
        )
        repository.save_validated_profile(
            run_id="RUN-001",
            model_version="S15.3_TEST",
            horizon_months=12,
            dataset_kind="MARKET_PREVALENCE",
            calibration_method="UNBIASED_WALK_FORWARD",
            calibration=future,
            evidence=_evidence(),
        )
        with pytest.raises(CalibrationProfileUnavailable):
            repository.load_validated_profile(
                calibration_id="CAL-FUTURE",
                as_of=AS_OF,
            )
    finally:
        store.close()


def test_forecast_run_is_reproducible_and_deterministic(tmp_path: Path):
    store = SQLiteStore(tmp_path / "forecast-run.sqlite")
    store.initialize()
    try:
        _insert_security(store)
        _insert_backtest_run(store)
        calibration_repository = ForecastCalibrationRepository(store)
        calibration_repository.save_validated_profile(
            run_id="RUN-001",
            model_version="S15.3_TEST",
            horizon_months=12,
            dataset_kind="MARKET_PREVALENCE",
            calibration_method="UNBIASED_WALK_FORWARD",
            calibration=_calibration(),
            evidence=_evidence(),
        )
        provider = PinnedCalibrationProvider(
            calibration_repository,
            calibration_id="CAL-001",
        )
        result = ForecastEngine(FakeScorer(), provider).forecast(
            candidate=CANDIDATE,
            as_of=AS_OF,
            current_date=TODAY,
        )
        repository = ForecastRunRepository(store)
        kwargs = {
            "result": result,
            "v12_model_version": "S15.3_V1.2",
            "v14_model_version": "S15.3_V1.4",
            "data_snapshot_hash": "a" * 64,
            "model_config_hash": "b" * 64,
        }
        first = repository.save(**kwargs)
        second = repository.save(**kwargs)
        assert first.analysis_id == second.analysis_id
        assert first.forecast_hash == second.forecast_hash

        stored = repository.load(first.analysis_id)
        assert stored["forecast_hash"] == first.forecast_hash
        assert stored["calibration_evidence_hash"] == first.calibration_evidence_hash
        assert stored["forecast_payload"]["calibration_id"] == "CAL-001"
        assert stored["forecast_payload"]["v12_model_version"] == "S15.3_V1.2"
        assert stored["forecast_payload"]["v14_model_version"] == "S15.3_V1.4"
    finally:
        store.close()


def test_forecast_run_requires_real_reproducibility_hashes(tmp_path: Path):
    store = SQLiteStore(tmp_path / "forecast-run.sqlite")
    store.initialize()
    try:
        _insert_security(store)
        _insert_backtest_run(store)
        calibration_repository = ForecastCalibrationRepository(store)
        calibration_repository.save_validated_profile(
            run_id="RUN-001",
            model_version="S15.3_TEST",
            horizon_months=12,
            dataset_kind="MARKET_PREVALENCE",
            calibration_method="UNBIASED_WALK_FORWARD",
            calibration=_calibration(),
            evidence=_evidence(),
        )
        result = ForecastEngine(
            FakeScorer(),
            PinnedCalibrationProvider(calibration_repository, calibration_id="CAL-001"),
        ).forecast(
            candidate=CANDIDATE,
            as_of=AS_OF,
            current_date=TODAY,
        )
        with pytest.raises(ForecastReproducibilityError, match="data_snapshot_hash"):
            ForecastRunRepository(store).save(
                result=result,
                v12_model_version="S15.3_V1.2",
                v14_model_version="S15.3_V1.4",
                data_snapshot_hash="not-a-hash",
                model_config_hash="b" * 64,
            )
    finally:
        store.close()


def test_forecast_run_detects_calibration_provenance_tamper(tmp_path: Path):
    store = SQLiteStore(tmp_path / "forecast-run.sqlite")
    store.initialize()
    try:
        _insert_security(store)
        _insert_backtest_run(store)
        calibration_repository = ForecastCalibrationRepository(store)
        calibration_repository.save_validated_profile(
            run_id="RUN-001",
            model_version="S15.3_TEST",
            horizon_months=12,
            dataset_kind="MARKET_PREVALENCE",
            calibration_method="UNBIASED_WALK_FORWARD",
            calibration=_calibration(),
            evidence=_evidence(),
        )
        result = ForecastEngine(
            FakeScorer(),
            PinnedCalibrationProvider(calibration_repository, calibration_id="CAL-001"),
        ).forecast(
            candidate=CANDIDATE,
            as_of=AS_OF,
            current_date=TODAY,
        )
        store.connection.execute(
            """
            UPDATE forecast_calibration_profiles
            SET evidence_json='{"tampered":true}'
            WHERE calibration_id='CAL-001'
            """
        )
        store.connection.commit()
        with pytest.raises(ForecastReproducibilityError, match="hash mismatch"):
            ForecastRunRepository(store).save(
                result=result,
                v12_model_version="S15.3_V1.2",
                v14_model_version="S15.3_V1.4",
                data_snapshot_hash="a" * 64,
                model_config_hash="b" * 64,
            )
    finally:
        store.close()


def test_phase8_acceptance_contract_fails_closed_when_v14_is_blocked():
    assert len(PHASE8_ACCEPTANCE_ITEMS) == 17
    items = [
        ForecastAcceptanceItem(name=name, passed=True, evidence="test evidence")
        for name in PHASE8_ACCEPTANCE_ITEMS
    ]
    require_phase8_complete(items)

    idx = PHASE8_ACCEPTANCE_ITEMS.index("V1.4 canonical scoring")
    items[idx] = ForecastAcceptanceItem(
        name="V1.4 canonical scoring",
        passed=False,
        evidence="Phase 5 authoritative V1.4 specification is not yet executable",
    )
    with pytest.raises(RuntimeError, match="V1.4 canonical scoring"):
        require_phase8_complete(items)
