"""Phase24j — INOD SEC acceptance time vs filing date, New York wall-time audit.

Read-only classification. An SEC filing_date later than acceptance UTC date can
occur for late submissions. Such calendar differences are NOT proof that a
timestamp needs repairing; SEC per-form/holiday/filing rule validation is still
required. No canonical PIT or historical CIK approval is performed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import date, datetime, timedelta, time
import json
import os
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from scripts.phase24i_inod_financial_accession_year_gaps import (
    _source_accessions, _prior, FINANCIAL_FORMS, START, END, SCHEMA as PHASE24I_SCHEMA
)
from scripts.phase14_sec_submissions_archive_reconcile import _issuer_index

SCHEMA = "MERIDYEN_PHASE24J_INOD_SEC_ACCEPTANCE_ET_CLASSIFICATION_V1"
TZ = "America/New_York"
CUTOFF = time(17, 30)


def _weekday_after(day: date) -> date:
    following = day + timedelta(days=1)
    while following.weekday() >= 5:
        following += timedelta(days=1)
    return following


def audit(db: Path, sources: Path, previous: Path):
    if (db.is_symlink() or not db.is_file() or
        sources.is_symlink() or not sources.is_dir() or
        previous.is_symlink() or not previous.is_file()):
        raise ValueError("OFFLINE_BACKUP_OR_PRIOR_REPORT_UNAVAILABLE")
    original = json.loads(previous.read_text(encoding="utf-8"))
    if (original.get("schema") != PHASE24I_SCHEMA or
        original.get("status") != "INOD_FINANCIAL_ACCESSION_DATE_GAPS_CLASSIFIED_REVIEW_ONLY" or
        original.get("PIT_approved") is not False or
        original.get("database_modified") is not False or
        original.get("window") != {"start": START.isoformat(), "end": END.isoformat()}):
        raise ValueError("PHASE24I_REPORT_NOT_VERIFIED")
    # Check its upstream phase24h against same originals. Never rely on an
    # unverifiable tally in a stand-alone JSON.
    phase24h = previous.parent.parent / "phase24h" / "inod_sec_form_gap_review.json"
    upstream = _prior(phase24h)
    _valid, counts, anomalies, by_form = _source_accessions(sources)
    if (counts["accepted_UTC_before_filing_date"] !=
        original["accepted_UTC_before_filing_date_source_count"] or
        counts["accepted_UTC_before_filing_date"] !=
        upstream["source_before_filing_date_count_not_double_counted"] or
        dict(sorted(by_form.items())) != original["date_conflict_form_counts"] or
        len(anomalies) != counts["accepted_UTC_before_filing_date"]):
        raise ValueError("SEC_SOURCE_ANOMALIES_CHANGED_OR_TRUNCATED")
    eastern = ZoneInfo(TZ)
    records = []
    statuses = Counter()
    form_statuses = Counter()
    target_financial = Counter()
    with closing(sqlite3.connect(db.resolve().as_uri()+"?mode=ro",
                                 uri=True,timeout=15)) as con:
        con.execute("PRAGMA query_only=ON")
        ind={r[1] for r in con.execute("PRAGMA index_list(fundamental_facts_source)")}
        if "idx_fundamental_accession" not in ind:
            raise ValueError("INDEX_REQUIRED_TO_AVOID_LARGE_FACT_SCANS")
        mapped=_issuer_index(con)
        if len(mapped.get("0000903651",())) != 1:
            raise ValueError("SEC_CIK_CURRENT_MAPPING_AMBIGUOUS")
        sid=next(iter(mapped["0000903651"]))
        for e in anomalies:
            filed = date.fromisoformat(e["filing_date"])
            utc=datetime.fromisoformat(e["acceptance_utc"])
            if utc.tzinfo is None or utc.utcoffset() is None:
                raise ValueError("SEC_ACCEPTANCE_NOT_TIMEZONE_AWARE")
            ny=utc.astimezone(eastern)
            cutoff_passed=ny.timetz().replace(tzinfo=None) >= CUTOFF
            next_weekday = _weekday_after(ny.date())
            # A plausible SEC administrative date progression, NOT legal
            # proof of the applicable 17:30 ET rule for every SEC form.
            if cutoff_passed and filed == next_weekday:
                state = "AFTER_1730_ET_NEXT_WEEKDAY_CANDIDATE_REVIEW"
            elif cutoff_passed and filed > ny.date():
                state = "AFTER_1730_ET_HOLIDAY_OR_FORM_RULE_REVIEW"
            else:
                state = "NOT_EXPLAINED_BY_SIMPLE_AFTER_HOURS_RULE_REVIEW"
            fact = con.execute(
                """SELECT 1 FROM fundamental_facts_source
                   WHERE security_id=? AND accession_number=?
                     AND source='SEC_EDGAR' LIMIT 1""",
                (sid,e["accession"])
            ).fetchone() is not None
            target = START <= filed <= END
            if target and e["form"] in FINANCIAL_FORMS:
                target_financial[("with_facts" if fact else "without_facts")]+=1
            statuses[state]+=1
            form_statuses[(e["form"],state)]+=1
            records.append({
                "accession":e["accession"],
                "form":e["form"],
                "SEC_filing_date":e["filing_date"],
                "SEC_accepted_utc_original":e["acceptance_utc"],
                "SEC_accepted_New_York":ny.isoformat(),
                "accepted_after_1730_ET":cutoff_passed,
                "next_weekday_after_NY_accepted":next_weekday.isoformat(),
                "review_class":state,
                "in_2024_2025_target_by_filing_date":target,
                "existing_backup_SEC_fact_accession_match":fact,
                "automatically_repaired":False,
            })
    return {
        "schema":SCHEMA,
        "status":"SEC_ACCEPTANCE_ET_CANDIDATES_REVIEW_ONLY_NO_DATE_REPAIR",
        "CIK_candidate_not_historically_certified":"0000903651",
        "source_anomalies":len(records),
        "by_class":dict(sorted(statuses.items())),
        "by_form_and_class":[
            {"form":form,"class":c,"count":n}
            for (form,c),n in sorted(form_statuses.items())
        ],
        "target_2024_2025_financial_anomalies":sum(target_financial.values()),
        "target_2024_2025_financial_anomalies_with_existing_facts":
            target_financial["with_facts"],
        "target_2024_2025_financial_anomalies_without_existing_facts":
            target_financial["without_facts"],
        "source_records":records,
        "after_hours_is_not_SEC_rule_certification":True,
        "US_market_holidays_not_inferred":True,
        "timestamp_changed":False,
        "historical_SimFinId_CIK_certified":False,
        "PIT_certified":False,
        "DB_modified":False,
        "network_requests":0,
        "models_modified":False,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    root=Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / (
        "S153ResearchTerminal/runtime")
    p.add_argument("--db",type=Path,default=root/"phase24g/operational_inod_offline_backup.db")
    p.add_argument("--sources",type=Path,default=root/"sec_submissions")
    p.add_argument("--phase24i",type=Path,default=root/"phase24i/inod_financial_accession_gaps.json")
    p.add_argument("--out",type=Path,default=root/"phase24j/inod_sec_acceptance_ET_review.json")
    a=p.parse_args()
    try:
        dest=a.out.expanduser().resolve()
        if dest in {a.db.resolve(),a.phase24i.resolve()} or a.sources.resolve() in dest.parents:
            raise ValueError("REPORT_MUST_NOT_OVERWRITE_INPUT")
        result=audit(a.db,a.sources,a.phase24i)
        a.out.parent.mkdir(parents=True,exist_ok=True)
        tmp=a.out.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",
                       encoding="utf-8")
        tmp.replace(a.out)
    except (OSError,ValueError,TypeError,KeyError,sqlite3.Error,ZoneInfoNotFoundError):
        print("PHASE24J_BLOCKED: SEC_EVIDENCE_BACKUP_OR_NY_TIMEZONE_UNAVAILABLE")
        return 2
    print(json.dumps({
        "status":result["status"],
        "source_anomalies":result["source_anomalies"],
        "by_class":result["by_class"],
        "target_financial_anomalies":
            result["target_2024_2025_financial_anomalies"],
        "target_financial_with_existing_SEC_facts":
            result["target_2024_2025_financial_anomalies_with_existing_facts"],
        "target_financial_without_existing_SEC_facts":
            result["target_2024_2025_financial_anomalies_without_existing_facts"],
        "report":str(a.out),
        "PIT_certified":False,"DB_modified":False,"network_requests":0,
    },indent=2,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
