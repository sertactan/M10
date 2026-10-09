"""Phase25b — read-only distinct trading-date depth of historical SimFin research cohort.

Streams the unchanged user-downloaded SimFin CSV/ZIP once, checks its SHA256
against Phase24, re-verifies 21 monthly listing files, and measures qualified
SimFinId/ticker/day counts. Does NOT certify that a weekday is a real exchange
session, that adjusted close is correctly adjusted, or historical CIK/FIGI.
No database, API, price write, model training or backtest.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
import json
import math
import os
from pathlib import Path
import sys

from scripts.phase21_simfin_price_source_audit import _file_sha256, _reader
from scripts.phase22_simfin_ohlc_monthly_qa import (
    _classify_ohlc, _monthly_pit, input_text,
)
from scripts.phase25a_simfin_universe_price_depth_audit import (
    _parse, DIRECT_LABEL, WEAK_LABEL, SCHEMA as SCHEMA_25A,
)

SCHEMA = "MERIDYEN_PHASE25B_SIMFIN_DISTINCT_DATE_QUALITY_RESEARCH_V1"
WINDOW = {"start":"2024-01-01","end":"2025-09-30"}
PER_MONTH_KEYS = tuple(
    f"{year}-{month:02d}"
    for year in (2024, 2025)
    for month in range(1, 13)
    if year == 2024 or month <= 9
)
MONTHS = len(PER_MONTH_KEYS)
assert MONTHS == 21
VALID_LABELS = {DIRECT_LABEL, WEAK_LABEL}


def _local_json(file: Path):
    if file.is_symlink() or not file.is_file():
        raise ValueError("PRIVATE_REPORT_UNAVAILABLE")
    return json.loads(file.read_text(encoding="utf-8"))


def _col(columns, *names):
    return next((columns.get(n.lower()) for n in names if columns.get(n.lower())),None)


def cohort(phase24, phase25a):
    s,records=_parse(phase24)
    a=_local_json(phase25a)
    if (a.get("schema")!=SCHEMA_25A
        or a.get("status")!="PHASE25A_RESEARCH_ONLY_SIMFIN_COVERAGE_DEPTH_NOT_CANONICAL"
        or a.get("period")!=WINDOW
        or a.get("SimFinIds_reviewed") != len(records)
        or a.get("source_SHA256") != s.get("source_sha256")
        or a.get("canonical_backtest_eligible_securities") != 0
        or a.get("database_modified") is not False):
        raise ValueError("PHASE25A_PRIVATE_REPORT_OR_PROVENANCE_INVALID")
    eligible={}
    for r in records:
        if (r["valid_OHLC_positive_adj_close_rows_with_month_end_ticker_overlap"]>=100
            and len(r["candidate_CIKs_NOT_verified"])==1
            and len(r["ticker_strings"])==1
            and not r["multiple_exchange_listed_calendar_months"]
            and r["review_class"] in VALID_LABELS
            and r["calendar_months_month_end_ticker_overlap"]==21):
            sid=str(r["SimFinId"])
            if sid in eligible:
                raise ValueError("DUPLICATE_SIMFINID")
            eligible[sid]=r
    if (len(eligible) != a.get("metrics",{}).get("review_21months_single_CIK_not_pit")
        or len(eligible)>s.get("simfin_ids_in_window",0)):
        raise ValueError("PHASE24_AND_25A_ELIGIBILITY_COUNTS_CHANGED")
    return s,a,eligible


def analyze(source:Path, pit_dir:Path, phase24:Path, phase25a:Path):
    original,prior,selected=cohort(phase24,phase25a)
    if source.is_symlink() or not source.is_file():
        raise ValueError("PRICE_SOURCE_UNAVAILABLE")
    sha=_file_sha256(source)
    if sha != original.get("source_sha256"):
        raise ValueError("SIMFIN_INPUT_CHANGED_SHA256_MISMATCH")
    membership=_monthly_pit(
        pit_dir,date.fromisoformat(WINDOW["start"]),date.fromisoformat(WINDOW["end"]))
    if set(membership) != set(PER_MONTH_KEYS):
        raise ValueError("SOURCE_MONTHLY_LISTING_KEYS_CHANGED")

    # One integer ordinal per observed date for each SimFinId+month, not all
    # 6.2m CSV rows. Intended for low-memory Windows machines.
    dates={sid:defaultdict(set) for sid in selected}
    rowcounts=Counter()
    duplicates=Counter()
    weekends=Counter()
    stats=Counter()
    examples=[]
    with input_text(source) as handle:
        reader=_reader(handle)
        names={str(n).strip().lower():n for n in (reader.fieldnames or [])}
        cols={
            "id":_col(names,"SimFinId"),
            "ticker":_col(names,"Ticker","Symbol"),
            "date":_col(names,"Date"),
            "adjusted":_col(names,"Adj. Close","Adjusted Close","Adj Close"),
            "open":_col(names,"Open"),
            "high":_col(names,"High"),
            "low":_col(names,"Low"),
            "close":_col(names,"Close"),
        }
        if any(v is None for v in cols.values()):
            raise ValueError("SOURCE_REQUIRED_COLUMNS_MISSING")
        for row in reader:
            stats["source_rows_streamed"]+=1
            sid=str(row.get(cols["id"]) or "").strip()
            target=selected.get(sid)
            if target is None:
                continue
            ds=str(row.get(cols["date"]) or "").strip()
            if not (len(ds)==10 and WINDOW["start"]<=ds<=WINDOW["end"]):
                continue
            ticker=str(row.get(cols["ticker"]) or "").strip().upper()
            if ticker!=target["ticker_strings"][0] or ticker not in membership.get(ds[:7],set()):
                continue
            stats["selected_id_listed_month_rows"]+=1
            try:
                dt=date.fromisoformat(ds)
            except ValueError:
                continue
            if _classify_ohlc(row,cols)!="VALID":
                stats["selected_ohlc_invalid_rows"]+=1
                continue
            try:
                adjusted=float(row.get(cols["adjusted"]) or "")
            except (ValueError,TypeError):
                adjusted=float("nan")
            if not (math.isfinite(adjusted) and adjusted>0):
                stats["selected_adjusted_invalid_rows"]+=1
                continue
            rowcounts[sid]+=1
            ordinal=dt.toordinal()
            bucket=dates[sid][ds[:7]]
            if ordinal in bucket:
                duplicates[sid]+=1
                if len(examples)<12:
                    examples.append({"SimFinId":sid,"date":ds,"ticker":ticker})
            bucket.add(ordinal)
            if dt.weekday()>=5:
                weekends[sid]+=1
            if stats["source_rows_streamed"]%1_000_000==0:
                print(f"PHASE25B_SOURCE_ROWS_READ={stats['source_rows_streamed']}",
                      file=sys.stderr,flush=True)
    aggregate=Counter()
    per_id=[]
    highest_missing=[]
    for sid,old in sorted(selected.items()):
        if rowcounts[sid]!=old[
            "valid_OHLC_positive_adj_close_rows_with_month_end_ticker_overlap"]:
            raise ValueError("PHASE24_ROW_COUNT_MISMATCH_FOR_SIMFINID_"+sid)
        d=dates[sid]
        counted_months=sum(bool(d.get(key)) for key in PER_MONTH_KEYS)
        if counted_months!=21:
            raise ValueError("PHASE24_MONTH_OVERLAP_MISMATCH_FOR_SIMFINID_"+sid)
        # The denominator is deliberately NOT an NYSE/Nasdaq session calendar.
        per_month_weekday=[
            sum(date.fromordinal(ordinal).weekday()<5 for ordinal in d.get(m,set()))
            for m in PER_MONTH_KEYS
        ]
        all_ords=set().union(*(d.values()))
        weekday_days=sum(date.fromordinal(ordinal).weekday()<5 for ordinal in all_ords)
        sorted_days=sorted(all_ords)
        gaps=[b-a for a,b in zip(sorted_days,sorted_days[1:])]
        longest_gap=max(gaps,default=0)
        active_months15=sum(n>=15 for n in per_month_weekday)
        active_months10=sum(n>=10 for n in per_month_weekday)
        aggregate["candidate_ids"]+=1
        aggregate["distinct_valid_dates"]+=len(all_ords)
        aggregate["valid_source_rows"]+=rowcounts[sid]
        aggregate["duplicate_valid_id_dates"]+=duplicates[sid]
        aggregate["weekend_qualified_rows"]+=weekends[sid]
        for days in (100,200,300,400):
            if weekday_days>=days:
                aggregate[f"ids_with_{days}_plus_distinct_weekdays"]+=1
        if active_months15==21:
            aggregate["ids_with_15_plus_weekdays_in_all_21_months"]+=1
        if active_months10==21:
            aggregate["ids_with_10_plus_weekdays_in_all_21_months"]+=1
        if active_months15>=18:
            aggregate["ids_with_15_plus_weekdays_in_at_least_18_months"]+=1
        if duplicates[sid]:
            aggregate["ids_with_duplicate_qualified_same_date"]+=1
        if weekends[sid]:
            aggregate["ids_with_qualified_weekend_dates"]+=1
        if longest_gap>=8:
            aggregate["ids_with_calendar_gap_8_plus_days"]+=1
        if longest_gap>=15:
            aggregate["ids_with_calendar_gap_15_plus_days"]+=1
        item={
            "SimFinId":sid,"ticker":old["ticker_strings"][0],
            "candidate_CIK_NOT_verified":old["candidate_CIKs_NOT_verified"][0],
            "valid_ohlc_positive_source_adjusted_rows":rowcounts[sid],
            "unique_qualified_dates":len(all_ords),
            "unique_qualified_weekdays_NOT_session_certified":weekday_days,
            "months_with_at_least_10_distinct_qualified_weekdays":active_months10,
            "months_with_at_least_15_distinct_qualified_weekdays":active_months15,
            "minimum_month_distinct_qualified_weekdays":min(per_month_weekday),
            "maximum_gap_between_qualified_date_rows_calendar_days":longest_gap,
            "duplicate_valid_id_date_rows":duplicates[sid],
            "qualified_weekend_rows":weekends[sid],
            "daily_PIT_or_adjustment_certified":False,
        }
        per_id.append(item)
    if aggregate["candidate_ids"]!=len(selected):
        raise ValueError("CANDIDATE_SUM_MISMATCH")
    return {
        "schema":SCHEMA,
        "status":"DISTINCT_SIMFINID_DATE_COUNTS_VERIFIED_RESEARCH_ONLY_NOT_PIT",
        "window":WINDOW,
        "source_price_file_SHA256":sha,
        "phase25a_prior_candidate_21months":len(selected),
        "metrics":dict(sorted(aggregate.items())),
        "stream_totals":dict(sorted(stats.items())),
        "duplicate_examples":examples,
        "candidate_depth_records":per_id,
        "limitations":[
            "A calendar weekday is not proof of an open market session or a holiday-aware trading calendar.",
            "Source Adj.Close positivity does not prove dividends, splits, adjusted returns or delisting proceeds are correctly handled.",
            "Monthly month-end ticker presence is not daily PIT identity and existing CIK is present-day only.",
            "No daily or intraday S15.3/S16/S16-EA canonical scoring or learning is performed.",
        ],
        "canonical_eligible":0,
        "historical_SimFinId_CIK_certifications":0,
        "price_adjustment_certifications":0,
        "operational_DB_modified":False,
        "source_file_modified":False,
        "SEC_data_modified":False,
        "network_calls":0,
        "paid_API_calls":0,
        "model_training_performed":False,
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    runtime=Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))/(
        "S153ResearchTerminal/runtime")
    parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("--pit-dir",type=Path,
                        default=runtime/"phase19/pit_staging")
    parser.add_argument("--phase24",type=Path,
                        default=runtime/"phase24/simfin_sec_cik_candidates.json")
    parser.add_argument("--phase25a",type=Path,
                        default=runtime/"phase25a/simfin_price_depth_research_audit.json")
    parser.add_argument("--out",type=Path,
                        default=runtime/"phase25b/simfin_distinct_daily_depth_research.json")
    args=parser.parse_args()
    try:
        out=args.out.resolve()
        if args.out.is_symlink() or out in {
            args.input.resolve(),args.phase24.resolve(),args.phase25a.resolve()
        } or args.pit_dir.resolve() in out.parents:
            raise ValueError("REPORT_OVERWRITES_SOURCE_OR_PRIOR_REPORT")
        report=analyze(args.input,args.pit_dir,args.phase24,args.phase25a)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        temp=args.out.with_suffix(".json.tmp")
        if temp.is_symlink():
            raise ValueError("UNSAFE_REPORT_OUTPUT_SYMLINK")
        temp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",
                        encoding="utf-8")
        temp.replace(args.out)
    except (OSError,ValueError,TypeError,KeyError):
        print("PHASE25B_BLOCKED: SOURCE_OR_PRIVATE_AUDIT_MISMATCH")
        return 2
    metrics=report["metrics"]
    print(json.dumps({
        "status":report["status"],
        "SimFinIds_21_month_cohort":report["phase25a_prior_candidate_21months"],
        "at_least_400_distinct_weekdays":
            metrics.get("ids_with_400_plus_distinct_weekdays",0),
        "15_plus_days_each_of_21_months":
            metrics.get("ids_with_15_plus_weekdays_in_all_21_months",0),
        "10_plus_days_each_of_21_months":
            metrics.get("ids_with_10_plus_weekdays_in_all_21_months",0),
        "duplicates_id_date":
            metrics.get("duplicate_valid_id_dates",0),
        "ids_with_8_plus_day_calendar_gaps":
            metrics.get("ids_with_calendar_gap_8_plus_days",0),
        "canonical_eligible":0,
        "report":str(args.out),
        "operational_DB_modified":False,
    },ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
