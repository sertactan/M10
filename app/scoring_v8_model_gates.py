"""Offline V8 readiness audit of the sealed V7 research checkpoint.

This module reports *evidence gaps*. It never infers canonical scores from
partially computed research diagnostics and never modifies source evidence.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any

from core.historical.s16_feature_coverage import S16_REQUIRED_FEATURES


SCHEMA = "M10_SCORING_V8_OTHER_MODELS_AUDIT_V1"
TICKERS = ("INOD", "TMDX", "CRMD", "PENG", "ETON")
MODEL_VERSIONS = ("S15.3 V1.2", "S15.3 V1.4", "S15.3 V1.4.1")
S14_LEGS = ("B_Q", "S6", "S7", "S11", "S12", "S13")
S13_BLOCKS = ("AUD", "RPT", "REC", "DIL", "REV", "ACQ", "GOV")
V7_RESEARCH = {
    "INOD": {"S7": 100.0, "S11": 0.0, "S12": 91.52886637844543},
    "TMDX": {"S7": 100.0, "S12": 85.40388058409478,
              "S9": 77.77777777777777},
    "CRMD": {"S7": 100.0, "S11": 86.01535933860907,
             "S12": 95.68213179601975},
    "PENG": {"S7": 100.0, "S12": 83.51205769458369,
             "S9": 66.66666666666667},
    "ETON": {"S7": 100.0, "S11": 7.860332129752234,
             "S9": 55.55555555555556},
}


class EvidenceGateError(ValueError):
    """Source, report, or acceptance assertion did not pass."""


def _models(stock: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = stock.get("models")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise EvidenceGateError("invalid model rows")
    lookup = {m["model"]: m for m in rows}
    if len(lookup) != len(rows):
        raise EvidenceGateError("duplicate model identifier")
    return lookup


def _number(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def verify_v7_baseline(report: Mapping[str, Any]) -> None:
    """Check exact original accepted V7 scores and absence of promotions.

    A matching checksum establishes local byte integrity, while the inherited
    source-specific V7 replay remains the authority for the underlying 10-Ks.
    """
    if (report.get("schema") != "M10_SCORING_COMPLETION_RESEARCH_V1"
            or report.get("canonical_securities") != 0
            or report.get("canonical_dates") != 0
            or report.get("full_model_count") != 15
            or report.get("WF9") != "BLOCKED"
            or report.get("LearningV3") != "NOT_TRAINED"
            or report.get("S16_E_activation") != "PENDING_APPROVAL"):
        raise EvidenceGateError("V7 sealed checkpoint invariants changed")
    stocks = report.get("stocks")
    if not isinstance(stocks, list) or [x.get("ticker") for x in stocks] != list(TICKERS):
        raise EvidenceGateError("V7 five-stock identity/order mismatch")
    all_count = 0
    for stock in stocks:
        ticker = stock["ticker"]
        models = _models(stock)
        real = {k: m["score"] for k, m in models.items() if m.get("score") is not None}
        if set(real) != set(V7_RESEARCH[ticker]):
            raise EvidenceGateError(f"{ticker}: V7 accepted model set changed")
        for name, expected in V7_RESEARCH[ticker].items():
            score = real[name]
            if not _number(score) or not math.isclose(score, expected, rel_tol=0, abs_tol=1e-11):
                raise EvidenceGateError(f"{ticker}: {name} changed; zero is distinct from missing")
            if name == "S9" and models[name].get("status") != "REAL_SCORE_ACCEPTED_RESEARCH":
                raise EvidenceGateError(f"{ticker}: S9 Research acceptance status changed")
            if models[name].get("canonical_accepted") is True or models[name].get("historical_pit_accepted") is True:
                raise EvidenceGateError(f"{ticker}: Research score promoted to PIT")
        if stock.get("full_model_count") != len(real):
            raise EvidenceGateError(f"{ticker}: Research count mismatch")
        if stock.get("s16_accepted") != 0:
            raise EvidenceGateError(f"{ticker}: unexpected S16 canonical promotion")
        for name in (*MODEL_VERSIONS, "S1", "S2", "S3", "S4", "S5", "S6",
                     "S13", "S14", "S16-E", "S16-C", "S16-EA"):
            if name not in models or models[name].get("score") is not None:
                raise EvidenceGateError(f"{ticker}: unaccepted complete model {name}")
        all_count += len(real)
    if all_count != 15:
        raise EvidenceGateError("V7 baseline has other than 15 complete Research scores")


def _research_chain(stock: Mapping[str, Any]) -> dict[str, Any]:
    chain = stock.get("control_chain") or {}
    models = _models(stock)
    complete = chain.get("discovery_complete_factors", 0)
    controls = chain.get("control_inputs_present", 0)
    if not isinstance(complete, int) or not 0 <= complete <= 48:
        raise EvidenceGateError("invalid Core48 coverage")
    if not isinstance(controls, int) or not 0 <= controls <= 12:
        raise EvidenceGateError("invalid Control12 coverage")
    partial = chain.get("partial_discovery_factors") or []
    if any(not isinstance(i, int) or not 1 <= i <= 48 for i in partial):
        raise EvidenceGateError("invalid partial discovery factors")
    return {
        "status": "DATA_MISSING", "full_scores": {n: models[n].get("score") for n in ("S1", "S2", "S3")},
        "core48_research_candidate_complete_factors": complete,
        "core48_required": 48, "core48_partial_factor_ids": sorted(set(partial)),
        "control12_research_input_candidates": controls, "control12_required": 12,
        "canonical_factor_acceptances": 0,
        "historical_H": chain.get("historical_h"),
        "historical_H_qualified": False,
        "missing": ["D01..D48 source-complete normalized PIT factors",
                    "F49..F60 source-complete normalized PIT controls",
                    "frozen router/Gate6 plus N61/FPR all-source qualification",
                    "dated and uncontaminated winner/control historical H"],
        "partial_renormalized_DNA_is_complete": False,
    }


def _quality(stock: Mapping[str, Any]) -> dict[str, Any]:
    quality = stock.get("quality") or {}
    models = _models(stock)
    scores = {}
    for key in S14_LEGS:
        leg = quality.get(key) or {}
        scores[key] = leg.get("score")
        if scores[key] is not None and not _number(scores[key]):
            raise EvidenceGateError(f"{stock['ticker']}: invalid S14 leg {key}")
    present = sum(value is not None for value in scores.values())
    s14 = models["S14"]
    if s14.get("present") != present or s14.get("score") is not None:
        raise EvidenceGateError(f"{stock['ticker']}: S14 six-leg gate inconsistent")
    bq_count = (stock.get("sec_quality_v3") or {}).get("B_Q_risk_count")
    s6_count = (stock.get("task9_financial_evidence") or {}).get("S6_verified_count")
    reviewer = (stock.get("sec_forensic_v3") or {}).get("reviewed_risk_block_count")
    if stock["ticker"] == "INOD":
        if bq_count != 5 or s6_count != 5 or reviewer != 0:
            raise EvidenceGateError("INOD B_Q/S6/S13 preserved evidence coverage changed")
        if scores["S11"] != 0.0 or present != 3:
            raise EvidenceGateError("INOD S11 zero or 3/6 S14 evidence changed")
    return {
        "status": "REVIEW_REQUIRED" if reviewer is not None else "DATA_MISSING",
        "S14": None, "S14_valid_legs": present, "S14_required_legs": 6,
        "S14_legs": scores,
        "B_Q_evidenced_risk_legs": bq_count, "B_Q_required": 7,
        "B_Q_missing_inputs": ["pure depreciation DEPI", "comparable interest-bearing debt LVGI"],
        "S6_evidenced_components": s6_count, "S6_required": 7,
        "S6_missing_inputs": ["period-matched inventory delta", "fully reconciled RSST WC/NCO/FIN"],
        "S13_signed_decisions": reviewer, "S13_required_decisions": 7,
        "S13_blocks": S13_BLOCKS, "S13": None,
        "S4_S5": {m: models[m].get("score") for m in ("S4", "S5")},
        "S4_S5_missing": ["two year exact source-matched Beneish ratio fields",
                             "DEPI/LVGI classification and frozen risk interactions"],
        "zero_not_missing_example": {"INOD_S11": 0.0} if stock["ticker"] == "INOD" else {},
    }


def _s153(stock: Mapping[str, Any]) -> dict[str, Any]:
    rows = _models(stock)
    result = {}
    for name in MODEL_VERSIONS:
        model = rows[name]
        runtime = (model.get("evidence") or {}).get("result") or {}
        missing = list(dict.fromkeys([*(model.get("missing") or []),
                                      *(runtime.get("missing_requirements") or [])]))
        if not missing:
            raise EvidenceGateError(f"{stock['ticker']}: {name} lacks blocker evidence")
        if runtime.get("score") is not None:
            raise EvidenceGateError(f"{stock['ticker']}: partial S15.3 promoted")
        result[name] = {"status": "DATA_MISSING", "score": None,
                        "engine_status": runtime.get("status"),
                        "reported_missing_requirements": missing,
                        "ready": False}
    return result


def _pit(stock: Mapping[str, Any]) -> dict[str, Any]:
    rows = stock.get("s16_features")
    if not isinstance(rows, list) or len(rows) != len(S16_REQUIRED_FEATURES):
        raise EvidenceGateError(f"{stock['ticker']}: S16-C must enumerate 22 factors")
    keys = [r.get("key") for r in rows]
    if set(keys) != set(S16_REQUIRED_FEATURES) or len(set(keys)) != len(keys):
        raise EvidenceGateError(f"{stock['ticker']}: S16-C factor identity mismatch")
    raw_candidates = []
    for row in rows:
        # Baseline canonical acceptance is zero. Untrusted boolean flags or a
        # five-stock normalization cannot upgrade a historical feature.
        if (row.get("score") is not None or row.get("accepted") is not False
                or row.get("pit_usable") is not False):
            raise EvidenceGateError(f"{stock['ticker']}: unauthorized PIT feature promotion: {row['key']}")
        if row.get("raw"):
            raw_candidates.append(row["key"])
    verified_sec = stock.get("sec_acceptance_verifications") or {}
    if not isinstance(verified_sec, dict):
        raise EvidenceGateError("invalid SEC acceptance map")
    first_public = sum(bool(x.get("public_dissemination_at")) for x in verified_sec.values())
    provider_at = sum(bool(x.get("historical_provider_available_at")) for x in verified_sec.values())
    if first_public or provider_at:
        raise EvidenceGateError("V7 SEC PIT claims changed without a separate primary-source audit")
    return {
        "Task13": {"status": "PARTIAL", "SEC_acceptance_candidates": len(verified_sec),
                   "verified_first_publication_timestamps": first_public,
                   "verified_historical_provider_availability": provider_at,
                   "missing": ["original public dissemination timestamp", "historical provider available_at",
                               "replay-safe period/identity and adjusted price population"]},
        "Task14_S16_C": {"status": "BLOCKED", "score": None,
                        "accepted_normalized_PIT_features": 0, "required_features": 22,
                        "raw_research_candidate_features": sorted(raw_candidates),
                        "missing_normalized_features": list(S16_REQUIRED_FEATURES)},
    }


def audit_v7_report(report: Mapping[str, Any], *, report_sha256: str | None = None,
                    verification: str = "V7_BASELINE_ONLY") -> dict[str, Any]:
    """Reevaluate all other-model evidence without rediscovering raw sources."""
    verify_v7_baseline(report)
    details = {}
    for stock in report["stocks"]:
        ticker = stock["ticker"]
        details[ticker] = {"S1_S3": _research_chain(stock),
                           "S4_S5_S6_BQ_S13_S14": _quality(stock),
                           "S15_3": _s153(stock),
                           **_pit(stock)}
    if any((stock.get("sec_event_candidates_v3") or {}).get("verified_early_alerts", 0)
           for stock in report["stocks"]):
        raise EvidenceGateError("unverified early alert was promoted")
    return {
        "schema": SCHEMA, "source_checkpoint": "V7_7af654a", "checkpoint_sha256": report_sha256,
        "verification": verification,
        "accepted_research_scores": 15, "new_model_scores_accepted": 0,
        "canonical_securities": 0, "canonical_dates": 0,
        "Task11_S1_S3_full_scores": 0, "Task12_S15_3_full_scores": 0,
        "Task13_historical_PIT": "PARTIAL",
        "Task14_S16_C_normalized_PIT": "0/22",
        "Task15_S16_E": {"status": "PENDING_APPROVAL", "score": None,
                         "missing": ["user-approved 0-100 numeric estimator", "real OOS calibration"]},
        "Task16_S16_EA": {"status": "PARTIAL", "verified_alerts": 0,
                          "missing": ["independent first-publication UTC event times",
                                      "same-clock historical reference and session proof",
                                      "independent 1m/5m feed sufficiency"]},
        "S16_E_estimated": None, "S16_C_canonical": None,
        "WF9": "BLOCKED", "LearningV3": "NOT_TRAINED", "stocks": details,
    }


def load_sealed_v7(path: Path, *, phase27: Path | None = None,
                   phase28: Path | None = None) -> tuple[Mapping[str, Any], str, str]:
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise EvidenceGateError("V7 sealed report unavailable or symlinked")
    raw = path.read_bytes()
    digest = sha256(raw).hexdigest()
    seal_path = Path(f"{path}.sha256")
    if not seal_path.is_file() or seal_path.is_symlink():
        raise EvidenceGateError("V7 source seal unavailable")
    if seal_path.read_text(encoding="ascii").strip() != digest:
        raise EvidenceGateError("V7 report checksum mismatch")
    if (phase27 is None) != (phase28 is None):
        raise EvidenceGateError("both phase27 and phase28 needed for underlying replay")
    if phase27 is not None:
        from app.scoring_completion import load_report
        report = load_report(path, phase27, phase28)
        level = "V7_SOURCE_REPLAY_AND_SHA256"
    else:
        report = json.loads(raw)
        level = "V7_SHA256_SEAL_AND_CONTRACT_ONLY_NO_RAW_SOURCE_REPLAY"
    verify_v7_baseline(report)
    return report, digest, level
