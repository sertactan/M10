"""Archive-independent tests for read-only Phase25M/R/S evidence snapshots."""
from __future__ import annotations

import json

from core.hermes_team.phase25_source_evidence import (
    local_phase25_sources,
    phase25_evidence_snapshot,
)


def _store(root, path, payload):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def _m():
    return {
        "schema": "MERIDYEN_PHASE25M_OFFICIAL_ISSUER_DISTRIBUTION_TRIAGE_V1",
        "status": "P2_ISSUER_CASH_AND_UNIT_ACTION_REFERENCES_NOT_VENDOR_PRICE_CERTIFICATION",
        "unique_issuers_with_official_distribution_documents": 3,
        "individual_official_issuer_distribution_reference_events": 6,
        "source_warnings_in_these_three_issuers": 13,
        "remaining_other_issuer_source_warnings_not_reviewed_in_this_phase": 154,
        "other_candidate_issuer_total": 127,
        "canonical_adjusted_prices_certified": 0,
        "historical_CIK_full_window_certified": 0,
        "canonical_backtest_eligible": 0,
        "WF9_executed": False, "Learning_V3_executed": False,
        "original_data_modified": False, "operational_DB_modified": False,
    }


def _r():
    return {
        "schema": "MERIDYEN_PHASE25R_FULL_STAGING_RESEARCH_COVERAGE_QA_V1",
        "status": "21_MONTH_FULL_RESEARCH_SOURCE_COVERAGE_RECONCILED_NOT_CANONICAL",
        "reconciled_3557_strong_monthly_price_candidates": 3557,
        "reconciled_strong_candidate_source_valid_rows": 1557903,
        "conflicting_month_ticker_exchange_identity_rows": 464,
        "duplicate_identical_month_ticker_exchange_rows": 21,
        "conflicting_distinct_ticker_strings": 30,
        "conflicting_strong_cohort_tickers_count": 7,
        "conflicting_strong_cohort_tickers": [
            "B", "CWBC", "FUN", "STRR", "TEL", "TTE", "VIVO"
        ],
        "membership_identity_conflict_quarantine": [
            {"conflicting_company_identity_quarantined": True}
            for _ in range(464)
        ],
        "canonical_approved_rows": 0,
        "actual_WF9_executed": False,
        "actual_Learning_V3_executed": False,
        "production_DB_modified": False,
        "source_files_modified": False,
        "network_requests": 0,
    }


def _s():
    return {
        "schema": "MERIDYEN_PHASE25S_SITC_OFFICIAL_ACTION_SOURCE_PAIR_RESEARCH_V1",
        "status": "TWO_SEC_OFFICIAL_SITC_ACTION_EVENTS_DOCUMENTED_SOURCE_PRICES_NOT_CERTIFIED",
        "issuer_documented_actions": 2,
        "source_pair_diagnostics_computed": 2,
        "official_historic_event_issuer_CIK": "0000894315",
        "actions": [
            {"event_type": kind, "official_event_issuer_only": True,
             "independent_adjusted_price_certified": False,
             "lookahead_free_backtest_allowed": False}
            for kind in ("REVERSE_SPLIT", "SPINOFF")
        ],
        "historical_SimFinId_CIK_full_window_verified": 0,
        "corporate_action_vendor_adjusted_price_certified": 0,
        "canonical_eligible_securities": 0,
        "WF9_executed": False, "Learning_V3_trained": False,
        "production_DB_modified": False, "original_vendor_sources_modified": False,
        "network_requests": 0,
    }



def _l():
    return {
        "schema": "MERIDYEN_PHASE25L_B_FUN_ISSUER_TRANSITION_EVIDENCE_V1",
        "status": "FOUR_OFFICIAL_ISSUER_IDENTITY_ACTION_REFERENCES_FOR_TWO_CONFLICT_TICKERS_NOT_FULL_PIT",
        "source_conflicting_identity_rows_total": 464,
        "source_conflicting_ticker_count": 30,
        "official_dated_event_references": 4,
        "event_tickers_with_issuer_date_evidence": ["B", "FUN"],
        "source_ticker_collision_rows_remaining_quarantined": 464,
        "cash_merger_events_with_documented_terms": 1,
        "ticker_identity_change_events": 1,
        "legal_security_class_merger_transition_events": 2,
        "issuer_event_evidence": [
            {"historical_simfin_id_identity_certified": False,
             "official_source_url": "https://www.sec.gov/Archives/test",
             "event": event, "source_CIK": cik,
             **({"terminal_cash_USD_per_eligible_common_share": 47.50}
                if event == "BARNES_APOLLO_CASH_MERGER_DELIST" else {})}
            for event, cik in (
                ("BARNES_APOLLO_CASH_MERGER_DELIST", "0000009984"),
                ("BARRICK_GOLD_TO_B_TICKER_CHANGE", "0000756894"),
                ("CEDAR_FAIR_AND_SIX_FLAGS_MERGER_EFFECTIVE", "0000811532"),
                ("COMBINED_SIX_FLAGS_FUN_NEW_SECURITY", "0001999001"),
            )
        ],
        "source_price_corporate_adjustment_verified": 0,
        "official_historic_SimFinId_CIK_full_window_certified": 0,
        "historical_daily_PIT_verified": False,
        "delisting_total_returns_certified": 0,
        "canonical_eligible_securities": 0,
        "original_source_modified": False,
        "operational_DB_modified": False,
        "WF9_executed": False,
        "Learning_V3_trained": False,
    }



