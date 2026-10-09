"""Phase24i: review INOD 10-K/10-Q accession gaps by actual filing date.

Offline, bounded, read-only. Uses Phase24h's recorded research result, original
SEC submissions JSON and the existing SQLite BACKUP. Does NOT mark historical
SimFinId↔SEC CIK canonical or repair SEC acceptance/filing timestamps.
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

from scripts.phase14_sec_submissions_archive_reconcile import (
    ROOT_FILE, _source_rows, _issuer_index,
)
from scripts.phase14_sec_acceptance_stage import ACCESSION, exact_utc

SCHEMA = "MERIDYEN_PHASE24I_INOD_FINANCIAL_ACCESSION_YEAR_GAPS_V1"
PRIOR = "MERIDYEN_PHASE24H_INOD_SEC_FORM_GAP_REVIEW_V1"
FINANCIAL_FORMS = ("10-K", "10-K/A", "10-Q", "10-Q/A")
START = date(2024, 1, 1)
END = date(2025, 9, 30)


def _prior(path: Path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("PHASE24H_PRIVATE_REPORT_MISSING")
    r = json.loads(path.read_text(encoding="utf-8"))
    if (r.get("schema") != PRIOR or
        r.get("status") != "INOD_SEC_FORM_GAPS_CLASSIFIED_RESEARCH_ONLY_NOT_PIT" or
        r.get("historical_PIT_certified") is not False or
        r.get("database_modified") is not False or
        r.get("pilot_CIK_not_historically_certified") != "0000903651"):
        raise ValueError("PHASE24H_SOURCE_NOT_VERIFIED")
    return r


def _source_accessions(folder: Path):
    roots = sorted(p for p in folder.iterdir() if ROOT_FILE.fullmatch(p.name))
    if len(roots) != 1 or roots[0].name != "CIK0000903651.json":
        raise ValueError("EXPECTED_INOD_ONLY_SEC_SUBMISSIONS_PILOT")
    counts = Counter()
    good = {}
    barred = set()
    anomalies = []
    conflicts = Counter()
    for name, sha, entries in _source_rows(folder, roots[0], "0000903651", counts):
        for e in entries:
            accession = e["accession"]
            if not ACCESSION.fullmatch(accession):
                conflicts["bad_accession_format"] += 1
                continue
            accepted = exact_utc(e["accepted"])
            if accepted is None:
                conflicts["missing_or_nonoffset_SEC_acceptance"] += 1
                barred.add(accession)
                good.pop(accession, None)
                continue
            try:
                filed = date.fromisoformat(str(e["filing_date"]))
            except (ValueError, TypeError):
                conflicts["invalid_filing_date"] += 1
                barred.add(accession)
                good.pop(accession, None)
                continue
            if accepted.date() < filed:
                conflicts["accepted_UTC_before_filing_date"] += 1
                if len(anomalies) < 30:
                    anomalies.append({
                        "accession": accession, "form": e["form"],
                        "filing_date": filed.isoformat(),
                        "acceptance_utc": accepted.isoformat(),
                        "source":name,
                        "acceptance_utc_day_delta":
                            (filed-accepted.date()).days,
                    })
                barred.add(accession)
                good.pop(accession, None)
                continue
            if accession in barred:
                continue
            current = {
                "accession": accession, "form": e["form"],
                "filed": filed.isoformat(), "accepted": accepted.isoformat(),
            }
            prior = good.get(accession)
            if prior is not None and prior != current:
                conflicts["conflicting_duplicate_accession"] += 1
                barred.add(accession)
                del good[accession]
            elif prior is None:
                good[accession] = current
    return good, conflicts, anomalies


def analyze(db: Path, submissions: Path, phase24h: Path,
            *, max_financial_accessions: int = 2000):
    if (db.is_symlink() or not db.is_file() or
        submissions.is_symlink() or not submissions.is_dir()):
        raise ValueError("OFFLINE_BACKUP_OR_SEC_SOURCE_MISSING")
    r = _prior(phase24h)
    good, conflicts, anomalies = _source_accessions(submissions)
    if (len(good) != r["valid_accessions_total"]
        or conflicts["accepted_UTC_before_filing_date"] !=
           r["source_before_filing_date_count_not_double_counted"]):
        raise ValueError("PHASE24H_SOURCE_COUNTS_CHANGED")
    forms = Counter(v["form"] for v in good.values())
    if dict(sorted(forms.items())) != r["forms_all_valid_accessions"]:
        raise ValueError("PHASE24H_FORM_COUNTS_CHANGED")
    financial = sorted((v for v in good.values() if v["form"] in FINANCIAL_FORMS),
                       key=lambda e: (e["filed"], e["accession"]))
    if len(financial) > max_financial_accessions:
        raise ValueError("FINANCIAL_ACCESSIONS_EXCEED_SAFE_BOUND")
    matched = Counter()
    missing = Counter()
    matched_year = Counter()
    missing_year = Counter()
    target_missing = []
    older_missing = Counter()
    in_scope = Counter()
    with closing(sqlite3.connect(db.resolve().as_uri() + "?mode=ro",
                                 uri=True, timeout=15)) as con:
        con.execute("PRAGMA query_only=ON")
        con.execute("PRAGMA busy_timeout=15000")
        indexes = con.execute("PRAGMA index_list(fundamental_facts_source)").fetchall()
        if not any(row[1] == "idx_fundamental_accession" for row in indexes):
            raise ValueError("REQUIRED_SEC_ACCESSION_INDEX_MISSING")
        cmap = _issuer_index(con)
        if len(cmap.get("0000903651", ())) != 1:
            raise ValueError("CIK_CURRENT_MASTER_SECURITY_AMBIGUOUS")
        sid = next(iter(cmap["0000903651"]))
        for e in financial:
            d = date.fromisoformat(e["filed"])
            key = e["form"]
            target = START <= d <= END
            if target:
                in_scope[key] += 1
            has_fact = con.execute(
                """SELECT 1 FROM fundamental_facts_source
                   WHERE security_id=? AND accession_number=?
                     AND source='SEC_EDGAR' LIMIT 1""",
                (sid,e["accession"])
            ).fetchone() is not None
            if has_fact:
                matched[key] += 1
                matched_year[str(d.year)] += 1
            else:
                missing[key] += 1
                missing_year[str(d.year)] += 1
                if target:
                    target_missing.append({
                        "accession":e["accession"],"form":key,
                        "filing_date":e["filed"],
                        "accepted_utc":e["accepted"],
                        "status":"NO_MATCHING_SEC_FACT_IN_EXISTING_BACKUP_NOT_PROOF_OF_MISSING_XBRL",
                    })
                else:
                    older_missing[str(d.year)] += 1

    # Reconcile all 4 form types against the source-backed Phase24h audit.
    for form in FINANCIAL_FORMS:
        if matched[form] != r["forms_with_reviewable_financial_facts"].get(form,0):
            raise ValueError("PHASE24H_MATCHED_FINANCIAL_FORM_COUNT_CHANGED")
        if missing[form] != r["forms_without_financial_facts"].get(form,0):
            raise ValueError("PHASE24H_MISSING_FINANCIAL_FORM_COUNT_CHANGED")
    return {
        "schema": SCHEMA,
        "status":"INOD_FINANCIAL_ACCESSION_DATE_GAPS_CLASSIFIED_REVIEW_ONLY",
        "window":{"start":START.isoformat(),"end":END.isoformat()},
        "total_valid_SEC_accessions":len(good),
        "total_valid_10K_10Q_including_amendments":len(financial),
        "all_years_matched_financial_forms":dict(sorted(matched.items())),
        "all_years_no_fact_financial_forms":dict(sorted(missing.items())),
        "all_years_matched_by_filing_year":dict(sorted(matched_year.items())),
        "all_years_no_fact_by_filing_year":dict(sorted(missing_year.items())),
        "filings_in_target_window_by_form":dict(sorted(in_scope.items())),
        "financial_filings_no_fact_in_target_window_by_form":dict(sorted(
            Counter(v["form"] for v in target_missing).items())),
        "financial_filings_no_fact_in_target_window_count":len(target_missing),
        "financial_no_fact_before_or_after_window_by_year":dict(
            sorted(older_missing.items())),
        "target_window_no_fact_candidates_NOT_verified":target_missing,
        "accepted_UTC_before_filing_date_source_count":
            conflicts["accepted_UTC_before_filing_date"],
        "date_conflict_form_counts":dict(sorted(Counter(
            v["form"] for v in anomalies).items())),
        "date_conflict_examples_bounded":anomalies,
        "date_conflicts_automatically_fixed":False,
        "additional_SEC_source_needed_proven":False,
        "missing_fact_proves_source_gap":False,
        "original_SEC_provenance_independently_verified":False,
        "historical_SimFinId_CIK_certifications":0,
        "PIT_approved":False,
        "database_modified":False,
        "network_requests":0,
        "canonical_prices_written":0,
        "training_performed":False,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    root=Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / (
        "S153ResearchTerminal/runtime"
    )
    p.add_argument("--db", type=Path,default=root/"phase24g/operational_inod_offline_backup.db")
    p.add_argument("--submissions-dir",type=Path,default=root/"sec_submissions")
    p.add_argument("--phase24h",type=Path,default=root/"phase24h/inod_sec_form_gap_review.json")
    p.add_argument("--out",type=Path,default=root/"phase24i/inod_financial_accession_gaps.json")
    a=p.parse_args()
    try:
        report=analyze(a.db,a.submissions_dir,a.phase24h)
        a.out.parent.mkdir(parents=True,exist_ok=True)
        stage=a.out.with_suffix(".json.tmp")
        stage.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",
                         encoding="utf-8")
        stage.replace(a.out)
    except (OSError,ValueError,TypeError,KeyError,sqlite3.Error):
        print("PHASE24I_BLOCKED: PRIOR_SEC_FORM_SOURCE_OR_SQLITE_NOT_RECONCILED")
        return 2
    print(json.dumps({
        "status":report["status"],
        "all_years_financial_no_fact_by_form":
            report["all_years_no_fact_financial_forms"],
        "2024_2025_financial_no_fact_by_form":
            report["financial_filings_no_fact_in_target_window_by_form"],
        "2024_2025_financial_no_fact_count":
            report["financial_filings_no_fact_in_target_window_count"],
        "out_of_window_no_fact_by_year":
            report["financial_no_fact_before_or_after_window_by_year"],
        "UTC_acceptance_before_filing_date_count":
            report["accepted_UTC_before_filing_date_source_count"],
        "report":str(a.out),
        "database_modified":False,"network_requests":0,
        "PIT_certified":False,
    },indent=2,ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
