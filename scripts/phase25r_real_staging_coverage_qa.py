"""Phase25R: independent read-only audit of the *real* Phase25Q research staging.

Enumerates monthly historical-list churn and vendor price-depth reconciliation.
No future point-in-time availability is assumed, no delisted terminal payoff is
invented, and zero source rows become canonical or trigger WF9/Learning V3.
"""
from __future__ import annotations
import argparse
from datetime import date
import hashlib
from data.providers.alpha_vantage_pit_universe import AlphaVantagePitUniverseProvider
from collections import Counter,defaultdict
from contextlib import closing
import json,os
from pathlib import Path
import sqlite3

from scripts.phase25b_simfin_distinct_daily_depth_audit import PER_MONTH_KEYS, WINDOW

SCHEMA="MERIDYEN_PHASE25R_FULL_STAGING_RESEARCH_COVERAGE_QA_V1"
BLOCKERS=[
 "HISTORICAL_MONTHLY_MEMBERSHIP_RETRIEVED_RETROSPECTIVELY_2026",
 "SURVIVORSHIP_CENSORING_AND_DELISTING_EXIT_RETURN_NOT_PROVEN",
 "SIMFIN_ADJUSTED_PRICE_VENDOR_RETRO_ADJUSTMENT_NOT_INDEPENDENTLY_VERIFIED",
 "HISTORICAL_DAILY_ISSUER_CIK_AND_SHARE_CLASS_NOT_CERTIFIED",
 "SEC_ACCEPTED_AT_OR_DISSEMINATION_AVAILABLE_AT_INCOMPLETE",
 "NO_APPROVED_CANONICAL_IMPORT_OR_MATURED_252_SESSION_LEARNING_LABELS",
]

