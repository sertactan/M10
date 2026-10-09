"""Phase24m — fail-closed SEC public dissemination / daily backtest handoff.

For all seven INOD 2024-01-01..2025-09-30 financial SEC accessions,
read existing Phase24k/l reports and prepare a research-only candidate
calendar day for future dissemination evidence review. This tool NEVER
approves a trading session or claims that public dissemination occurred at
SEC acceptance time. It does NOT contact SEC, access SQLite or modify models.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, timedelta
import json
import os
from pathlib import Path

from scripts.phase24k_inod_target_sec_availability_audit import SCHEMA as K_SCHEMA
from scripts.phase24l_inod_sec_official_date_crosscheck import SCHEMA as L_SCHEMA

SCHEMA = "MERIDYEN_PHASE24M_SEC_DISSEMINATION_DAILY_REPLAY_GATE_V1"
WINDOW_START = date(2024, 1, 1)
WINDOW_END = date(2025, 9, 30)


def _next_weekday(d: date) -> date:
    """A calendar *candidate* only; NOT an NYSE/Nasdaq holiday-aware session."""
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _report(path: Path, schema: str, status: str) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("PREVIOUS_PRIVATE_AUDIT_REPORT_MISSING")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("schema") != schema or obj.get("status") != status:
        raise ValueError("UNRECOGNIZED_PREVIOUS_PRIVATE_AUDIT_REPORT")
    return obj


def audit(phase24k: Path, phase24l: Path) -> dict:
    k = _report(
        phase24k, K_SCHEMA,
        "INOD_2024_2025_FINANCIAL_PIT_TIMESTAMP_CANDIDATE_AUDIT_ONLY")
    l = _report(
        phase24l, L_SCHEMA,
        "THREE_INOD_SEC_10Q_FILING_DATES_PRIMARY_SOURCE_CROSSCHECKED_NO_PIT")
    if (k.get("eligible_for_canonical_PIT_promotion") is not False
        or k.get("database_modified") is not False
        or k.get("target_window") != {
            "start": WINDOW_START.isoformat(), "end": WINDOW_END.isoformat()}
        or l.get("canonical_PIT_certified") is not False
        or l.get("database_modified") is not False
        or l.get("SEC_public_dissemination_lookahead_gate") != "BLOCKED_UNKNOWN"
        or l.get("public_dissemination_timestamps_verified") != 0
        or l.get("offline_crosschecked_10Q_count") != 3):
        raise ValueError("PIT_OR_PROVENANCE_GATES_NOT_CLOSED")
    input_rows = k.get("accessions", [])
    if (not isinstance(input_rows,list)
        or not 0 < len(input_rows) <= 200
        or len(input_rows) != k.get("counts",{}).get("accessions")
        or any(row.get("PIT_certified") is not False for row in input_rows)):
        raise ValueError("UNTRUSTED_PHASE24K_ACCESSION_ROWS")
    crosschecked = l.get("records", [])
    if not isinstance(crosschecked,list) or len(crosschecked)!=3:
        raise ValueError("INVALID_PHASE24L_CROSSCHECK")
    verified_ids = {}
    for rec in crosschecked:
        id_ = rec.get("accession")
        if (id_ in verified_ids or
            rec.get("official_filing_date_and_acceptance_match_pinned_index")
                is not True or
            rec.get("public_dissemination_time_verified") is not False or
            rec.get("PIT_certified") is not False):
            raise ValueError("PHASE24L_PRIMARY_INDEX_FIELDS_NOT_VERIFIED")
        verified_ids[id_] = rec

    seen=set()
    result=[]
    counts=Counter()
    for row in sorted(input_rows,key=lambda r:(r["filing_date"],r["accession"])):
        id_=row["accession"]
        if id_ in seen:
            raise ValueError("DUPLICATE_FINANCIAL_ACCESSION")
        seen.add(id_)
        filed=date.fromisoformat(row["filing_date"])
        if not (WINDOW_START <= filed <= WINDOW_END):
            raise ValueError("TARGET_WINDOW_NOT_PRESERVED")
        quarantined = row.get("source_chronology") != "NORMAL_CONSIDERED"
        if quarantined:
            match=verified_ids.get(id_)
            if not match or (
                match.get("SEC_accepted_UTC_unchanged") != row["accepted_utc"]
                or match.get("SEC_official_filing_date_unchanged")
                    != row["filing_date"]
                or match.get("form") != row["form"]):
                raise ValueError("AFTER_HOURS_SEC_SOURCE_NOT_CROSSCHECKED")
        if "LOOKAHEAD_RISK_AVAILABLE_BEFORE_SEC_ACCEPTANCE" in row.get("issues",[]):
            raise ValueError("ACTIVE_LOOKAHEAD_RISK_BLOCKS_HANDOFF")
        counts["quarantined" if quarantined else "normal"]+=1
        result.append({
            "accession":id_,
            "form":row["form"],
            "SEC_official_filing_date_unmodified":filed.isoformat(),
            "SEC_accepted_utc_unmodified":row["accepted_utc"],
            "official_date_primary_index_crosschecked":id_ in verified_ids,
            "review_only_next_weekday_after_filing_date":
                _next_weekday(filed).isoformat(),
            "candidate_date_is_verified_exchange_session":False,
            "actual_public_dissemination_timestamp_verified":False,
            "historical_security_identity_certified":False,
            "daily_PIT_replay_use_permitted":False,
            "blockers":[
                "ACTUAL_SEC_PUBLIC_DISSEMINATION_TIMESTAMP_NOT_PROVEN",
                "EXCHANGE_TRADING_CALENDAR_NOT_VERIFIED",
                "HISTORICAL_SIMFINID_CIK_SHARECLASS_NOT_CERTIFIED",
            ],
        })
    if counts["quarantined"]!=3 or counts["normal"]!=4 or set(verified_ids)!={
        r["accession"] for r in result
        if r["official_date_primary_index_crosschecked"]
    }:
        raise ValueError("SEVEN_ACCESSION_COHORT_CHANGED_FROM_AUDITS")
    return {
        "schema":SCHEMA,
        "status":"SEC_DISSEMINATION_REPLAY_HANDOFF_RESEARCH_ONLY_ALL_BLOCKED",
        "window":{"start":WINDOW_START.isoformat(),"end":WINDOW_END.isoformat()},
        "financial_accessions_scoped":len(result),
        "official_filing_date_primary_index_crosschecked":len(verified_ids),
        "weekday_proxy_is_market_session":False,
        "SEC_public_dissemination_proven":0,
        "PIT_replay_eligible_count":0,
        "canonical_PIT_certified":False,
        "source_SEC_dates_modified":False,
        "DB_modified":False,
        "network_requests":0,
        "paid_API_requests":0,
        "model_training_performed":False,
        "records":result,
    }


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    root=Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / (
        "S153ResearchTerminal/runtime")
    p.add_argument("--phase24k",type=Path,default=
                   root/"phase24k/inod_sec_financial_timestamp_evidence.json")
    p.add_argument("--phase24l",type=Path,default=
                   root/"phase24l/inod_sec_primary_filing_date_review.json")
    p.add_argument("--out",type=Path,default=
                   root/"phase24m/inod_sec_dissemination_replay_gate.json")
    a=p.parse_args()
    try:
        out=a.out.resolve()
        if out in {a.phase24k.resolve(),a.phase24l.resolve()}:
            raise ValueError("OUTPUT_OVERLAPS_INPUT")
        report=audit(a.phase24k,a.phase24l)
        a.out.parent.mkdir(parents=True,exist_ok=True)
        temp=a.out.with_suffix(".json.tmp")
        temp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",
                        encoding="utf-8")
        temp.replace(a.out)
    except (OSError,TypeError,ValueError,KeyError):
        print("PHASE24M_BLOCKED: PRIOR_PRIVATE_REPORT_MISMATCH")
        return 2
    print(json.dumps({
        "status":report["status"],
        "financial_accessions_scoped":report["financial_accessions_scoped"],
        "official_filing_date_crosschecked":
            report["official_filing_date_primary_index_crosschecked"],
        "SEC_public_dissemination_proven":0,
        "PIT_replay_eligible_count":0,
        "weekday_proxy_is_market_session":False,
        "report":str(a.out),
        "database_modified":False,
    },ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
