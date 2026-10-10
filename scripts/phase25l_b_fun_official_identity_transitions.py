"""Source-backed 2024–2025 ticker-identity transitions for B and FUN.

Resolves documented issuer/action *event facts* for two of 30 historical
ticker conflicts; DOES NOT silently resolve SimFinId/CIK mapping, corporate
action vendor adjustment, delisting payoff date, survivorship or daily PIT.
The 464 conflicting source records stay in mandatory quarantine.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
import os
from pathlib import Path

SCHEMA="MERIDYEN_PHASE25L_B_FUN_ISSUER_TRANSITION_EVIDENCE_V1"
REPORT_SCHEMA="MERIDYEN_PHASE25R_FULL_STAGING_RESEARCH_COVERAGE_QA_V1"

# References are original SEC issuer filings, plus Barrick's official
# issuer release. Filer CIK is independent of a vendor's SimFinId.
EVIDENCE=[
 {"event":"BARNES_APOLLO_CASH_MERGER_DELIST","source_ticker":"B",
  "source_CIK":"0000009984","issuer":"Barnes Group Inc",
  "exchange":"NYSE","security_class":"Common shares, par $0.01",
  "date":"2025-01-27","source_class":"SEC_FORM_8K",
  "official_source_url":"https://www.sec.gov/Archives/edgar/data/9984/000114036125001965/ef20042046_8k.htm",
  "official_exhibit":"https://www.sec.gov/Archives/edgar/data/9984/000114036125001965/ef20042046_ex99-1.htm",
  "delisted_pre_open":"2025-01-27",
  "terminal_cash_USD_per_eligible_common_share":47.50,
  "terminal_payoff_evidence_type":"COMPLETED_CASH_MERGER_CONSIDERATION",
  "normal_2025_01_27_trading_price_exists":False,
  "historical_simfin_id_identity_certified":False,
  "proof_limit":"Cash merger consideration established; shareholder eligibility, trade settlement and exact vendor terminal-return treatment NOT reconciled."},
 {"event":"BARRICK_GOLD_TO_B_TICKER_CHANGE","source_ticker":"B",
  "source_CIK":"0000756894","issuer":"Barrick Mining Corporation",
  "exchange":"NYSE","security_class":"Common shares",
  "date":"2025-05-09","source_class":"ISSUER_2025_05_06_OFFICIAL",
  "official_source_url":"https://www.barrick.com/English/news/news-details/2025/barrick-announces-name-change-to-barrick-mining-corporation-and-election-of-directors/default.aspx",
  "prior_ticker":"GOLD","new_ticker":"B","first_trading_day_new_ticker":"2025-05-09",
  "new_cusip":"06849F108",
  "historical_simfin_id_identity_certified":False,
  "proof_limit":"Official ticker change is independently dated; vendor continuous SimFinId, change-of-identifier corporate basis and complete CIK PIT crosswalk are not proven."},
 {"event":"CEDAR_FAIR_AND_SIX_FLAGS_MERGER_EFFECTIVE","source_ticker":"FUN",
  "source_CIK":"0000811532","issuer":"Cedar Fair, L.P.",
  "exchange":"NYSE","security_class":"Depositary LP units",
  "date":"2024-07-01","source_class":"SEC_EXHIBIT_99_1",
  "official_source_url":"https://www.sec.gov/Archives/edgar/data/811532/000119312524163040/d853340dex991.htm",
  "old_FUN_lp_units_cease_trading":"2024-07-01",
  "old_lp_unit_to_new_Fun_common_ratio":1.0,
  "historical_simfin_id_identity_certified":False,
  "proof_limit":"Prior NYSE FUN denotes LP depositary units, not the July 2 new corporation common share."},
 {"event":"COMBINED_SIX_FLAGS_FUN_NEW_SECURITY","source_ticker":"FUN",
  "source_CIK":"0001999001","issuer":"Six Flags Entertainment Corporation (combined)",
  "exchange":"NYSE","security_class":"New combined issuer common shares",
  "date":"2024-07-02","source_class":"SEC_8K_AND_EXHIBIT",
  "official_source_url":"https://www.sec.gov/Archives/edgar/data/1999001/000199900124000014/fun-20240808.htm",
  "new_FUN_common_start_trading":"2024-07-02",
  "former_SIX_common_to_new_FUN_common_ratio":0.58,
  "cedar_fair_old_FUN_lp_to_new_FUN_common_ratio":1.0,
  "former_SIX_CIK":"0000701374",
  "historical_simfin_id_identity_certified":False,
  "proof_limit":"Legal and share class identity discontinuity; vendor source series cannot be joined only by ticker."},
]

def _read(path:Path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("PHASE25R_RESEARCH_QA_REPORT_MISSING")
    obj=json.loads(path.read_text(encoding="utf-8"))
    return obj if isinstance(obj,dict) else {}

def assess(path:Path):
    qa=_read(path)
    if (qa.get("schema")!=REPORT_SCHEMA
        or qa.get("status")!="21_MONTH_FULL_RESEARCH_SOURCE_COVERAGE_RECONCILED_NOT_CANONICAL"
        or qa.get("conflicting_month_ticker_exchange_identity_rows")!=464
        or qa.get("conflicting_distinct_ticker_strings")!=30
        or qa.get("canonical_approved_rows")!=0
        or qa.get("actual_WF9_executed") is not False
        or qa.get("actual_Learning_V3_executed") is not False
        or qa.get("production_DB_modified") is not False):
        raise ValueError("PHASE25R_QUARANTINE_STATUS_NOT_TRUSTED")
    conflicts=qa.get("membership_identity_conflict_quarantine")
    if not isinstance(conflicts,list) or len(conflicts)!=464:
        raise ValueError("OFFICIAL_SOURCE_COLLISION_QUARANTINE_CHANGED")
    group=Counter(x.get("ticker") for x in conflicts)
    if "B" not in group or "FUN" not in group:
        raise ValueError("B_FUN_SOURCE_COLLISION_NOT_OBSERVED")
    originals={}
    for name in ("B","FUN"):
        originals[name]=[x for x in conflicts if x.get("ticker")==name]
    return {
      "schema":SCHEMA,
      "status":"FOUR_OFFICIAL_ISSUER_IDENTITY_ACTION_REFERENCES_FOR_TWO_CONFLICT_TICKERS_NOT_FULL_PIT",
      "research_stage_version":qa["staging_version"],
      "source_conflicting_identity_rows_total":len(conflicts),
      "source_conflicting_ticker_count":qa["conflicting_distinct_ticker_strings"],
      "official_dated_event_references":len(EVIDENCE),
      "event_tickers_with_issuer_date_evidence":["B","FUN"],
      "source_ambiguous_rows_in_B_FUN":
          {k:len(v) for k,v in originals.items()},
      "source_collision_records_B_FUN":originals,
      "issuer_event_evidence":EVIDENCE,
      "cash_merger_events_with_documented_terms":1,
      "ticker_identity_change_events":1,
      "legal_security_class_merger_transition_events":2,
      "source_price_corporate_adjustment_verified":0,
      "official_historic_SimFinId_CIK_full_window_certified":0,
      "historical_daily_PIT_verified":False,
      "delisting_total_returns_certified":0,
      "canonical_eligible_securities":0,
      "source_ticker_collision_rows_remaining_quarantined":464,
      "original_source_modified":False,"operational_DB_modified":False,
      "WF9_executed":False,"Learning_V3_trained":False,
    }

def main():
    root=Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))/"S153ResearchTerminal/runtime"
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase25r",type=Path,
                        default=root/"phase25r/staging_readonly_reconciliation.json")
    parser.add_argument("--out",type=Path,
                        default=root/"phase25l/b_fun_official_historical_identity_transition_evidence.json")
    args=parser.parse_args()
    try:
        if args.out.resolve()==args.phase25r.resolve() or args.out.is_symlink():
            raise ValueError("OVERLAPPING_SOURCE_REPORT")
        obj=assess(args.phase25r)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        tmp=args.out.with_name(args.out.name+".tmp")
        if tmp.is_symlink():raise ValueError("SYMLINK_TEMP")
        tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        tmp.replace(args.out)
    except (OSError,ValueError,KeyError,TypeError,UnicodeError):
        print("PHASE25L_BLOCKED: SOURCE_QA_OR_CIK_IDENTITY_PROVENANCE_INVALID")
        return 2
    print(json.dumps({
        "status":obj["status"],
        "official_historical_issuer_events":4,
        "historical_ticker_conflict_research_groups":2,
        "total_source_conflicts_still_quarantined":464,
        "delisting_terminal_cash_contract_verified":1,
        "historical_SimFinId_CIK_full_window_approved":0,
        "canonical_approved":0,
        "out":str(args.out)},ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