def _p():
    from core.research.sec_publication_gate import OBSERVED_ACCEPTANCES
    return {
        "schema": "MERIDYEN_PHASE25P_SEC_ACCEPTED_NOT_PUBLIC_AVAILABILITY_V1",
        "status": "THREE_SEC_INDEX_ACCEPTANCES_DOCUMENTED_NO_HISTORIC_FEATURE_PIT_CERTIFICATION",
        "observed_official_SEC_index_acceptance_stamps": 3,
        "historical_public_dissemination_stamps_independently_verified": 0,
        "model_signal_eligible_records": 0,
        "records": [{
            "ticker": f.ticker, "cik": f.cik, "accession": f.accession,
            "form": f.form, "period_end": f.reported_period_end,
            "SEC_index_accepted_at_ET": f.sec_index_accepted_et,
            "SEC_index_accepted_at_UTC": f.sec_accepted_at_utc.isoformat(),
            "original_SEC_index_url": f.sec_index_url,
            "public_dissemination_time_independently_verified": False,
            "SEC_feature_available_at_independently_verified": False,
            "feature_usable_for_historical_training": False,
        } for f in OBSERVED_ACCEPTANCES],
        "operational_DB_modified": False, "models_modified": False,
        "WF9_executed": False, "Learning_V3_executed": False,
    }


def test_all_five_real_format_reports_stay_research_only(tmp_path):
    base = tmp_path / "S153ResearchTerminal" / "runtime"
    _store(base, "phase25m/issuer_cash_evidence_secondary_P2.json", _m())
    _store(base, "phase25r/staging_readonly_reconciliation.json", _r())
    _store(base, "phase25s/sitc_official_reverse_split_spinoff_price_diagnostics.json", _s())
    _store(base, "phase25l/b_fun_official_historical_identity_transition_evidence.json", _l())
    _store(base, "phase25p/sec_acceptance_not_public_dissemination.json", _p())
    for name in ("issuer_actions", "identity_collisions", "sitc_curb_events", "b_fun_transitions", "sec_publication_floor"):
        result = phase25_evidence_snapshot(base, name)
        assert result["status"] == "VERIFIED_EXISTING_SOURCE_REPORT_RESEARCH_ONLY"
        assert result["canonical_pit"] is False
        assert result["canonical_adjusted_prices"] is False
        assert result["wf9_executed"] is False
        assert result["learning_v3_executed"] is False
        assert len(result["source_report_sha256"]) == 64
    assert phase25_evidence_snapshot(base, "identity_collisions")[
        "strong_cohort_quarantined"] == [
            "B", "CWBC", "FUN", "STRR", "TEL", "TTE", "VIVO"
        ]


def test_tampered_issuer_report_never_promoted(tmp_path):
    item = _m()
    item["canonical_adjusted_prices_certified"] = 1
    _store(tmp_path, "phase25m/issuer_cash_evidence_secondary_P2.json", item)
    x = phase25_evidence_snapshot(tmp_path, "issuer_actions")
    assert x["status"] == "INCONCLUSIVE"
    assert x["canonical_pit"] is False


def test_identity_quarantine_tamper_never_promoted(tmp_path):
    report = _r()
    report["membership_identity_conflict_quarantine"] = report[
        "membership_identity_conflict_quarantine"][:-1]
    _store(tmp_path, "phase25r/staging_readonly_reconciliation.json", report)
    assert phase25_evidence_snapshot(tmp_path, "identity_collisions")[
        "status"] == "INCONCLUSIVE"


def test_sitc_unverified_adjustment_stays_inconclusive(tmp_path):
    report = _s()
    report["actions"][0]["independent_adjusted_price_certified"] = True
    _store(tmp_path,
           "phase25s/sitc_official_reverse_split_spinoff_price_diagnostics.json",
           report)
    assert phase25_evidence_snapshot(tmp_path, "sitc_curb_events")[
        "status"] == "INCONCLUSIVE"


def test_absent_or_unrecognized_private_report(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    results = local_phase25_sources()
    assert all(value["status"] == "INCONCLUSIVE" for value in results.values())
    assert phase25_evidence_snapshot(tmp_path, "not-a-phase")[
        "reason"] == "UNRECOGNIZED_REPORT_NAME"


def test_b_fun_transition_tamper_is_inconclusive(tmp_path):
    report = _l()
    report["source_ticker_collision_rows_remaining_quarantined"] = 0
    _store(tmp_path,
           "phase25l/b_fun_official_historical_identity_transition_evidence.json",
           report)
    value = phase25_evidence_snapshot(tmp_path, "b_fun_transitions")
    assert value["status"] == "INCONCLUSIVE"
    assert value["canonical_pit"] is False


def test_edgar_acceptance_alone_does_not_create_model_available_at(tmp_path):
    report = _p()
    report["records"][0]["public_dissemination_time_independently_verified"] = True
    _store(tmp_path, "phase25p/sec_acceptance_not_public_dissemination.json", report)
    blocked = phase25_evidence_snapshot(tmp_path, "sec_publication_floor")
    assert blocked["status"] == "INCONCLUSIVE"
    assert blocked["canonical_pit"] is False
