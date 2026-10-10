"""Summarize immutable Phase25M/R/S evidence reports without re-running ingestion.

These files are private Windows output artifacts. This adapter never invokes
LLMs, brokers, web APIs, or writes into the local research archive.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

SOURCE_REPORTS = {
    "issuer_actions": (
        "phase25m/issuer_cash_evidence_secondary_P2.json",
        "MERIDYEN_PHASE25M_OFFICIAL_ISSUER_DISTRIBUTION_TRIAGE_V1",
    ),
    "identity_collisions": (
        "phase25r/staging_readonly_reconciliation.json",
        "MERIDYEN_PHASE25R_FULL_STAGING_RESEARCH_COVERAGE_QA_V1",
    ),
    "sitc_curb_events": (
        "phase25s/sitc_official_reverse_split_spinoff_price_diagnostics.json",
        "MERIDYEN_PHASE25S_SITC_OFFICIAL_ACTION_SOURCE_PAIR_RESEARCH_V1",
    ),
    "b_fun_transitions": (
        "phase25l/b_fun_official_historical_identity_transition_evidence.json",
        "MERIDYEN_PHASE25L_B_FUN_ISSUER_TRANSITION_EVIDENCE_V1",
    ),
    "sec_publication_floor": (
        "phase25p/sec_acceptance_not_public_dissemination.json",
        "MERIDYEN_PHASE25P_SEC_ACCEPTED_NOT_PUBLIC_AVAILABILITY_V1",
    ),
}
MAX_REPORT_BYTES = 12 * 1024 * 1024


def _reject(reason: str) -> dict[str, Any]:
    return {"status": "INCONCLUSIVE", "reason": reason,
            "canonical_pit": False, "canonical_adjusted_prices": False,
            "wf9_executed": False, "learning_v3_executed": False}


def _read_safe_json(root: Path, relpath: str) -> tuple[dict, str]:
    path = root / relpath
    if root.is_symlink() or path.is_symlink() or any(
        parent.is_symlink() for parent in path.parents if parent != path.anchor
    ):
        raise ValueError("UNSAFE_SYMLINK")
    if not path.is_file() or path.stat().st_size > MAX_REPORT_BYTES:
        raise ValueError("MISSING_OR_LARGE_REPORT")
    raw = path.read_bytes()
    if len(raw) > MAX_REPORT_BYTES:
        raise ValueError("EXCESSIVE_REPORT")
    obj = json.loads(raw.decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("INVALID_REPORT")
    return obj, hashlib.sha256(raw).hexdigest()


def _verify_issuer_actions(x: dict) -> dict:
    if not (
        x.get("status") ==
        "P2_ISSUER_CASH_AND_UNIT_ACTION_REFERENCES_NOT_VENDOR_PRICE_CERTIFICATION"
        and x.get("unique_issuers_with_official_distribution_documents") == 3
        and x.get("individual_official_issuer_distribution_reference_events") == 6
        and x.get("source_warnings_in_these_three_issuers") == 13
        and x.get("remaining_other_issuer_source_warnings_not_reviewed_in_this_phase") == 154
        and x.get("other_candidate_issuer_total") == 127
        and x.get("canonical_adjusted_prices_certified") == 0
        and x.get("historical_CIK_full_window_certified") == 0
        and x.get("canonical_backtest_eligible") == 0
        and x.get("WF9_executed") is False
        and x.get("Learning_V3_executed") is False
        and x.get("original_data_modified") is False
        and x.get("operational_DB_modified") is False
    ):
        raise ValueError("ISSUER_ACTION_ACCEPTANCE_CONFLICT")
    return {"official_event_references": 6, "issuer_count": 3,
            "source_warnings_triaged": 13, "remaining_source_warnings": 154}


def _verify_identity_collisions(x: dict) -> dict:
    expected = {"B", "CWBC", "FUN", "STRR", "TEL", "TTE", "VIVO"}
    symbols = x.get("conflicting_strong_cohort_tickers")
    rows = x.get("membership_identity_conflict_quarantine")
    if not (
        x.get("status") ==
        "21_MONTH_FULL_RESEARCH_SOURCE_COVERAGE_RECONCILED_NOT_CANONICAL"
        and x.get("reconciled_3557_strong_monthly_price_candidates") == 3557
        and x.get("conflicting_month_ticker_exchange_identity_rows") == 464
        and x.get("duplicate_identical_month_ticker_exchange_rows") == 21
        and x.get("conflicting_distinct_ticker_strings") == 30
        and x.get("conflicting_strong_cohort_tickers_count") == 7
        and isinstance(symbols, list) and set(symbols) == expected
        and isinstance(rows, list) and len(rows) == 464
        and all(isinstance(r, dict)
                and r.get("conflicting_company_identity_quarantined") is True
                for r in rows)
        and x.get("canonical_approved_rows") == 0
        and x.get("actual_WF9_executed") is False
        and x.get("actual_Learning_V3_executed") is False
        and x.get("production_DB_modified") is False
        and x.get("source_files_modified") is False
        and x.get("network_requests") == 0
    ):
        raise ValueError("HISTORICAL_IDENTITY_CONFLICT_NOT_QUARANTINED")
    return {"ambiguous_source_rows": 464, "identical_duplicates": 21,
            "distinct_conflicting_tickers": 30,
            "strong_cohort_quarantined": sorted(expected),
            "qualified_source_price_rows": x.get(
                "reconciled_strong_candidate_source_valid_rows")}


def _verify_sitc_curb(x: dict) -> dict:
    actions = x.get("actions")
    if not (
        x.get("status") ==
        "TWO_SEC_OFFICIAL_SITC_ACTION_EVENTS_DOCUMENTED_SOURCE_PRICES_NOT_CERTIFIED"
        and x.get("issuer_documented_actions") == 2
        and x.get("official_historic_event_issuer_CIK") == "0000894315"
        and isinstance(actions, list) and len(actions) == 2
        and {a.get("event_type") for a in actions if isinstance(a, dict)}
        == {"REVERSE_SPLIT", "SPINOFF"}
        and all(a.get("official_event_issuer_only") is True and
                a.get("independent_adjusted_price_certified") is False and
                a.get("lookahead_free_backtest_allowed") is False for a in actions)
        and x.get("historical_SimFinId_CIK_full_window_verified") == 0
        and x.get("corporate_action_vendor_adjusted_price_certified") == 0
        and x.get("canonical_eligible_securities") == 0
        and x.get("WF9_executed") is False
        and x.get("Learning_V3_trained") is False
        and x.get("production_DB_modified") is False
        and x.get("original_vendor_sources_modified") is False
        and x.get("network_requests") == 0
    ):
        raise ValueError("SITC_OFFICIAL_ACTION_NOT_PRICE_CERTIFICATION")
    return {"issuer_actions": 2, "issuer_cik": "0000894315",
            "source_price_pairs": x.get("source_pair_diagnostics_computed"),
            "adjusted_price_certifications": 0}


def _verify_b_fun_transitions(x: dict) -> dict:
    events = x.get("issuer_event_evidence")
    event_map = {
        e.get("event"): e for e in events if isinstance(e, dict)
    } if isinstance(events, list) else {}
    expected_events = {
        "BARNES_APOLLO_CASH_MERGER_DELIST": "0000009984",
        "BARRICK_GOLD_TO_B_TICKER_CHANGE": "0000756894",
        "CEDAR_FAIR_AND_SIX_FLAGS_MERGER_EFFECTIVE": "0000811532",
        "COMBINED_SIX_FLAGS_FUN_NEW_SECURITY": "0001999001",
    }
    if not (
        x.get("status") ==
        "FOUR_OFFICIAL_ISSUER_IDENTITY_ACTION_REFERENCES_FOR_TWO_CONFLICT_TICKERS_NOT_FULL_PIT"
        and x.get("source_conflicting_identity_rows_total") == 464
        and x.get("source_conflicting_ticker_count") == 30
        and x.get("official_dated_event_references") == 4
        and x.get("event_tickers_with_issuer_date_evidence") == ["B", "FUN"]
        and x.get("source_ticker_collision_rows_remaining_quarantined") == 464
        and x.get("cash_merger_events_with_documented_terms") == 1
        and x.get("ticker_identity_change_events") == 1
        and x.get("legal_security_class_merger_transition_events") == 2
        and isinstance(events, list) and len(events) == 4
        and set(event_map) == set(expected_events)
        and all(event_map[name].get("source_CIK") == cik
                for name, cik in expected_events.items())
        and event_map["BARNES_APOLLO_CASH_MERGER_DELIST"].get(
            "terminal_cash_USD_per_eligible_common_share") == 47.50
        and all(isinstance(e, dict)
                and e.get("historical_simfin_id_identity_certified") is False
                and str(e.get("official_source_url", "")).startswith("https://")
                for e in events)
        and x.get("source_price_corporate_adjustment_verified") == 0
        and x.get("official_historic_SimFinId_CIK_full_window_certified") == 0
        and x.get("historical_daily_PIT_verified") is False
        and x.get("delisting_total_returns_certified") == 0
        and x.get("canonical_eligible_securities") == 0
        and x.get("original_source_modified") is False
        and x.get("operational_DB_modified") is False
        and x.get("WF9_executed") is False
        and x.get("Learning_V3_trained") is False
    ):
        raise ValueError("B_FUN_ISSUER_EVENTS_NOT_FULL_PIT")
    return {"official_issuer_event_references": 4,
            "historically_ambiguous_tickers_reviewed": ["B", "FUN"],
            "source_collisions_still_quarantined": 464,
            "documented_barnes_cash_merger_usd_per_eligible_share": 47.50,
            "delisting_total_return_certified": False}


def _verify_sec_publication_floor(x: dict) -> dict:
    # Refer to original *existing* M10 evidence rather than inventing
    # a generic publication timestamp from a filing period-end.
    from core.research.sec_publication_gate import OBSERVED_ACCEPTANCES

    records = x.get("records")
    expected = {f.accession: f for f in OBSERVED_ACCEPTANCES}
    actual = {
        r.get("accession"): r for r in records if isinstance(r, dict)
    } if isinstance(records, list) else {}
    if not (
        x.get("status") ==
        "THREE_SEC_INDEX_ACCEPTANCES_DOCUMENTED_NO_HISTORIC_FEATURE_PIT_CERTIFICATION"
        and x.get("observed_official_SEC_index_acceptance_stamps") == 3
        and x.get("historical_public_dissemination_stamps_independently_verified") == 0
        and x.get("model_signal_eligible_records") == 0
        and isinstance(records, list) and len(records) == 3
        and set(actual) == set(expected)
        and all(
            actual[acc].get("ticker") == f.ticker
            and actual[acc].get("cik") == f.cik
            and actual[acc].get("SEC_index_accepted_at_ET") == f.sec_index_accepted_et
            and actual[acc].get("SEC_index_accepted_at_UTC") ==
                f.sec_accepted_at_utc.isoformat()
            and actual[acc].get("original_SEC_index_url") == f.sec_index_url
            and actual[acc].get("public_dissemination_time_independently_verified") is False
            and actual[acc].get("SEC_feature_available_at_independently_verified") is False
            and actual[acc].get("feature_usable_for_historical_training") is False
            for acc, f in expected.items()
        )
        and x.get("operational_DB_modified") is False
        and x.get("models_modified") is False
        and x.get("WF9_executed") is False
        and x.get("Learning_V3_executed") is False
    ):
        raise ValueError("SEC_ACCEPTED_TIMESTAMP_NOT_PUBLIC_AVAILABLE_AT")
    return {"SEC_index_accepted_timestamp_records": 3,
            "independently_verified_public_dissemination_records": 0,
            "model_features_historically_usable": 0,
            "publication_gate": "DENY_UNTIL_PUBLIC_AND_FEATURE_CLOCKS_VERIFIED"}


def phase25_evidence_snapshot(root: Path, name: str) -> dict[str, Any]:
    """Validate one existing source report: never silently promote to PIT."""
    entry = SOURCE_REPORTS.get(name)
    if entry is None:
        return _reject("UNRECOGNIZED_REPORT_NAME")
    try:
        report, digest = _read_safe_json(root, entry[0])
        if report.get("schema") != entry[1]:
            return _reject("EVIDENCE_SCHEMA_MISMATCH")
        verifier = {
            "issuer_actions": _verify_issuer_actions,
            "identity_collisions": _verify_identity_collisions,
            "sitc_curb_events": _verify_sitc_curb,
            "b_fun_transitions": _verify_b_fun_transitions,
            "sec_publication_floor": _verify_sec_publication_floor,
        }[name]
        fields = verifier(report)
        return {"status": "VERIFIED_EXISTING_SOURCE_REPORT_RESEARCH_ONLY",
                "kind": name, "source_report_sha256": digest,
                **fields, "canonical_pit": False,
                "canonical_adjusted_prices": False,
                "wf9_executed": False, "learning_v3_executed": False}
    except (OSError, ValueError, UnicodeError, KeyError, TypeError, OverflowError):
        return _reject("PRIVATE_REPORT_ABSENT_OR_UNCERTIFIED")


def local_phase25_sources() -> dict[str, Any]:
    """Non-network snapshot; a missing private report is explicitly inconclusive."""
    root = Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / (
        "S153ResearchTerminal/runtime")
    return {name: phase25_evidence_snapshot(root, name)
            for name in SOURCE_REPORTS}
