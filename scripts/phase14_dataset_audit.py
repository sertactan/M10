from __future__ import annotations

"""Phase 14: fail-closed audit of historical PIT inputs and physical price files.

NO network downloads, database writes, model scoring or trading.
The results are diagnostics, not independent PIT certification.
Run on the M10 host with its real operational DB and parquet directory.
"""
import argparse
from collections import Counter
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import sqlite3

from core.backtest.wf5_schedule import monthly_snapshot_dates
from core.research.walkforward_readiness import WalkForwardReadinessAuditor
from data.storage.parquet_price_store import ParquetPriceStore


REQUIRED = (
    "universe_snapshot_membership", "canonical_price_selection",
    "fundamental_facts_source", "canonical_model_features",
)
ALLOWED_PIT_SOURCES = frozenset(
    ("STOCK_DATA_PIT", "ALPHAVANTAGE_PIT", "MASSIVE", "IMPORTED_PIT_CANONICAL")
)
SCHEMA = "MERIDYEN_PHASE14_DATASET_AUDIT_V1"


def _date(value):
    return value if isinstance(value, date) else date.fromisoformat(value)


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _provider_status():
    """Only presence and filesystem checks; NEVER expose secrets."""
    def key(name):
        return bool((os.environ.get(name) or "").strip())
    def path(name):
        value=(os.environ.get(name) or "").strip()
        return {"configured":bool(value),
                "exists":bool(value and Path(value).exists()),
                "kind":("directory" if value and Path(value).is_dir()
                        else "file" if value and Path(value).is_file()
                        else "none")}
    return {
        "pit_universe":{"ALPHAVANTAGE_API_KEY":key("ALPHAVANTAGE_API_KEY"),
                        "MASSIVE_API_KEY":key("MASSIVE_API_KEY")},
        "adjusted_prices":{"MASSIVE_API_KEY":key("MASSIVE_API_KEY"),
                           "MARKETPARQUET_ROOT":path("MARKETPARQUET_ROOT"),
                           "SIMFIN_PRICE_BULK_PATH":path("SIMFIN_PRICE_BULK_PATH")},
        "free_sec_companyfacts":"PUBLIC_SEC_SOURCE_NOT_PIT_CERTIFICATE",
    }


