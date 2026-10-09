"""Phase24c — bounded, read-only diagnosis of SEC evidence-table population.

Works on the M10 Windows operational SQLite. No SEC download, API call,
SQLite update/migration, SimFin reads, price promotion or model training.
The bounded samples are NOT exhaustive proof of historical identity.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sqlite3

SCHEMA = "MERIDYEN_PHASE24C_LOCAL_SEC_EVIDENCE_POPULATION_DIAG_V1"
PREVIOUS = "MERIDYEN_PHASE24_SIMFIN_SEC_CIK_CANDIDATES_V1"
NEEDED = {
    "security_master": {"security_id", "cik"},
    "filing_records_source": {"security_id", "source", "filing_date",
                              "accepted_at", "accession_number"},
    "ticker_aliases": {"security_id", "alias", "valid_from", "valid_to",
                       "source", "availability_date"},
    "fundamental_facts_source": {"security_id", "source", "filing_date",
                                 "accepted_at", "available_at", "accession_number"},
}
WINDOW_START = "2024-01-01"
WINDOW_END = "2025-09-30"


def _valid_timestamp(value: object) -> bool:
    from datetime import datetime
    if not value:
        return False
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return d.tzinfo is not None and d.utcoffset() is not None
    except (ValueError, TypeError):
        return False


def _indexed(con: sqlite3.Connection, table: str, column: str) -> bool:
    for row in con.execute(f"PRAGMA index_list({table})"):
        name = str(row[1]).replace('"', '""')
        first = con.execute(f'PRAGMA index_info("{name}")').fetchone()
        if first and first[2] == column:
            return True
    return False


def _bounded_global_rows(con: sqlite3.Connection, table: str,
                         columns: str, limit: int) -> tuple[list, bool]:
    rows = con.execute(f"SELECT {columns} FROM {table} LIMIT ?", (limit+1,)).fetchall()
    return rows[:limit], len(rows)>limit


def _ids_to_probe(previous: dict, limit: int) -> list[str]:
    all_ids: set[str] = set()
    for r in previous["candidate_records"]:
        for sid in r.get("local_security_id_candidates_NOT_verified", []):
            all_ids.add(str(sid))
    keys = sorted(all_ids)
    if len(keys) <= limit:
        return keys
    # Deterministic systematic sample across sorted candidate IDs, not random
    # and not claimed representative of all SEC issuers.
    return [keys[(i * (len(keys)-1)) // (limit-1)] for i in range(limit)]


def analyze(db: Path, phase24: Path, *, sample_ids: int = 24,
            per_id_rows: int = 150) -> dict:
    if not (2 <= sample_ids <= 100 and 10 <= per_id_rows <= 1000):
        raise ValueError("BOUNDED_SAMPLING_LIMIT_REQUIRED")
    if db.is_symlink() or not db.is_file() or phase24.is_symlink() or not phase24.is_file():
        raise ValueError("REQUIRED_EXISTING_SOURCE_MISSING")
    raw = phase24.read_bytes()
    prev = json.loads(raw)
    if (prev.get("schema") != PREVIOUS
        or prev.get("status") != "SIMFIN_ID_TO_CIK_CANDIDATES_ONLY_ZERO_HISTORICAL_ID_CERTIFICATIONS"
        or prev.get("reconciled_phase19_20_21_23") is not True
        or prev.get("historical_identity_certifications") != 0
        or len(prev.get("candidate_records",[])) != prev.get("simfin_ids_in_window")):
        raise ValueError("PHASE24_UNTRUSTED_OR_INCOMPLETE")
    ids = _ids_to_probe(prev, sample_ids)
    conn = sqlite3.connect(db.resolve().as_uri()+"?mode=ro",
                           uri=True, timeout=5)
    try:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        for table, cols in NEEDED.items():
            available={r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            if not cols.issubset(available):
                raise ValueError("REQUIRED_SOURCE_SCHEMA_MISSING_"+table)
        # These bounded samples measure existence and possible empty tables;
        # they DO NOT establish full-table completeness.
        fr, fr_trunc = _bounded_global_rows(
            conn,"filing_records_source",
            "source,filing_date,accepted_at,accession_number",300)
        alias, alias_trunc = _bounded_global_rows(
            conn,"ticker_aliases",
            "source,valid_from,valid_to,availability_date",300)
        stats = {
            "filing_table_any_rows":bool(fr),
            "filing_table_first_300_rows_sampled":len(fr),
            "filing_first_300_rows_truncated":fr_trunc,
            "filing_first_300_SEC_EDGAR_count":sum(r[0]=="SEC_EDGAR" for r in fr),
            "filing_first_300_timezone_accepted_count":
                sum(r[0]=="SEC_EDGAR" and _valid_timestamp(r[2]) for r in fr),
            "alias_table_any_rows":bool(alias),
            "alias_table_first_300_rows_sampled":len(alias),
            "alias_first_300_rows_truncated":alias_trunc,
            "alias_first_300_sourced_bounded_count":sum(
                bool(src and src.upper() != "UNKNOWN" and start and end and av)
                for src,start,end,av in alias
            ),
        }
        indexed={
            t:_indexed(conn,t,"security_id")
            for t in ("filing_records_source","fundamental_facts_source","ticker_aliases")
        }
        breakdown=Counter()
        summary=[]
        for sid in ids:
            # Absent leading security_id index on SEC fact table: no expensive
            # multi-million-row scan; mark result unknown rather than zero.
            row={"security_id":sid}
            for name,query,fields in (
                ("filings",
                 """SELECT source,filing_date,accepted_at,accession_number
                    FROM filing_records_source WHERE security_id=? LIMIT ?""",
                 ("source","filing_date","accepted_at","accession")),
                ("facts",
                 """SELECT source,filing_date,accepted_at,available_at,accession_number
                    FROM fundamental_facts_source WHERE security_id=? LIMIT ?""",
                 ("source","filing_date","accepted_at","available_at","accession")),
                ("aliases",
                 """SELECT source,valid_from,valid_to,availability_date
                    FROM ticker_aliases WHERE security_id=? LIMIT ?""",
                 ("source","valid_from","valid_to","availability")),
            ):
                table={"filings":"filing_records_source",
                       "facts":"fundamental_facts_source","aliases":"ticker_aliases"}[name]
                if not indexed[table]:
                    row[name+"_skipped_missing_leading_index"]=True
                    continue
                rows=conn.execute(query,(sid,per_id_rows+1)).fetchall()
                row[name+"_sample_size"]=min(len(rows),per_id_rows)
                row[name+"_sample_truncated"]=len(rows)>per_id_rows
                rows=rows[:per_id_rows]
                if name=="facts":
                    eligible=[v for v in rows if v[0]=="SEC_EDGAR"]
                    row["SEC_facts_sample"]=len(eligible)
                    row["SEC_facts_with_accession_sample"] = sum(bool(v[4]) for v in eligible)
                    row["SEC_facts_with_real_accepted_at_sample"] = sum(
                        _valid_timestamp(v[2]) for v in eligible)
                    row["SEC_facts_2024_2025_filed_sample"] = sum(
                        bool(v[1] and WINDOW_START <= str(v[1])[:10] <= WINDOW_END)
                        for v in eligible)
                elif name=="filings":
                    eligible=[v for v in rows if v[0]=="SEC_EDGAR"]
                    row["SEC_filing_records_sample"]=len(eligible)
                    row["SEC_filings_2024_2025_filed_sample"] = sum(
                        bool(v[1] and WINDOW_START <= str(v[1])[:10] <= WINDOW_END)
                        for v in eligible)
                    row["SEC_filing_records_real_accepted_at_sample"]=sum(
                        _valid_timestamp(v[2]) for v in eligible)
                else:
                    row["dated_sourced_alias_sample"]=sum(
                        bool(v[0] and v[0]!="UNKNOWN" and v[1] and v[2] and v[3])
                        for v in rows)
            if (row.get("SEC_facts_sample",0)>0 and
                row.get("SEC_filing_records_sample",0)==0 and
                not row.get("filings_skipped_missing_leading_index")):
                diagnosis="SEC_FACTS_PRESENT_NO_FILING_RECORD_IN_BOUNDED_SAMPLE"
            elif row.get("SEC_filing_records_sample",0)>0 and not row.get(
                    "SEC_filing_records_real_accepted_at_sample",0):
                diagnosis="FILINGS_PRESENT_BUT_ACCEPTANCE_TIMESTAMP_MISSING_IN_SAMPLE"
            elif row.get("SEC_filing_records_real_accepted_at_sample",0)>0:
                diagnosis="SOME_SEC_ACCEPTANCE_EVIDENCE_PRESENT_IN_SAMPLE"
            else:
                diagnosis="NOT_ENOUGH_EVIDENCE_IN_BOUNDED_SAMPLE"
            row["diagnostic_NOT_historical_certification"]=diagnosis
            breakdown[diagnosis]+=1
            summary.append(row)
        return {
            "schema":SCHEMA,
            "status":"BOUNDED_SEC_EVIDENCE_POPULATION_DIAG_NOT_CANONICAL",
            "phase24_source_sha256":hashlib.sha256(raw).hexdigest(),
            "candidate_security_ids_in_phase24":
                len({str(k) for r in prev["candidate_records"] for k
                     in r.get("local_security_id_candidates_NOT_verified",[])}),
            "sampled_candidate_security_ids":len(ids),
            "sampling_method":"DETERMINISTIC_SYSTEMATIC_NOT_EXHAUSTIVE",
            "per_security_id_sample_cap":per_id_rows,
            "security_id_leading_indices":indexed,
            "global_bounded_sample":stats,
            "bounded_sample_diagnosis":dict(sorted(breakdown.items())),
            "source_samples":summary,
            "source_population_complete":False,
            "canonical_historical_identity_certified":False,
            "database_modified":False,
            "canonical_price_selection_written":False,
            "api_calls":0,
            "model_training_performed":False,
        }
    finally:
        conn.close()


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    root=Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))/(
        "S153ResearchTerminal/runtime")
    p.add_argument("--db",type=Path,default=root/"data/runtime/operational.db")
    p.add_argument("--phase24",type=Path,default=root/"phase24/simfin_sec_cik_candidates.json")
    p.add_argument("--out",type=Path,default=root/"phase24c/sec_evidence_source_population.json")
    p.add_argument("--sample-ids",type=int,default=24)
    a=p.parse_args()
    try:
        report=analyze(a.db,a.phase24,sample_ids=a.sample_ids)
        a.out.parent.mkdir(parents=True,exist_ok=True)
        staged=a.out.with_suffix(".tmp")
        staged.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",
                          encoding="utf-8")
        staged.replace(a.out)
    except (OSError,ValueError,KeyError,TypeError,sqlite3.Error):
        print("PHASE24C_BLOCKED: EXISTING_SOURCES_OR_READONLY_INDEX_GUARD_FAILED")
        return 2
    print(json.dumps({
        "status":report["status"],
        "sampled_candidate_security_ids":report["sampled_candidate_security_ids"],
        "global_bounded_sample":report["global_bounded_sample"],
        "security_id_leading_indices":report["security_id_leading_indices"],
        "bounded_sample_diagnosis":report["bounded_sample_diagnosis"],
        "report_file":str(a.out),
        "database_modified":False,"canonical_historical_identity_certified":False,
    },ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
