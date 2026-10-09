"""Phase25a: read-only breadth/depth readiness audit of private Phase24 SimFinId/CIK candidates.

Not a source-price importer, not PIT identity certification, not a statement
that month overlap represents daily membership, and not a backtest. Reports
non-canonical cohorts / data gaps to prioritize free-data research only.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
import os
from pathlib import Path

SCHEMA = "MERIDYEN_PHASE25A_SIMFIN_PRICE_DEPTH_RESEARCH_GATE_V1"
SOURCE_SCHEMA = "MERIDYEN_PHASE24_SIMFIN_SEC_CIK_CANDIDATES_V1"
SOURCE_STATUS = "SIMFIN_ID_TO_CIK_CANDIDATES_ONLY_ZERO_HISTORICAL_ID_CERTIFICATIONS"
WINDOW = {"start":"2024-01-01","end":"2025-09-30"}
REQUIRED_MONTHS = 21
RISK_LABELS = {
    "SIMFIN_ID_MULTIPLE_TICKERS_REVIEW",
    "TICKER_MULTIPLE_SIMFIN_IDS_REVIEW",
    "MULTIPLE_CIK_OR_EXCHANGE_CANDIDATES_REVIEW",
}
DIRECT_LABEL = "ONE_PRESENT_DAY_SEC_CIK_CANDIDATE_NOT_HISTORICAL_PROOF"
WEAK_LABEL = "ONE_WEAK_PRESENT_DAY_CIK_CANDIDATE_REVIEW"
PERIOD_BUCKETS = ("0", "1-5", "6-11", "12-17", "18-20", "21")


def _whole(x, name):
    if isinstance(x, bool) or not isinstance(x,int) or x < 0:
        raise ValueError("INVALID_NONNEGATIVE_"+name)
    return x


def _strs(row, key):
    val = row.get(key)
    if not isinstance(val,list) or not all(
        isinstance(v,str) and v.strip() for v in val):
        raise ValueError("INVALID_ARRAY_"+key)
    return val


def _bucket(n):
    return ("0" if n == 0 else "1-5" if n<=5 else "6-11" if n<=11
            else "12-17" if n<=17 else "18-20" if n<=20 else "21")


def _parse(source: Path):
    if source.is_symlink() or not source.is_file():
        raise ValueError("PHASE24_SOURCE_MISSING")
    doc=json.loads(source.read_text(encoding="utf-8"))
    if (doc.get("schema")!=SOURCE_SCHEMA
        or doc.get("status")!=SOURCE_STATUS
        or doc.get("period")!=WINDOW
        or doc.get("reconciled_phase19_20_21_23") is not True
        or doc.get("historical_identity_certifications") != 0
        or doc.get("ticker_only_identity_link_accepted") is not False
        or doc.get("canonical_price_selections_written") != 0
        or doc.get("original_SEC_or_price_data_modified") is not False
        or doc.get("model_training_performed") is not False):
        raise ValueError("PHASE24_PRIOR_AUDIT_NOT_SAFE")
    rows=doc.get("candidate_records")
    if (not isinstance(rows,list)
        or len(rows)!=doc.get("simfin_ids_in_window")
        or not 0 < len(rows) <= 100_000):
        raise ValueError("PHASE24_RECORD_COUNT_INVALID")
    return doc,rows


def audit(source: Path)->dict:
    src,records=_parse(source)
    buckets=Counter()
    label_counts=Counter()
    totals=Counter()
    ambiguous_examples=[]
    seen=set()
    for record in records:
        if not isinstance(record,dict):
            raise ValueError("PHASE24_INVALID_RECORD")
        sid=str(record.get("SimFinId","")).strip()
        if not sid or sid in seen:
            raise ValueError("PHASE24_DUPLICATE_SIMFIN_ID")
        seen.add(sid)
        if record.get("certified_historical_SimFinId_CIK") is not False:
            raise ValueError("PHASE24_UNEXPECTED_IDENTITY_CERTIFICATION")
        ticker=_strs(record,"ticker_strings")
        ciks=_strs(record,"candidate_CIKs_NOT_verified")
        exchanges=_strs(record,"multiple_exchange_listed_calendar_months")
        # Classification already emits a candidate label. A ticker with
        # multiple SimFinIds must NOT be silently promoted by one CIK.
        label=record.get("review_class")
        if not isinstance(label,str) or not label:
            raise ValueError("PHASE24_REVIEW_LABEL_MISSING")
        price_rows=_whole(record.get(
            "valid_OHLC_positive_adj_close_rows_with_month_end_ticker_overlap"),"PRICE_ROWS")
        months=_whole(record.get("calendar_months_month_end_ticker_overlap"),"MONTHS")
        allmonths=_whole(record.get("calendar_months_price"),"PRICE_MONTHS")
        totalrows=_whole(record.get("window_price_rows"),"WINDOW_ROWS")
        if (months>REQUIRED_MONTHS or months>allmonths
            or price_rows>totalrows):
            raise ValueError("PHASE24_PRICE_COVERAGE_IMPOSSIBLE")
        label_counts[label]+=1
        buckets[_bucket(months)]+=1
        if price_rows > 0:
            totals["at_least_one_valid_adj_overlap_row"]+=1
        for threshold in (100,200,300,400):
            if price_rows >= threshold:
                totals[f"at_least_{threshold}_valid_adj_overlap_rows"]+=1
        if months == REQUIRED_MONTHS:
            totals["all_21_calendar_months_have_some_matching_price"]+=1
        if months >= 18:
            totals["at_least_18_calendar_months_have_some_matching_price"]+=1
        if not ciks:
            totals["no_present_day_CIK_candidate"]+=1
        if len(ciks)>1:
            totals["multiple_present_day_CIK_candidates"]+=1
        if label in RISK_LABELS:
            totals["explicit_identity_risk_records"]+=1

        # Same deliberately permissive window used in the operator's
        # PowerShell result. The stronger gate is explicitly separate.
        preliminary=(price_rows>=100 and len(ciks)==1
                     and len(ticker)==1 and len(exchanges)==0)
        if preliminary:
            totals["preliminary_single_CIK_100row_not_pit"]+=1
            buckets["preliminary_"+_bucket(months)]+=1
        safer=(preliminary and label in {DIRECT_LABEL,WEAK_LABEL})
        if safer:
            totals["preliminary_excluding_known_identity_risk_not_pit"]+=1
            for minmonths in (6,12,18,21):
                if months>=minmonths:
                    totals[f"review_{minmonths}months_single_CIK_not_pit"]+=1
            if label == DIRECT_LABEL:
                totals["direct_present_day_CIK_candidate_not_pit"]+=1
            else:
                totals["weak_present_day_CIK_candidate_not_pit"]+=1
        if preliminary and not safer and len(ambiguous_examples)<12:
            ambiguous_examples.append({
                "SimFinId":sid,
                "ticker_strings":ticker[:3],
                "identity_review_class":label,
                "matched_price_months":months,
            })

    if sum(buckets[k] for k in PERIOD_BUCKETS)!=len(records):
        raise ValueError("BUCKET_SUM_MISMATCH")
    if (totals["preliminary_single_CIK_100row_not_pit"] >
        totals["at_least_100_valid_adj_overlap_rows"] or
        totals["preliminary_excluding_known_identity_risk_not_pit"] >
        totals["preliminary_single_CIK_100row_not_pit"]):
        raise ValueError("COHORT_INVARIANT_BROKEN")
    return {
        "schema":SCHEMA,
        "status":"PHASE25A_RESEARCH_ONLY_SIMFIN_COVERAGE_DEPTH_NOT_CANONICAL",
        "source_audit_status":src["status"],
        "period":WINDOW,
        "source_SHA256":src.get("source_sha256"),
        "SimFinIds_reviewed":len(records),
        "metrics":dict(sorted(totals.items())),
        "month_coverage_buckets":{k:buckets[k] for k in PERIOD_BUCKETS},
        "preliminary_month_coverage_buckets":{
            k:buckets["preliminary_"+k] for k in PERIOD_BUCKETS
        },
        "review_class_counts":dict(sorted(label_counts.items())),
        "ambiguous_preliminary_examples":ambiguous_examples,
        "limitations":[
            "Rows count only strict OHLC and positive source adjusted close in a matching month-end ticker month.",
            "21 matching calendar months do not prove consecutive daily trading, historical CIK/FIGI identity, point-in-time membership, or delisting.",
            "100+ rows are NOT 100+ distinct trading sessions unless independently checked.",
            "Vendor adjusted close is NOT independently validated for split/dividend/total return.",
            "One present-day CIK candidate never certifies historical issuer identity.",
        ],
        "certified_historical_SimFinId_CIK":0,
        "certified_adjusted_price_securities":0,
        "canonical_backtest_eligible_securities":0,
        "historical_delisting_returns_certified":False,
        "database_modified":False,
        "source_prices_modified":False,
        "model_training_performed":False,
        "paid_API_requests":0,
        "network_requests":0,
    }


def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    root=Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / (
        "S153ResearchTerminal/runtime")
    p.add_argument("--phase24",type=Path,
                   default=root/"phase24/simfin_sec_cik_candidates.json")
    p.add_argument("--out",type=Path,
                   default=root/"phase25a/simfin_price_depth_research_audit.json")
    a=p.parse_args()
    try:
        if a.out.resolve()==a.phase24.resolve() or a.out.is_symlink():
            raise ValueError("OUTPUT_OVERLAPS_PRIOR_AUDIT")
        result=audit(a.phase24)
        a.out.parent.mkdir(parents=True,exist_ok=True)
        temp=a.out.with_suffix(".json.tmp")
        if temp.is_symlink():
            raise ValueError("OUTPUT_SYMLINK_BLOCKED")
        temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",
                        encoding="utf-8")
        temp.replace(a.out)
    except (ValueError,OSError,TypeError,KeyError):
        print("PHASE25A_BLOCKED: PRIVATE_PHASE24_REPORT_INVALID_OR_MISSING")
        return 2
    print(json.dumps({
        "status":result["status"],
        "SimFinIds_reviewed":result["SimFinIds_reviewed"],
        "preliminary_single_CIK_100row_not_pit":
            result["metrics"].get("preliminary_single_CIK_100row_not_pit",0),
        "excluding_known_identity_risk":
            result["metrics"].get(
                "preliminary_excluding_known_identity_risk_not_pit",0),
        "research_18months_single_CIK":
            result["metrics"].get("review_18months_single_CIK_not_pit",0),
        "research_21months_single_CIK":
            result["metrics"].get("review_21months_single_CIK_not_pit",0),
        "canonical_backtest_eligible_securities":0,
        "report":str(a.out),
        "database_modified":False,
    },ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
