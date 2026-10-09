"""Phase24l: cross-check three INOD 10-Q administrative filing dates.

Pinned primary-source SEC archive filing-index facts were independently checked
by a researcher on 2026-10-09; this offline command reconciles those published
facts against the existing local SEC submissions JSON and Phase24k audit.
It DOES NOT fetch SEC pages at runtime, confirm public dissemination times,
modify source data, or certify point-in-time investing eligibility.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from scripts.phase24i_inod_financial_accession_year_gaps import _source_accessions
from scripts.phase24k_inod_target_sec_availability_audit import SCHEMA as SCHEMA_K
from scripts.phase14_sec_acceptance_stage import exact_utc

SCHEMA = "MERIDYEN_PHASE24L_INOD_SEC_PRIMARY_FILING_DATE_REVIEW_V1"
SOURCE_DATE_REVIEWED = "2026-10-09"

# Source: actual SEC EDGAR issuer filing-index pages. The URL references allow
# independent manual re-check; URLs are never requested by this offline tool.
PRIMARY_SEC_INDEX_EVIDENCE = (
    {
        "accession": "0001410578-24-000611",
        "CIK": "0000903651",
        "form": "10-Q",
        "accepted_utc": "2024-05-07T21:48:33+00:00",
        "accepted_et": "2024-05-07T17:48:33-04:00",
        "official_filing_date": "2024-05-08",
        "period_of_report": "2024-03-31",
        "SEC_index_url": "https://www.sec.gov/Archives/edgar/data/903651/0001410578-24-000611-index.htm",
    },
    {
        "accession": "0001410578-24-001246",
        "CIK": "0000903651",
        "form": "10-Q",
        "accepted_utc": "2024-08-08T22:00:33+00:00",
        "accepted_et": "2024-08-08T18:00:33-04:00",
        "official_filing_date": "2024-08-09",
        "period_of_report": "2024-06-30",
        "SEC_index_url": "https://www.sec.gov/Archives/edgar/data/903651/0001410578-24-001246-index.htm",
    },
    {
        "accession": "0001410578-25-001113",
        "CIK": "0000903651",
        "form": "10-Q",
        "accepted_utc": "2025-05-08T21:49:06+00:00",
        "accepted_et": "2025-05-08T17:49:06-04:00",
        "official_filing_date": "2025-05-09",
        "period_of_report": "2025-03-31",
        "SEC_index_url": "https://www.sec.gov/Archives/edgar/data/903651/000141057825001113/0001410578-25-001113-index.htm",
    },
)

SEC_OFFICIAL_FILING_TIMING_RULE_URL = (
    "https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data"
)


def _next_weekday(d: date) -> date:
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def audit(phase24k: Path, sources: Path):
    if (phase24k.is_symlink() or not phase24k.is_file()
        or sources.is_symlink() or not sources.is_dir()):
        raise ValueError("LOCAL_PRIOR_PHASE24K_OR_SEC_SOURCE_MISSING")
    k=json.loads(phase24k.read_text(encoding="utf-8"))
    if (k.get("schema")!=SCHEMA_K
        or k.get("status")!="INOD_2024_2025_FINANCIAL_PIT_TIMESTAMP_CANDIDATE_AUDIT_ONLY"
        or k.get("eligible_for_canonical_PIT_promotion") is not False
        or k.get("database_modified") is not False
        or k.get("counts",{}).get("quarantined_source_chronology_accessions")!=3
        or k.get("counts",{}).get("accessions")!=len(k.get("accessions",[]))):
        raise ValueError("UNTRUSTED_OR_INCOMPLETE_PHASE24K_REPORT")
    quarantined=[
        e for e in k["accessions"]
        if e.get("source_chronology")!="NORMAL_CONSIDERED"
    ]
    source_good, source_counts, anomalies, source_forms = _source_accessions(sources)
    # Protect against accidental cross-check against wrong, edited SEC root
    # or the earlier 20 count no longer being true.
    if (len(anomalies)!=20
        or len(quarantined)!=3
        or set(x["accession"] for x in quarantined)!=
           set(x["accession"] for x in PRIMARY_SEC_INDEX_EVIDENCE)
        or len({a["accession"] for a in anomalies})!=20
        or source_counts["accepted_UTC_before_filing_date"]!=20):
        raise ValueError("SEC_SOURCE_ANOMALY_LIST_DIFFERENT_FROM_PHASE24J")
    anomaly_by_id={e["accession"]:e for e in anomalies}
    local_by_id={e["accession"]:e for e in quarantined}
    tz=ZoneInfo("America/New_York")
    records=[]
    for primary in PRIMARY_SEC_INDEX_EVIDENCE:
        accession=primary["accession"]
        sec=anomaly_by_id[accession]
        local=local_by_id[accession]
        accepted=exact_utc(sec["acceptance_utc"])
        expected=exact_utc(primary["accepted_utc"])
        if accepted is None or expected is None or accepted!=expected:
            raise ValueError("SEC_PRIMARY_SOURCE_ACCEPTANCE_MISMATCH")
        ny=accepted.astimezone(tz)
        if (ny.isoformat()!=primary["accepted_et"]
            or ny.time().replace(tzinfo=None)<time(17,30)
            or _next_weekday(ny.date()).isoformat()!=primary["official_filing_date"]
            or date.fromisoformat(sec["filing_date"])!=
               date.fromisoformat(primary["official_filing_date"])
            or sec["form"]!=primary["form"]
            or local.get("accepted_utc")!=sec["acceptance_utc"]
            or local.get("filing_date")!=sec["filing_date"]
            or local.get("form")!=primary["form"]
            or local.get("PIT_certified") is not False
            or local.get("matched_SEC_fact_rows_bounded",0)<=0
            or local.get("issues")!=[
                "AFTER_HOURS_SEC_FILING_DATE_RULE_NOT_INDEPENDENTLY_VERIFIED"
            ]):
            raise ValueError("SEC_OFFICIAL_INDEX_FIELDS_OR_LOCAL_FACTS_MISMATCH")
        records.append({
            "accession":accession,"form":primary["form"],
            "SEC_filer_CIK":primary["CIK"],
            "period_of_report":primary["period_of_report"],
            "SEC_accepted_UTC_unchanged":primary["accepted_utc"],
            "SEC_accepted_ET_unchanged":ny.isoformat(),
            "SEC_official_filing_date_unchanged":
                primary["official_filing_date"],
            "source_index_URL":primary["SEC_index_url"],
            "official_filing_date_and_acceptance_match_pinned_index":True,
            "administrative_date_difference_explained":True,
            "public_dissemination_time_verified":False,
            "SEC_fact_accession_match_existing":True,
            "PIT_certified":False,
        })
    return {
        "schema":SCHEMA,
        "status":"THREE_INOD_SEC_10Q_FILING_DATES_PRIMARY_SOURCE_CROSSCHECKED_NO_PIT",
        "primary_SEC_index_fields_checked_on":SOURCE_DATE_REVIEWED,
        "primary_SEC_filing_rule_URL":SEC_OFFICIAL_FILING_TIMING_RULE_URL,
        "offline_crosschecked_10Q_count":len(records),
        "accepted_after_1730_ET_next_business_day_consistent_count":
            len(records),
        "unexplained_date_difference_in_these_three":0,
        "full_SEC_20_anomaly_audit_completed":False,
        "historical_SimFinId_CIK_certifications":0,
        "public_dissemination_timestamps_verified":0,
        "SEC_public_dissemination_lookahead_gate":"BLOCKED_UNKNOWN",
        "canonical_PIT_certified":False,
        "database_modified":False,
        "network_requests":0,
        "SEC_timestamp_mutations":0,
        "model_training_performed":False,
        "records":records,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    root=Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))/(
        "S153ResearchTerminal/runtime")
    p.add_argument("--phase24k",type=Path,
                   default=root/"phase24k/inod_sec_financial_timestamp_evidence.json")
    p.add_argument("--sources",type=Path,default=root/"sec_submissions")
    p.add_argument("--out",type=Path,default=root/"phase24l/inod_sec_primary_filing_date_review.json")
    args=p.parse_args()
    try:
        dest=args.out.resolve()
        if dest==args.phase24k.resolve() or args.sources.resolve() in dest.parents:
            raise ValueError("REPORT_DESTINATION_OVERWRITES_SOURCE")
        result=audit(args.phase24k,args.sources)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        stage=args.out.with_suffix(".json.tmp")
        stage.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        stage.replace(args.out)
    except (OSError,ValueError,TypeError,KeyError,ZoneInfoNotFoundError):
        print("PHASE24L_BLOCKED: SEC_INDEX_FIELDS_OR_EXISTING_PHASE24K_DONT_MATCH")
        return 2
    print(json.dumps({
        "status":result["status"],
        "official_SEC_10Q_filing_date_matches":
            result["offline_crosschecked_10Q_count"],
        "unexplained_date_difference_in_these_three":
            result["unexplained_date_difference_in_these_three"],
        "public_dissemination_timestamps_verified":
            result["public_dissemination_timestamps_verified"],
        "PIT_certified":False,"database_modified":False,
        "full_report":str(args.out),
    },ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
