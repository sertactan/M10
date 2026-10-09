"""Phase24h — read-only classification of INOD SEC accession evidence gaps.

Uses the two existing Phase14 archival reconciliation reports, the same saved
SEC root/archive documents, and the verified offline SQLite BACKUP. Does not
download, import SEC, update any database, certify PIT, or train models.

Classifies missing financial facts by SEC filing form; an 8-K or ownership filing
may legitimately have no US-GAAP companyfacts rows. Invalid acceptance/filing
chronology is quarantined, not repaired or reinterpreted.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import date
import json
import os
from pathlib import Path
import re
import sqlite3

from scripts.phase14_sec_submissions_archive_reconcile import (
    ROOT_FILE, SCHEMA as P14_SCHEMA, _source_rows, _issuer_index
)
from scripts.phase14_sec_acceptance_stage import ACCESSION, exact_utc

SCHEMA = "MERIDYEN_PHASE24H_INOD_SEC_FORM_GAP_REVIEW_V1"


def _report(path: Path, offset: int) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("PRIOR_RECONCILIATION_REPORT_MISSING")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if (doc.get("schema") != P14_SCHEMA
        or doc.get("accession_offset") != offset
        or doc.get("historical_pit_certified") is not False
        or doc.get("database_modified") is not False
        or not doc.get("archival_coverage_complete")
        or doc.get("counts", {}).get("valid_accessions_indexed", 0) <= 0):
        raise ValueError("PRIOR_RECONCILIATION_NOT_VALIDATED")
    return doc


def analyze(db: Path, sec_dir: Path, first: Path, tail: Path,
            *, max_accessions: int = 3000) -> dict:
    a = _report(first, 0)
    b = _report(tail, 1000)
    if db.is_symlink() or not db.is_file() or sec_dir.is_symlink() or not sec_dir.is_dir():
        raise ValueError("BACKUP_OR_ORIGINAL_SEC_SOURCE_MISSING")
    if (Path(a["database"]).resolve() != db.resolve()
        or Path(b["database"]).resolve() != db.resolve()
        or Path(a["submissions_dir"]).resolve() != sec_dir.resolve()
        or Path(b["submissions_dir"]).resolve() != sec_dir.resolve()
        or a["counts"]["valid_accessions_indexed"] !=
           b["counts"]["valid_accessions_indexed"]
        or a.get("next_accession_offset") != 1000
        or b.get("next_accession_offset") is not None
        or b.get("next_issuer_offset") is not None):
        raise ValueError("PRIOR_RECONCILIATION_PAGINATION_INCONSISTENT")
    indexed = a["counts"]["valid_accessions_indexed"]
    if not (1000 < indexed <= max_accessions):
        raise ValueError("PRIOR_RECONCILIATION_CANNOT_BOUND_COMPLETE_WINDOW")

    roots = sorted(p for p in sec_dir.iterdir() if ROOT_FILE.fullmatch(p.name))
    if len(roots) != 1:
        raise ValueError("EXPECTED_EXACTLY_ONE_INOD_SEC_ROOT_FILE")
    cik = ROOT_FILE.fullmatch(roots[0].name).group(1)
    if cik != "0000903651":
        raise ValueError("INOD_PILOT_CIK_NOT_MATCHED")

    source_counts = Counter()
    chronology_by_form = Counter()
    bad_chronology_samples = []
    seen = {}
    barred = set()
    for source_name, sha, entries in _source_rows(
        sec_dir, roots[0], cik, source_counts
    ):
        for e in entries:
            acc = e["accession"]
            if not ACCESSION.fullmatch(acc):
                source_counts["invalid_accession_format"] += 1
                continue
            accepted = exact_utc(e["accepted"])
            if accepted is None:
                source_counts["acceptance_missing_offset"] += 1
                barred.add(acc)
                seen.pop(acc, None)
                continue
            try:
                filed = date.fromisoformat(str(e["filing_date"]))
            except ValueError:
                source_counts["invalid_filing_date"] += 1
                barred.add(acc)
                seen.pop(acc, None)
                continue
            if accepted.date() < filed:
                source_counts["acceptance_before_filing_date"] += 1
                chronology_by_form[e["form"]] += 1
                if len(bad_chronology_samples) < 15:
                    bad_chronology_samples.append({
                        "accession":acc,
                        "form":e["form"],
                        "filing_date":str(filed),
                        "sec_accepted_utc":accepted.isoformat(),
                        "source_filename":source_name,
                    })
                barred.add(acc)
                seen.pop(acc,None)
                continue
            if acc in barred:
                continue
            candidate = {
                "accession":acc, "form":e["form"],
                "filing_date":str(filed),
                "acceptance":accepted.isoformat(),
            }
            if acc in seen:
                p = seen[acc]
                if any(p[k] != candidate[k] for k in
                       ("form","filing_date","acceptance")):
                    source_counts["conflicting_duplicate_accessions"] += 1
                    seen.pop(acc,None)
                    barred.add(acc)
            else:
                seen[acc] = candidate

    if (len(seen) != indexed
        or source_counts["acceptance_before_filing_date"] !=
           a["counts"].get("acceptance_before_filing_date",0)
        or source_counts["acceptance_before_filing_date"] !=
           b["counts"].get("acceptance_before_filing_date",0)):
        raise ValueError("ORIGINAL_SUBMISSIONS_RECONCILIATION_MISMATCH")

    existing_evidence = {
        str(e["accession_number"]):e
        for report in (a,b) for e in report.get("evidence_candidates",[])
    }
    if len(existing_evidence) != sum(
        r["counts"].get("accessions_with_reviewable_evidence",0) for r in (a,b)
    ):
        raise ValueError("DUPLICATE_OR_INCOMPLETE_PRIOR_EVIDENCE")

    by_form = Counter()
    unmatched_by_form = Counter()
    matched_by_form = Counter()
    abnormal = Counter()
    unmatched_examples = []
    with closing(sqlite3.connect(db.resolve().as_uri()+"?mode=ro",
                                 uri=True,timeout=10)) as con:
        con.execute("PRAGMA query_only=ON")
        con.execute("PRAGMA busy_timeout=10000")
        mapped = _issuer_index(con)
        if len(mapped.get(cik,())) != 1:
            raise ValueError("SEC_CIK_CURRENT_SECURITY_MASTER_AMBIGUOUS")
        security_id = next(iter(mapped[cik]))
        for acc, ent in sorted(seen.items()):
            form = ent["form"]
            by_form[form] += 1
            if acc in existing_evidence:
                matched_by_form[form] += 1
                continue
            count = con.execute(
                """SELECT COUNT(*) FROM
                    (SELECT 1 FROM fundamental_facts_source
                     WHERE source='SEC_EDGAR' AND security_id=?
                       AND accession_number=? LIMIT 1)""",
                (security_id, acc)
            ).fetchone()[0]
            if count == 0:
                unmatched_by_form[form] += 1
                if len(unmatched_examples)<15:
                    unmatched_examples.append({
                        "accession":acc,"form":form,
                        "filing_date":ent["filing_date"],
                    })
            else:
                abnormal[form] += 1
    first_missing = a["counts"].get("accessions_without_matching_facts",0)
    tail_missing = b["counts"].get("accessions_without_matching_facts",0)
    if (sum(unmatched_by_form.values()) != first_missing+tail_missing
        or sum(matched_by_form.values()) != len(existing_evidence)
        or sum(abnormal.values()) != (
            indexed - len(existing_evidence) - first_missing-tail_missing)):
        raise ValueError("SEC_FACT_EVIDENCE_FORM_RECONCILIATION_MISMATCH")

    return {
        "schema":SCHEMA,
        "status":"INOD_SEC_FORM_GAPS_CLASSIFIED_RESEARCH_ONLY_NOT_PIT",
        "pilot_CIK_not_historically_certified":cik,
        "valid_accessions_total":indexed,
        "first_1000_reviewable_accessions":a["counts"].get(
            "accessions_with_reviewable_evidence",0),
        "tail_reviewable_accessions":b["counts"].get(
            "accessions_with_reviewable_evidence",0),
        "reviewable_accessions_total":len(existing_evidence),
        "first_1000_without_matching_facts":first_missing,
        "tail_without_matching_facts":tail_missing,
        "total_without_matching_facts":sum(unmatched_by_form.values()),
        "forms_all_valid_accessions":dict(sorted(by_form.items())),
        "forms_with_reviewable_financial_facts":dict(sorted(matched_by_form.items())),
        "forms_without_financial_facts":dict(sorted(unmatched_by_form.items())),
        "forms_with_facts_but_not_reviewable":dict(sorted(abnormal.items())),
        "source_before_filing_date_count_not_double_counted":
            source_counts["acceptance_before_filing_date"],
        "source_before_filing_date_forms":dict(sorted(chronology_by_form.items())),
        "date_conflict_examples_for_human_review":bad_chronology_samples,
        "no_fact_examples_for_human_review":unmatched_examples,
        "absence_of_facts_proves_missing_data":False,
        "date_chronology_conflicts_automatically_fixed":False,
        "issuer_share_class_crosswalk_certified":False,
        "SEC_origin_independently_certified":False,
        "historical_PIT_certified":False,
        "database_modified":False,
        "new_downloads":0,
        "model_training_performed":False,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    root=Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / (
        "S153ResearchTerminal/runtime"
    )
    p.add_argument("--db",type=Path,default=root/"phase24g/operational_inod_offline_backup.db")
    p.add_argument("--submissions-dir",type=Path,default=root/"sec_submissions")
    p.add_argument("--first",type=Path,default=root/"phase24g/inod_sec_reconciliation.json")
    p.add_argument("--tail",type=Path,default=root/"phase24g/inod_sec_reconciliation_tail.json")
    p.add_argument("--out",type=Path,default=root/"phase24h/inod_sec_form_gap_review.json")
    args=p.parse_args()
    try:
        result=analyze(args.db,args.submissions_dir,args.first,args.tail)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        draft=args.out.with_suffix(".json.tmp")
        draft.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",
                         encoding="utf-8")
        draft.replace(args.out)
    except (OSError,ValueError,TypeError,KeyError,sqlite3.Error):
        print("PHASE24H_BLOCKED: SEC_SOURCE_REPORT_OR_BACKUP_MISMATCH")
        return 2
    print(json.dumps({
        "status":result["status"],
        "valid_accessions":result["valid_accessions_total"],
        "reviewable":result["reviewable_accessions_total"],
        "without_facts":result["total_without_matching_facts"],
        "without_facts_by_form":result["forms_without_financial_facts"],
        "nonreviewable_with_facts_by_form":
            result["forms_with_facts_but_not_reviewable"],
        "acceptance_before_filing_date_distinct_source_row_occurrences":
            result["source_before_filing_date_count_not_double_counted"],
        "chronology_conflict_by_form":result["source_before_filing_date_forms"],
        "report":str(args.out),
        "database_modified":False,
    },indent=2,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
