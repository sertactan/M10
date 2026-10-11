"""Acceptance boundary tests: these minimal models are synthetic, not evidence."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
import json
import unittest

from app.scoring_v8_model_gates import (
    EvidenceGateError, MODEL_VERSIONS, S14_LEGS, S16_REQUIRED_FEATURES,
    TICKERS, V7_RESEARCH, audit_v7_report, load_sealed_v7, verify_v7_baseline,
)


@contextmanager
def expect_gate_error(message: str | None = None):
    try:
        yield
    except EvidenceGateError as error:
        if message is not None:
            assert message in str(error), (message, str(error))
    else:
        raise AssertionError("Expected independent evidence gate to reject this mutation")


def _report():
    stocks = []
    for ticker in TICKERS:
        accepted = V7_RESEARCH[ticker]
        legs = {key: {"score": accepted.get(key)} for key in S14_LEGS}
        entries = [
            {"model": key, "score": score, "status":
             "REAL_SCORE_ACCEPTED_RESEARCH" if key == "S9" else "VERIFIED_DONE"}
            for key, score in accepted.items()
        ]
        extra = ("S1", "S2", "S3", "S4", "S5", "S6", "S8", "S9", "S10",
                 "S11", "S12", "S13", "S14", "S16-E", "S16-C", "S16-EA",
                 *MODEL_VERSIONS)
        for name in extra:
            if name not in accepted:
                entries.append({"model": name, "score": None,
                                "present": sum(x["score"] is not None for x in legs.values())
                                if name == "S14" else None,
                                "missing": ["S15.2", "M10>=5/7", "T10>=5/7"]
                                if name in MODEL_VERSIONS else [],
                                "evidence": {"result": {"status": "INCONCLUSIVE",
                                        "score": None, "missing_requirements": ["S15.2"]}}
                                if name in MODEL_VERSIONS else {}})
        stock = {
            "ticker": ticker, "models": entries, "quality": legs,
            "full_model_count": len(accepted), "s16_accepted": 0,
            "control_chain": {"discovery_complete_factors": 3,
                              "partial_discovery_factors": [1, 2],
                              "control_inputs_present": 2,
                              "historical_h": None},
            "s16_features": [{"key": key, "accepted": False, "pit_usable": False,
                              "score": None, "raw": {"observed": 0} if key == "compression" else {}}
                             for key in S16_REQUIRED_FEATURES],
            "sec_acceptance_verifications": {"000001-26-000001": {
                "accepted_at": "2026-02-26T22:22:13Z", "public_dissemination_at": None,
                "historical_provider_available_at": None}},
        }
        if ticker == "INOD":
            stock["sec_quality_v3"] = {"B_Q_risk_count": 5}
            stock["task9_financial_evidence"] = {"S6_verified_count": 5}
            stock["sec_forensic_v3"] = {"reviewed_risk_block_count": 0}
        stocks.append(stock)
    return {"schema": "M10_SCORING_COMPLETION_RESEARCH_V1",
            "canonical_securities": 0, "canonical_dates": 0,
            "full_model_count": 15, "WF9": "BLOCKED", "LearningV3": "NOT_TRAINED",
            "S16_E_activation": "PENDING_APPROVAL", "stocks": stocks}


def test_preserve_true_s11_zero_and_all_fifteen_research_scores():
    report = _report()
    verify_v7_baseline(report)
    result = audit_v7_report(report)
    assert result["accepted_research_scores"] == 15
    assert result["new_model_scores_accepted"] == 0
    assert result["stocks"]["INOD"]["S4_S5_S6_BQ_S13_S14"]["S14_valid_legs"] == 3
    assert result["stocks"]["INOD"]["S4_S5_S6_BQ_S13_S14"]["zero_not_missing_example"] == {"INOD_S11": 0}
    assert result["stocks"]["INOD"]["S1_S3"]["core48_research_candidate_complete_factors"] == 3
    assert result["Task14_S16_C_normalized_PIT"] == "0/22"
    assert result["Task15_S16_E"]["score"] is None


def test_real_zero_cannot_be_changed_to_missing_or_fabricated():
    for replacement in (None, -1, 1.0, float("nan"), True):
        report = _report()
        row = next(m for m in report["stocks"][0]["models"] if m["model"] == "S11")
        row["score"] = replacement
        with expect_gate_error():
            verify_v7_baseline(report)


def test_cannot_promote_partial_core48_or_s153():
    report = _report()
    row = next(m for m in report["stocks"][0]["models"] if m["model"] == "S1")
    row["score"] = 85.0
    with expect_gate_error():
        audit_v7_report(report)
    report = _report()
    row = next(m for m in report["stocks"][0]["models"] if m["model"] == "S15.3 V1.4")
    row["evidence"]["result"]["score"] = 75.0
    with expect_gate_error():
        audit_v7_report(report)


def test_cannot_promote_any_of_22_raw_s16_features():
    report = _report()
    row = report["stocks"][0]["s16_features"][13]
    row.update(accepted=True, pit_usable=True, score=78.0)
    with expect_gate_error("unauthorized PIT"):
        audit_v7_report(report)


def test_missing_and_real_zero_are_distinct_for_s14_legs():
    report = _report()
    s14 = audit_v7_report(report)["stocks"]["INOD"]["S4_S5_S6_BQ_S13_S14"]
    assert s14["S14_legs"]["S11"] == 0.0
    assert s14["S14_legs"]["S6"] is None
    assert s14["S13_signed_decisions"] == 0
    assert s14["S14"] is None
    report["stocks"][0]["quality"]["S6"]["score"] = 0.0
    with expect_gate_error("six-leg gate"):
        audit_v7_report(report)


def test_missing_pit_publication_does_not_inherit_sec_acceptance():
    result = audit_v7_report(_report())
    row = result["stocks"]["INOD"]["Task13"]
    assert row["SEC_acceptance_candidates"] == 1
    assert row["verified_first_publication_timestamps"] == 0
    assert row["verified_historical_provider_availability"] == 0
    assert result["stocks"]["INOD"]["Task14_S16_C"]["raw_research_candidate_features"] == ["compression"]


def test_report_seal_is_checked_and_source_replay_label_is_precise(tmp_path):
    path = tmp_path / "report.json"
    data = json.dumps(_report()).encode("utf-8")
    path.write_bytes(data)
    (tmp_path / "report.json.sha256").write_text(sha256(data).hexdigest(), encoding="ascii")
    report, digest, verification = load_sealed_v7(path)
    assert digest == sha256(data).hexdigest()
    assert verification == "V7_SHA256_SEAL_AND_CONTRACT_ONLY_NO_RAW_SOURCE_REPLAY"
    assert audit_v7_report(report)["Task12_S15_3_full_scores"] == 0
    path.write_bytes(data + b" ")
    with expect_gate_error("checksum"):
        load_sealed_v7(path)


def test_no_changed_signed_human_review_or_production_flags():
    report = _report()
    report["stocks"][0]["sec_forensic_v3"]["reviewed_risk_block_count"] = 7
    with expect_gate_error():
        audit_v7_report(report)
    report = deepcopy(_report())
    report["S16_E_activation"] = "ACTIVE"
    with expect_gate_error():
        audit_v7_report(report)


class TestScoringV8ModelGates(unittest.TestCase):
    """Standard-library runner; CI pytest also collects this TestCase."""

    def test_preserved_research(self):
        test_preserve_true_s11_zero_and_all_fifteen_research_scores()

    def test_real_zero(self):
        test_real_zero_cannot_be_changed_to_missing_or_fabricated()

    def test_partial_models(self):
        test_cannot_promote_partial_core48_or_s153()

    def test_pit_features(self):
        test_cannot_promote_any_of_22_raw_s16_features()

    def test_s14_missing_vs_zero(self):
        test_missing_and_real_zero_are_distinct_for_s14_legs()

    def test_sec_acceptance_not_publication(self):
        test_missing_pit_publication_does_not_inherit_sec_acceptance()

    def test_sealed_source(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        with TemporaryDirectory() as folder:
            test_report_seal_is_checked_and_source_replay_label_is_precise(Path(folder))

    def test_human_and_production_gates(self):
        test_no_changed_signed_human_review_or_production_flags()