def _load(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("REQUIRED_REPORT_MISSING")
    o=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(o,dict):
        raise ValueError("REPORT_NOT_OBJECT")
    return o

def analyze(phase25q_manifest:Path,phase25b:Path,pit_dir:Path,backup_check=True):
    m=_load(phase25q_manifest)
    b=_load(phase25b)
    if (
       m.get("schema")!="MERIDYEN_PHASE25Q_VERSIONED_RESEARCH_STAGING_V1"
       or m.get("status")!="RESEARCH_ONLY_NOT_CANONICAL_PIT"
       or m.get("period")!=WINDOW
       or m.get("month_end_snapshots")!=21
       or m.get("month_end_retrieved_after_backtest_window") is not True
       or m.get("canonical_ready") is not False
       or m.get("backtest_eligible_securities")!=0
       or m.get("production_DB_modified") is not False
       or b.get("schema")!="MERIDYEN_PHASE25B_SIMFIN_DISTINCT_DATE_QUALITY_RESEARCH_V1"
       or b.get("status")!="DISTINCT_SIMFINID_DATE_COUNTS_VERIFIED_RESEARCH_ONLY_NOT_PIT"
       or b.get("window")!=WINDOW or b.get("canonical_eligible")!=0
       or b.get("source_price_file_SHA256")!=m.get("source_price_sha256")
       or b.get("phase25a_prior_candidate_21months")!=3557
    ):
        raise ValueError("STAGING_SOURCE_MISMATCH")
    db=Path(m["staging_db"])
    backup=Path(m["backup_db"])
    if (db.is_symlink() or not db.is_file() or
        backup.is_symlink() or not backup.is_file()):
        raise ValueError("STAGING_DB_OR_BACKUP_MISSING")
    monthsets=defaultdict(set)
    month_rows=Counter()
    counts=Counter()
    matched_rows=defaultdict(int)
    original_snapshot_sha={}
    with closing(sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True,timeout=10)) as con:
        con.execute("PRAGMA query_only=ON")
        if con.execute("PRAGMA quick_check").fetchone()[0]!="ok":
            raise ValueError("STAGING_DB_QUICK_CHECK_FAILED")
        for source_key,sha in con.execute("SELECT source_key,source_sha256 FROM source_artifacts WHERE kind=\'ALPHAVANTAGE_HISTORIC_MONTH_END_RETRIEVED_RETROSPECTIVELY\'"):
            original_snapshot_sha[source_key]=sha
        for (month,ticker,exchange) in con.execute(
            "SELECT month_end,ticker,exchange FROM monthly_research_membership"):
            monthsets[month[:7]].add((ticker,exchange))
            month_rows[month[:7]]+=1
        for key,query in {
            "source_price_rows":"SELECT COUNT(*) FROM source_daily_price",
            "distinct_source_simfin_ids":"SELECT COUNT(DISTINCT simfin_id) FROM source_daily_price",
            "distinct_source_price_tickers":"SELECT COUNT(DISTINCT ticker) FROM source_daily_price",
            "same_month_listed_valid_price_rows":"SELECT COUNT(*) FROM source_daily_price WHERE listed_in_same_month_end_archive=1",
            "unlisted_month_valid_price_rows":"SELECT COUNT(*) FROM source_daily_price WHERE listed_in_same_month_end_archive=0",
            "phase24_candidate_identity_rows":"SELECT COUNT(*) FROM candidate_identity",
            "phase25k_quarantined_security_rows":"SELECT COUNT(*) FROM candidate_gate",
            "historical_identity_approved_rows":"SELECT COUNT(*) FROM candidate_identity WHERE historical_CIK_identity_certified!=0",
            "canonical_price_approved_rows":"SELECT COUNT(*) FROM source_daily_price WHERE source_adjustment_certified!=0",
        }.items():
            counts[key]=con.execute(query).fetchone()[0]
        for sid,ticker,n in con.execute(
            "SELECT simfin_id,ticker,COUNT(*) FROM source_daily_price "
            "WHERE listed_in_same_month_end_archive=1 GROUP BY simfin_id,ticker"
        ):
            matched_rows[(str(sid),ticker)] = n
    if backup_check:
        with closing(sqlite3.connect(backup.resolve().as_uri()+"?mode=ro",uri=True,timeout=10)) as bak:
            bak.execute("PRAGMA query_only=ON")
            if bak.execute("PRAGMA quick_check").fetchone()[0]!="ok":
                raise ValueError("STAGING_BACKUP_QUICK_CHECK_FAILED")
            if bak.execute("SELECT COUNT(*) FROM source_daily_price").fetchone()[0]!=counts["source_price_rows"]:
                raise ValueError("BACKUP_SOURCE_ROW_COUNT_MISMATCH")
    records=b.get("candidate_depth_records")
    if not isinstance(records,list) or len(records)!=3557:
        raise ValueError("PHASE25B_DEPTH_COHORT_CHANGED")
    total=0
    mismatches=[]
    for x in records:
        n=matched_rows.get((str(x["SimFinId"]),str(x["ticker"])),0)
        expected=x["valid_ohlc_positive_source_adjusted_rows"]
        total+=n
        if n!=expected and len(mismatches)<30:
            mismatches.append({"SimFinId":x["SimFinId"],"ticker":x["ticker"],
                               "staging_listed_price_rows":n,
                               "phase25b_expected_source_rows":expected})
    if total!=b["metrics"]["valid_source_rows"] or mismatches:
        raise ValueError("3557_INDEPENDENT_PRICE_DEPTH_COUNTS_DID_NOT_RECONCILE")
    if (counts["source_price_rows"]!=m["source_daily_valid_price_rows"]
        or sum(month_rows.values())!=m["monthly_membership_rows"]
        or counts["phase24_candidate_identity_rows"]!=5307
        or counts["phase25k_quarantined_security_rows"]!=133
        or counts["historical_identity_approved_rows"]!=0
        or counts["canonical_price_approved_rows"]!=0):
        raise ValueError("STAGING_ROW_COUNT_OR_CANONICAL_GATE_FAILURE")
    # The source provider sometimes supplies two distinct issuer names for the
    # SAME month/exchange/ticker. Never resolve these by accepting first row.
    identity_conflicts=[]
    duplicate_identical=0
    conflict_tickers=set()
    source_rows=0
    for key in PER_MONTH_KEYS:
        month_end=next((x for x in original_snapshot_sha if x.startswith(key)),None)
        if not month_end:
            raise ValueError("MONTH_SOURCE_PROVENANCE_MISSING")
        csvfile=pit_dir/(month_end+".csv")
        if csvfile.is_symlink() or not csvfile.is_file():
            raise ValueError("MONTH_SOURCE_CSV_MISSING")
        raw=csvfile.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=original_snapshot_sha[month_end]:
            raise ValueError("SOURCE_MONTH_SHA256_NOT_EQUAL_TO_STAGING")
        records_source=AlphaVantagePitUniverseProvider.parse_csv(
            raw.decode("utf-8-sig"),as_of=date.fromisoformat(month_end))
        seen={}
        for x in records_source:
            source_rows+=1
            ident=(x.ticker,x.exchange.value)
            candidate=(x.name,x.ipo_date.isoformat() if x.ipo_date else None)
            if ident in seen:
                if seen[ident]==candidate:
                    duplicate_identical+=1
                else:
                    conflict_tickers.add(x.ticker)
                    identity_conflicts.append({
                        "month_end":month_end,"ticker":x.ticker,"exchange":x.exchange.value,
                        "first_issuer_name":seen[ident][0],
                        "second_issuer_name":candidate[0],
                        "first_IPO":seen[ident][1],"second_IPO":candidate[1],
                        "conflicting_company_identity_quarantined":True})
            else:
                seen[ident]=candidate
    if (source_rows!=m["source_counts"]["month_snapshot_source_records"]
        or len(identity_conflicts)+duplicate_identical!=
          source_rows-m["monthly_membership_rows"]):
        raise ValueError("SOURCE_MONTH_DUPLICATES_NOT_RECONCILED")
    strong_tickers={str(x["ticker"]) for x in records}
    affected_strong=sorted(strong_tickers.intersection(conflict_tickers))
    churn=[]
    for i,mon in enumerate(PER_MONTH_KEYS):
        present=monthsets.get(mon,set())
        if not present:raise ValueError("HISTORIC_MONTH_MISSING_FROM_STAGE")
        previous=monthsets.get(PER_MONTH_KEYS[i-1],set()) if i else set()
        prior_only=previous-present if i else set()
        new=present-previous if i else set()
        churn.append({
           "month":mon,
           "ticker_exchange_snapshot_members":len(present),
           "new_since_previous_month_NOT_IPO_CERTIFIED":len(new) if i else None,
           "absent_since_previous_month_NOT_DELIST_CERTIFIED":len(prior_only) if i else None,
           "daily_PIT_universe_certified":False,
        })
    stats=m.get("source_counts",{})
    return {
      "schema":SCHEMA,
      "status":"21_MONTH_FULL_RESEARCH_SOURCE_COVERAGE_RECONCILED_NOT_CANONICAL",
      "staging_version":m["staging_version"],
      "window":WINDOW,
      "price_and_membership_counts":dict(counts),
      "reconciled_3557_strong_monthly_price_candidates":3557,
      "reconciled_strong_candidate_source_valid_rows":total,
      "original_monthly_source_records":stats.get("month_snapshot_source_records"),
      "distinct_monthly_ticker_exchange_keys":m["monthly_membership_rows"],
      "conflicting_month_ticker_exchange_identity_rows":len(identity_conflicts),
      "duplicate_identical_month_ticker_exchange_rows":duplicate_identical,
      "conflicting_distinct_ticker_strings":len(conflict_tickers),
      "conflicting_strong_cohort_tickers":affected_strong,
      "conflicting_strong_cohort_tickers_count":len(affected_strong),
      "membership_identity_conflict_quarantine":identity_conflicts,
      "source_duplicate_month_ticker_exchange_records_potential_identity_risk":
          stats.get("month_snapshot_source_records",0)-m["monthly_membership_rows"],
      "monthly_membership_churn_research_only":churn,
      "source_OHLC_invalid_rows":stats.get("invalid_OHLC"),
      "source_nonpositive_adjusted_or_bad_volume_rows":
          stats.get("nonpositive_adj_or_invalid_volume"),
      "acceptance_blockers":BLOCKERS,
      "independent_month_end_actual_available_at_proven":False,
      "delisting_terminal_price_total_return_proven":False,
      "all_issued_corporate_actions_proven":False,
      "independently_verified_issuer_daily_identity":False,
      "actual_WF9_executed":False,"actual_Learning_V3_executed":False,
      "canonical_approved_rows":0,
      "production_DB_modified":False,"source_files_modified":False,
      "network_requests":0,
    }

