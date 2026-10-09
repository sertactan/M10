"""Phase24k — INOD 2024-2025 financial accession PIT timestamp evidence audit.

Read only: SEC submissions root/archive JSON, Phase24i/j local review reports
and the EXISTING SQLite backup. Never writes fact/CIK/price/PIT canonical
tables. Source submission timestamp vs fact.available_at is an evidence check,
not a historical SimFinId↔CIK share-class identity certification.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import date
import json
import os
from pathlib import Path
import sqlite3

from scripts.phase14_sec_acceptance_stage import exact_utc
from scripts.phase14_sec_submissions_archive_reconcile import _issuer_index
from scripts.phase24i_inod_financial_accession_year_gaps import (
    _source_accessions, FINANCIAL_FORMS, START, END, SCHEMA as SCHEMA_I,
)
from scripts.phase24j_inod_sec_acceptance_et_review import SCHEMA as SCHEMA_J

SCHEMA = "MERIDYEN_PHASE24K_INOD_TARGET_SEC_PIT_AVAILABILITY_EVIDENCE_V1"
MAX_FINANCIAL_ACCESSIONS = 200
MAX_FACT_ROWS_PER_ACCESSION = 2500


def _load(path: Path, expected: str, status: str):
    if path.is_symlink() or not path.is_file():
        raise ValueError("PRIOR_LOCAL_REPORT_MISSING")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if (doc.get("schema") != expected
        or doc.get("status") != status):
        raise ValueError("PRIOR_LOCAL_REPORT_SCHEMA_OR_STATUS_CHANGED")
    return doc


def audit(db: Path, sources: Path, phase24i: Path, phase24j: Path):
    if (db.is_symlink() or not db.is_file()
        or sources.is_symlink() or not sources.is_dir()):
        raise ValueError("OFFLINE_BACKUP_OR_SEC_SUBMISSIONS_MISSING")
    report_i=_load(
        phase24i,SCHEMA_I,
        "INOD_FINANCIAL_ACCESSION_DATE_GAPS_CLASSIFIED_REVIEW_ONLY")
    report_j=_load(
        phase24j,SCHEMA_J,
        "SEC_ACCEPTANCE_ET_CANDIDATES_REVIEW_ONLY_NO_DATE_REPAIR")
    if (report_i.get("PIT_approved") is not False or
        report_i.get("database_modified") is not False or
        report_j.get("PIT_certified") is not False or
        report_j.get("DB_modified") is not False or
        report_j.get("timestamp_changed") is not False or
        report_i.get("window") != {
            "start":START.isoformat(),"end":END.isoformat()}):
        raise ValueError("PRIOR_PIT_OR_DB_SAFETY_CLAIM_FAILED")
    good,counts,anomalies,_ = _source_accessions(sources)
    if (len(good) != report_i.get("total_valid_SEC_accessions")
        or len(anomalies) != report_j.get("source_anomalies")
        or counts["accepted_UTC_before_filing_date"] !=
            report_i.get("accepted_UTC_before_filing_date_source_count")
        or report_j.get("target_2024_2025_financial_anomalies") !=
            sum(START<=date.fromisoformat(e["filing_date"])<=END
                and e["form"] in FINANCIAL_FORMS for e in anomalies)):
        raise ValueError("SEC_SOURCE_REPORT_COUNTS_INCONSISTENT")
    selections=[]
    for e in good.values():
        if (e["form"] in FINANCIAL_FORMS and
            START <= date.fromisoformat(e["filed"]) <= END):
            selections.append({
                "accession":e["accession"],"form":e["form"],
                "filing_date":e["filed"],
                "accepted_utc":e["accepted"],
                "source_chronology":"NORMAL_CONSIDERED",
            })
    for e in anomalies:
        if (e["form"] in FINANCIAL_FORMS and
            START <= date.fromisoformat(e["filing_date"]) <= END):
            selections.append({
                "accession":e["accession"],"form":e["form"],
                "filing_date":e["filing_date"],
                "accepted_utc":e["acceptance_utc"],
                "source_chronology":"AFTER_HOURS_OR_FORM_RULE_REQUIRES_REVIEW",
            })
    if not 0 < len(selections) <= MAX_FINANCIAL_ACCESSIONS:
        raise ValueError("TARGET_FINANCIAL_ACCESSION_COUNT_UNSAFE")
    if (len(set(e["accession"] for e in selections)) != len(selections)
        or Counter(e["form"] for e in selections if
                   e["source_chronology"]=="NORMAL_CONSIDERED") !=
           Counter(report_i["filings_in_target_window_by_form"])):
        raise ValueError("SEC_TARGET_ACCESSION_SET_INCONSISTENT")
    records=[]
    reasons=Counter()
    class_counts=Counter()
    totals=Counter()
    with closing(sqlite3.connect(db.resolve().as_uri()+"?mode=ro",
                                 uri=True,timeout=15)) as con:
        con.execute("PRAGMA query_only=ON")
        if "idx_fundamental_accession" not in {
            row[1] for row in con.execute(
                "PRAGMA index_list(fundamental_facts_source)") }:
            raise ValueError("NO_USABLE_SEC_FACT_ACCESSION_INDEX")
        mapping=_issuer_index(con)
        if len(mapping.get("0000903651",())) != 1:
            raise ValueError("CIK_CURRENT_MASTER_AMBIGUOUS")
        sid=next(iter(mapping["0000903651"]))
        for ent in sorted(selections,key=lambda e:(e["filing_date"],e["accession"])):
            rows=con.execute(
                """SELECT available_at,accepted_at,filing_date,
                          period_end,form_type
                   FROM fundamental_facts_source
                   WHERE security_id=? AND source='SEC_EDGAR'
                         AND accession_number=? LIMIT ?""",
                (sid,ent["accession"],MAX_FACT_ROWS_PER_ACCESSION+1)
            ).fetchall()
            issue=set()
            if not rows:
                issue.add("NO_MATCHED_SEC_FINANCIAL_FACT_ROWS")
            if len(rows)>MAX_FACT_ROWS_PER_ACCESSION:
                issue.add("FACT_ROWS_EXCEED_SAFE_PER_ACCESSION_CAP")
                rows=rows[:MAX_FACT_ROWS_PER_ACCESSION]
            src_accepted=exact_utc(ent["accepted_utc"])
            if src_accepted is None:
                raise ValueError("SEC_SUBMISSIONS_ACCEPTANCE_NOT_OFFSET_AWARE")
            for available,accepted,filing_date,period_end,form in rows:
                av=exact_utc(available)
                if av is None:
                    issue.add("FACT_AVAILABLE_AT_INVALID_OR_MISSING")
                elif av < src_accepted:
                    issue.add("LOOKAHEAD_RISK_AVAILABLE_BEFORE_SEC_ACCEPTANCE")
                old=exact_utc(accepted)
                if accepted not in (None,"") and old is None:
                    issue.add("STORED_FACT_ACCEPTANCE_INVALID")
                if old is not None and old != src_accepted:
                    issue.add("STORED_FACT_ACCEPTANCE_DIFFERS_FROM_SEC_SOURCE")
                if str(filing_date)!=ent["filing_date"]:
                    issue.add("FACT_FILING_DATE_NOT_EQUAL_ORIGINAL_SEC_FILING_DATE")
                if form and str(form)!=ent["form"]:
                    issue.add("FACT_FORM_DIFFERS_FROM_ORIGINAL_SEC_FORM")
                if period_end and str(period_end)>ent["filing_date"]:
                    issue.add("FACT_PERIOD_END_AFTER_FILING_DATE")
            if ent["source_chronology"]!="NORMAL_CONSIDERED":
                issue.add("AFTER_HOURS_SEC_FILING_DATE_RULE_NOT_INDEPENDENTLY_VERIFIED")
            if issue:
                cls="EVIDENCE_GAPS_REQUIRE_HUMAN_REVIEW_NOT_PIT"
            else:
                cls="SOURCE_AND_FACT_TIME_FIELDS_CONSISTENT_NOT_PIT"
            class_counts[cls]+=1
            totals["accessions"]+=1
            totals["scanned_fact_rows"]+=len(rows)
            if ent["source_chronology"]!="NORMAL_CONSIDERED":
                totals["quarantined_source_chronology_accessions"]+=1
            for reason in issue:
                reasons[reason]+=1
            records.append({
                **ent,"matched_SEC_fact_rows_bounded":len(rows),
                "class":cls,"issues":sorted(issue),
                "PIT_certified":False,
            })
    if (totals["quarantined_source_chronology_accessions"] !=
        report_j["target_2024_2025_financial_anomalies"] or
        sum(r["matched_SEC_fact_rows_bounded"]>0
            for r in records if
            r["source_chronology"]!="NORMAL_CONSIDERED") !=
        report_j["target_2024_2025_financial_anomalies_with_existing_facts"] or
        sum(r["matched_SEC_fact_rows_bounded"]==0
            for r in records if
            r["source_chronology"]!="NORMAL_CONSIDERED") !=
        report_j["target_2024_2025_financial_anomalies_without_existing_facts"] or
        sum(r["matched_SEC_fact_rows_bounded"]==0
            for r in records if
            r["source_chronology"]=="NORMAL_CONSIDERED") !=
        report_i["financial_filings_no_fact_in_target_window_count"]):
        raise ValueError("SOURCE_FACT_MATCH_COUNTS_CHANGED_FROM_PRIOR_AUDITS")
    return {
        "schema":SCHEMA,
        "status":"INOD_2024_2025_FINANCIAL_PIT_TIMESTAMP_CANDIDATE_AUDIT_ONLY",
        "target_window":{"start":START.isoformat(),"end":END.isoformat()},
        "counts":dict(totals),
        "accessions_by_review_class":dict(sorted(class_counts.items())),
        "accessions_with_issue_by_reason":dict(sorted(reasons.items())),
        "accessions":records,
        "eligible_for_canonical_PIT_promotion":False,
        "original_SEC_provenance_independently_verified":False,
        "historical_SimFinId_CIK_crosswalk_certified":False,
        "date_repairs":0,"database_modified":False,
        "network_requests":0,"model_training_performed":False,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    root=Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))/(
        "S153ResearchTerminal/runtime")
    p.add_argument("--db",type=Path,default=root/"phase24g/operational_inod_offline_backup.db")
    p.add_argument("--sources",type=Path,default=root/"sec_submissions")
    p.add_argument("--phase24i",type=Path,default=root/"phase24i/inod_financial_accession_gaps.json")
    p.add_argument("--phase24j",type=Path,default=root/"phase24j/inod_sec_acceptance_ET_review.json")
    p.add_argument("--out",type=Path,default=root/"phase24k/inod_sec_financial_timestamp_evidence.json")
    args=p.parse_args()
    try:
        dest=args.out.resolve()
        if (dest in {args.db.resolve(),args.phase24i.resolve(),args.phase24j.resolve()}
            or args.sources.resolve() in dest.parents):
            raise ValueError("OUTPUT_OVERLAPS_SOURCE_DATA")
        report=audit(args.db,args.sources,args.phase24i,args.phase24j)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        tmp=args.out.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",
                       encoding="utf-8")
        tmp.replace(args.out)
    except (OSError,ValueError,TypeError,KeyError,sqlite3.Error):
        print("PHASE24K_BLOCKED: SOURCE_CROSSCHECK_OR_OFFLINE_PIT_GATE_FAILED")
        return 2
    print(json.dumps({
        "status":report["status"],"counts":report["counts"],
        "review_class":report["accessions_by_review_class"],
        "reason_counts":report["accessions_with_issue_by_reason"],
        "report":str(args.out),
        "canonical_PIT":False,"database_modified":False,
        "network_requests":0,
    },indent=2,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
