"""Phase25S: official SEC-supported SITC 2024 split/spinoff vs local real source bars.

Two issuer/corporate action facts are from primary 2024 SEC 8-K evidence.
Source price diagnostics are NOT independent verification of SimFin's
adjustment process, historical SimFinId mapping, trading price, or PIT status.
Reads Phase25Q SQLite in strict query-only mode; no network or operational DB.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import date
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3

SCHEMA="MERIDYEN_PHASE25S_SITC_OFFICIAL_ACTION_SOURCE_PAIR_RESEARCH_V1"
DOCS=[
    {
      "event_id":"SITC_2024_REVERSE_SPLIT",
      "ticker":"SITC","SEC_filer_CIK":"0000894315",
      "share_class":"SITE Centers Corp NYSE common shares",
      "event_type":"REVERSE_SPLIT",
      "official_event_effective":"2024-08-16T17:00:00-04:00",
      "first_split_adjusted_trading_day":"2024-08-19",
      "record_date":None,"spin_child_ticker":None,
      "old_common_shares_per_new_common_share":4,
      "new_common_shares_per_old_common_share":0.25,
      "new_cusip":"82981J851",
      "filing_document":"https://www.sec.gov/Archives/edgar/data/894315/000095017024099069/sitc-20240816.htm",
      "document_form":"8-K",
      "document_signed_at":"2024-08-20",
      "verified_claim":"Effective Aug 16 17:00 Eastern; trading adjusted Aug 19; 1 for 4 reverse split and CUSIP change",
      "official_source_supports_corporate_action":True,
      "official_document_filing_acceptance_at_UTC_verified":False,
    },
    {
      "event_id":"SITC_2024_CURB_SPINOFF",
      "ticker":"SITC","SEC_filer_CIK":"0000894315",
      "share_class":"SITE Centers Corp NYSE common shares",
      "event_type":"SPINOFF",
      "official_event_effective":"2024-10-01",
      "first_split_adjusted_trading_day":None,
      "record_date":"2024-09-23","spin_child_ticker":"CURB",
      "child_common_shares_per_parent_common_share":2,
      "new_cusip":None,
      "filing_document":"https://www.sec.gov/Archives/edgar/data/894315/000119312524231147/d104351d8k.htm",
      "exhibit_document":"https://www.sec.gov/Archives/edgar/data/894315/000119312524231147/d104351dex991.htm",
      "document_form":"8-K",
      "document_signed_at":None,
      "verified_claim":"On Oct 1, 2024 CURB spinoff: 2 new CURB shares per 1 SITC held on Sep 23 record date",
      "official_source_supports_corporate_action":True,
      "official_document_filing_acceptance_at_UTC_verified":False,
    }
]
PAIR_DATES={
    "SITC_2024_REVERSE_SPLIT":("2024-08-16","2024-08-19"),
    "SITC_2024_CURB_SPINOFF":("2024-09-30","2024-10-01"),
}


def _load(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("PRIVATE_PHASE25Q_MANIFEST_MISSING")
    obj=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj,dict):
        raise ValueError("MANIFEST_INVALID")
    return obj


def reconcile(manifest_path:Path, *, expected_simfin_id="998403"):
    manifest=_load(manifest_path)
    if (
        manifest.get("schema")!="MERIDYEN_PHASE25Q_VERSIONED_RESEARCH_STAGING_V1"
        or manifest.get("status")!="RESEARCH_ONLY_NOT_CANONICAL_PIT"
        or manifest.get("period")!={"start":"2024-01-01","end":"2025-09-30"}
        or manifest.get("month_end_retrieved_after_backtest_window") is not True
        or manifest.get("canonical_ready") is not False
        or manifest.get("backtest_eligible_securities")!=0
        or manifest.get("production_DB_modified") is not False
    ):
        raise ValueError("SOURCE_DATA_IS_NOT_UNCERTIFIED_RESEARCH_STAGE")
    if expected_simfin_id!="998403":
        raise ValueError("P1_SITC_SIMFIN_ID_CHANGED")
    db=Path(manifest["staging_db"])
    if db.is_symlink() or not db.is_file():
        raise ValueError("LOCAL_STAGE_DB_MISSING")
    # Fail if user-replaced/corrupted SQLite rather than silently accepting
    # untrusted rows as historical verification. Original prices read only.
    bars={}
    with closing(sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True,timeout=15)) as con:
        con.execute("PRAGMA query_only=ON")
        if con.execute("PRAGMA quick_check").fetchone()[0]!="ok":
            raise ValueError("STAGE_SQLITE_INTEGRITY_FAILED")
        for ds,raw,adj,simfin in con.execute(
            "SELECT trade_date,source_close,source_adj_close,simfin_id "
            "FROM source_daily_price "
            "WHERE ticker='SITC' AND trade_date IN (?,?,?,?)",
            ("2024-08-16","2024-08-19","2024-09-30","2024-10-01")
        ):
            if not isinstance(ds,str):
                raise ValueError("SOURCE_TRADE_DATE_INVALID")
            if str(simfin)!=expected_simfin_id:
                # Same ticker/other SimFinId could represent a different issuer.
                raise ValueError("SITC_TICKER_COLLISION_DIFFERENT_SIMFIN_ID")
            if ds in bars or not all(
                isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>0
                for v in (raw,adj)
            ):
                raise ValueError("DUPLICATE_OR_INVALID_SOURCE_BAR")
            bars[ds]={"raw_close":raw,"source_adj_close":adj,
                       "factor_raw_div_adj":raw/adj}
    out=[]
    for d in DOCS:
        before_date,after_date=PAIR_DATES[d["event_id"]]
        before,after=bars.get(before_date),bars.get(after_date)
        row={**d,"source_before_date":before_date,"source_after_date":after_date,
             "source_pair_complete":bool(before and after),
             "source_before":before,"source_after":after,
             "official_event_issuer_only":True,
             "independent_adjusted_price_certified":False,
             "historical_full_window_SimFinId_to_CIK_certified":False,
             "delisting_terminal_value_proven":False,
             "lookahead_free_backtest_allowed":False}
        if before and after:
            row["raw_close_ratio"]=round(after["raw_close"]/before["raw_close"],9)
            row["adjusted_close_ratio"]=round(
                 after["source_adj_close"]/before["source_adj_close"],9)
            row["source_factor_after_over_before"]=round(
                 after["factor_raw_div_adj"]/before["factor_raw_div_adj"],9)
            row["source_factor_change_pct"]=round(
                 100*(row["source_factor_after_over_before"]-1),6)
        else:
            row["source_pair_incomplete_reason"]="MISSING_SOURCE_TRADING_SESSION"
        if d["event_type"]=="REVERSE_SPLIT":
            row["source_raw_price_ratio_minus_4"]=(
                round(row["raw_close_ratio"]-4,9) if before and after else None)
            row["note"]="4x raw-price split expectation is conditional on zero market movement; NOT an acceptance tolerance or independently verified vendor adjustment."
        else:
            row["note"]="Spin-off total shareholder return REQUIRES CURB distributed shares and pricing, payable/when-issued trading conditions, and cash/dividend effects; pair ratio is not enough."
        out.append(row)
    return {
        "schema":SCHEMA,
        "status":"TWO_SEC_OFFICIAL_SITC_ACTION_EVENTS_DOCUMENTED_SOURCE_PRICES_NOT_CERTIFIED",
        "research_staging_version":manifest["staging_version"],
        "referenced_private_source_SHA256":manifest["source_price_sha256"],
        "issuer_documented_actions":2,
        "source_pair_diagnostics_computed":sum(x["source_pair_complete"] for x in out),
        "official_historic_event_issuer_CIK":"0000894315",
        "official_historic_class":"NYSE common shares SITC",
        "historical_SimFinId_CIK_full_window_verified":0,
        "corporate_action_vendor_adjusted_price_certified":0,
        "canonical_eligible_securities":0,
        "canonical_security_dates":0,
        "WF9_executed":False,
        "Learning_V3_trained":False,
        "production_DB_modified":False,
        "original_vendor_sources_modified":False,
        "network_requests":0,
        "actions":out,
    }


def main():
    root=Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))/"S153ResearchTerminal/runtime"
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--out",type=Path,
                   default=root/"phase25s/sitc_official_reverse_split_spinoff_price_diagnostics.json")
    a=p.parse_args()
    try:
        if a.out.is_symlink() or a.out.resolve()==a.manifest.resolve():
            raise ValueError("OVERLAPPING_SOURCE_OUTPUT")
        report=reconcile(a.manifest)
        a.out.parent.mkdir(parents=True,exist_ok=True)
        tmp=a.out.with_name(a.out.name+".tmp")
        if tmp.is_symlink():
            raise ValueError("OUTPUT_TEMP_IS_SYMLINK")
        tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        tmp.replace(a.out)
    except (OSError,ValueError,TypeError,KeyError,sqlite3.Error):
        print("PHASE25S_BLOCKED: EVIDENCE_OR_STAGE_PRICE_INVALID")
        return 2
    print(json.dumps({
        "status":report["status"],"official_corporate_events":2,
        "source_pair_diagnostics":report["source_pair_diagnostics_computed"],
        "independent_adjusted_price_certifications":0,
        "canonical_approved":0,
        "WF9_or_V3_executed":False,
        "report":str(a.out),
    },ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