def main():
    root=Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))/"S153ResearchTerminal/runtime"
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--pit-dir",type=Path,
                   default=root/"phase19/pit_staging")
    p.add_argument("--phase25b",type=Path,
                   default=root/"phase25b/simfin_distinct_daily_depth_research.json")
    p.add_argument("--out",type=Path,
                   default=root/"phase25r/staging_readonly_reconciliation.json")
    a=p.parse_args()
    try:
        if a.out.resolve() in {a.manifest.resolve(),a.phase25b.resolve()} or a.out.is_symlink():
            raise ValueError("UNSAFE_OUTPUT")
        rep=analyze(a.manifest,a.phase25b,a.pit_dir)
        a.out.parent.mkdir(parents=True,exist_ok=True)
        temp=a.out.with_name(a.out.name+".tmp")
        if temp.is_symlink():raise ValueError("SYMLINK_TEMP")
        temp.write_text(json.dumps(rep,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        temp.replace(a.out)
    except (OSError,ValueError,sqlite3.Error,TypeError,KeyError):
        print("PHASE25R_BLOCKED: STAGING_INTEGRITY_OR_PRIOR_DATA_RECONCILIATION")
        return 2
    print(json.dumps({
       "status":rep["status"],
       "price_rows":rep["price_and_membership_counts"]["source_price_rows"],
       "reconciled_3557_source_rows":rep["reconciled_strong_candidate_source_valid_rows"],
       "member_rows":rep["distinct_monthly_ticker_exchange_keys"],
       "conflicting_identity_month_rows":rep["conflicting_month_ticker_exchange_identity_rows"],
       "strong_cohort_tickers_quarantined":rep["conflicting_strong_cohort_tickers"],
       "duplicates_potential_identity_risk":
         rep["source_duplicate_month_ticker_exchange_records_potential_identity_risk"],
       "canonical_accepted":0,
       "WF9_executed":False,
       "Learning_V3_executed":False,
       "report":str(a.out)},indent=2,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