def audit(db_path, parquet_root, start="2013-01-01", end="2024-12-31",
          *, price_checks=50000):
    start,end=_date(start),_date(end)
    if end<start or price_checks<0:
        raise ValueError("Invalid Phase14 audit dates/price_checks")
    expected=monthly_snapshot_dates(start,end)
    db=Path(db_path)
    parquet=Path(parquet_root)
    report={
        "schema":SCHEMA,"generated_at":_utc(),
        "start":start.isoformat(),"end":end.isoformat(),
        "requested_dates":len(expected),
        "status":"BLOCKED","wf9_activated":False,
        "pit_independently_verified":False,
        "provider_capabilities":_provider_status(),
        "warnings":["Data coverage and declared source type are not independent PIT certification."],
        "blockers":[],"by_date":[],"physical_prices":{},
    }
    if not db.is_file():
        report["blockers"].append("M10_OPERATIONAL_DB_MISSING")
        return report
    try:
        con=sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True)
        con.row_factory=sqlite3.Row
        try:
            tables={str(x[0]) for x in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            missing=sorted(set(REQUIRED)-tables)
            if missing:
                report["blockers"].append("REQUIRED_TABLES_MISSING")
                report["missing_tables"]=missing
                return report
            chk=con.execute("PRAGMA quick_check").fetchone()
            if chk is None or chk[0]!="ok":
                report["blockers"].append("SQLITE_INTEGRITY_FAILED")
                return report

            from types import SimpleNamespace
            auditor=WalkForwardReadinessAuditor(SimpleNamespace(connection=con))
            present=set(auditor.available_snapshot_dates())
            sources=Counter()
            missing_dates=[]
            for d in expected:
                key=d.isoformat()
                if d not in present:
                    missing_dates.append(key)
                    report["by_date"].append({"date":key,"status":"MISSING_SNAPSHOT"})
                    continue
                row=auditor.audit(d)
                src=con.execute(
                    """SELECT source, COUNT(DISTINCT security_id) AS n
                       FROM universe_snapshot_membership
                       WHERE snapshot_date=? AND exchange IN ('NASDAQ','NYSE','AMEX')
                       GROUP BY source""",(key,)).fetchall()
                for x in src:
                    sources[str(x["source"])] += int(x["n"])
                report["by_date"].append({
                    "date":key, "status":"READY_AS_ASSERTED" if not row.blockers else "BLOCKED",
                    "members":row.universe_members,
                    "exact_pit_source_asserted":row.exact_pit_universe,
                    "price_selection_covered":row.price_covered,
                    "fundamental_covered":row.fundamental_covered,
                    "feature_covered":row.feature_covered,
                    "v141_upstream_ready":row.v141_upstream_ready,
                    "blockers":list(row.blockers),
                    "sources":{str(x["source"]):int(x["n"]) for x in src},
                })
            report["missing_snapshot_dates"]=missing_dates
            report["membership_counts_by_source"]=dict(sources)
            if missing_dates:
                report["blockers"].append("MISSING_MONTHLY_HISTORICAL_MEMBERSHIP")
            if any(x.get("status")=="BLOCKED" for x in report["by_date"]):
                report["blockers"].append("PARTIAL_PIT_PRICE_FUNDAMENTAL_OR_FEATURE_COVERAGE")
            unknown=sorted(set(sources)-ALLOWED_PIT_SOURCES)
            if unknown:
                report["blockers"].append("NON_PIT_UNIVERSE_SOURCE")
                report["non_pit_sources"]=unknown

            if not parquet.is_dir():
                report["blockers"].append("CANONICAL_PRICE_PARQUET_ROOT_MISSING")
                report["physical_prices"]={"status":"PARQUET_ROOT_MISSING"}
                return report

            # A canonical_price_selection row alone is not a price file:
            # ensure physical yearly Parquet partitions exist for selections
            # overlapping the audit window. A yearly file existing does NOT
            # guarantee complete daily price, CA, delisting or 252-session data.
            selections=con.execute("""
                SELECT security_id,source,source_symbol,start_date,end_date
                FROM canonical_price_selection
                WHERE purpose='BACKTEST_ADJUSTED'
                  AND start_date<=? AND end_date>=?
                ORDER BY security_id,source,source_symbol,start_date
            """,(end.isoformat(),start.isoformat()))
            store=ParquetPriceStore(parquet)
            seen=set()
            checked=0
            missing_paths=[]
            n_selections=0
            exhausted=False
            for row in selections:
                n_selections+=1
                lo=max(start.year,date.fromisoformat(row["start_date"]).year)
                hi=min(end.year,date.fromisoformat(row["end_date"]).year)
                for y in range(lo,hi+1):
                    ident=(row["security_id"],row["source"],row["source_symbol"],y)
                    if ident in seen:
                        continue
                    if checked>=price_checks:
                        exhausted=True
                        break
                    seen.add(ident);checked+=1
                    name=store._year_path(row["source"],row["security_id"],
                                          row["source_symbol"],y)
                    if not name.is_file():
                        missing_paths.append({
                            "security_id":row["security_id"],
                            "source":row["source"],
                            "source_symbol":row["source_symbol"],
                            "year":y,
                        })
                if exhausted:
                    break
            report["physical_prices"]={
                "status":("CHECK_LIMIT_REACHED" if exhausted
                          else "PARTITIONS_PRESENT_NOT_BAR_VERIFIED" if not missing_paths
                          else "MISSING_PARTITIONS"),
                "selection_rows_examined":n_selections,"yearly_partitions_checked":checked,
                "yearly_partitions_missing":len(missing_paths),
                "missing_partition_examples":missing_paths[:30],
                "audit_limit":price_checks,
                "individual_bar_adjustments_verified":False,
                "delisting_consideration_verified":False,
            }
            if exhausted:
                report["blockers"].append("PHYSICAL_PARQUET_AUDIT_INCOMPLETE")
            if missing_paths:
                report["blockers"].append("CANONICAL_SELECTION_WITHOUT_PARQUET_PARTITION")
            if n_selections==0:
                report["blockers"].append("NO_BACKTEST_ADJUSTED_SELECTIONS")
            report["status"]=(
                "PREFLIGHT_INPUT_COVERAGE_ASSERTED_NOT_PIT_CERTIFIED"
                if not report["blockers"] else "BLOCKED"
            )
            if not report["blockers"]:
                report["warnings"].append(
                    "All asserted coverage passed lightweight checks; run native WF9, "
                    "verify raw/adjusted bars, security identity, delistings and filing PIT."
                )
        finally:
            con.close()
    except (sqlite3.Error, OSError, ValueError, ImportError) as exc:
        report["status"]="BLOCKED"
        report["blockers"].append("AUDIT_DATABASE_OR_RUNTIME_ERROR")
        report["error_class"]=type(exc).__name__
    return report


def main():
    from scripts.phase13_readiness_report import default_db_path
    root=Path(os.environ.get("S153_RUNTIME_ROOT") or Path(__file__).resolve().parents[1])
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db",type=Path,default=default_db_path())
    p.add_argument("--parquet-root",type=Path,default=root/"data/runtime/parquet")
    p.add_argument("--start",default="2013-01-01")
    p.add_argument("--end",default="2024-12-31")
    p.add_argument("--out",type=Path,default=Path("data/runtime/PHASE14_DATASET_AUDIT.json"))
    p.add_argument("--price-checks",type=int,default=50000)
    p.add_argument("--report-only",action="store_true")
    args=p.parse_args()
    result=audit(args.db,args.parquet_root,args.start,args.end,price_checks=args.price_checks)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"blockers":result["blockers"],
                      "report":str(args.out)},ensure_ascii=False))
    return 0 if args.report_only or not result["blockers"] else 2


if __name__=="__main__":
    raise SystemExit(main())
