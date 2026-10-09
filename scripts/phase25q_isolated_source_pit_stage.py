"""Phase25Q: versioned, isolated 21-month source-PIT *research* SQLite staging.

This is a point-in-time evidence staging format, not a canonical PIT dataset.
Alpha Vantage month-end snapshots were retrieved retrospectively in 2026;
SimFin adjusted prices are retrospectively adjusted. Neither is known to
have been available to a 2024 trading decision. Do not use for live signals,
backtest grading, model promotion, or Learning V3.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import csv
from datetime import date,datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import sys
from collections import Counter,defaultdict

from data.providers.alpha_vantage_pit_universe import AlphaVantagePitUniverseProvider
from scripts.phase19_alpha_pit_staging import month_ends
from scripts.phase21_simfin_price_source_audit import _reader,_file_sha256
from scripts.phase22_simfin_ohlc_monthly_qa import _classify_ohlc,input_text
from scripts.phase25b_simfin_distinct_daily_depth_audit import WINDOW,PER_MONTH_KEYS

SCHEMA = "MERIDYEN_PHASE25Q_VERSIONED_RESEARCH_STAGING_V1"
LABEL = "RESEARCH_ONLY_NOT_CANONICAL_PIT"
PRODUCTION_TABLES_NEVER_WRITTEN=True

def _load(path:Path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("SOURCE_NOT_ACCESSIBLE")
    return json.loads(path.read_text(encoding="utf-8"))

def _verify_inputs(pit_dir,source,phase24,phase25k):
    prior=_load(phase24)
    last=_load(phase25k)
    if (prior.get("status")!="SIMFIN_ID_TO_CIK_CANDIDATES_ONLY_ZERO_HISTORICAL_ID_CERTIFICATIONS"
        or prior.get("period")!=WINDOW
        or prior.get("historical_identity_certifications")!=0
        or prior.get("canonical_price_selections_written")!=0
        or last.get("schema")!="MERIDYEN_PHASE25K_FULL_UNIVERSE_CANONICAL_ACCEPTANCE_LEDGER_V1"
        or last.get("accepted_canonical_securities")!=0
        or last.get("actual_WF9_executed") is not False
        or last.get("actual_Learning_V3_executed") is not False):
        raise ValueError("PRIOR_RESEARCH_PROVENANCE_INVALID")
    if source.is_symlink() or not source.is_file():
        raise ValueError("PRICE_CSV_MISSING_OR_SYMLINK")
    price_sha=_file_sha256(source)
    if price_sha!=prior.get("source_sha256"):
        raise ValueError("SIMFIN_ORIGINAL_SHA256_CHANGED")
    index=[]
    for day in month_ends(date.fromisoformat(WINDOW["start"]),date.fromisoformat(WINDOW["end"])):
        key=day.isoformat()
        f=pit_dir/(key+".csv")
        m=pit_dir/(key+".manifest.json")
        if f.is_symlink() or m.is_symlink() or not f.is_file() or not m.is_file():
            raise ValueError("MISSING_MONTHLY_SOURCE_OR_MANIFEST_"+key)
        manifest=_load(m)
        raw=f.read_bytes()
        actual=hashlib.sha256(raw).hexdigest()
        if actual!=manifest.get("sha256"):
            raise ValueError("HISTORICAL_MONTH_SHA256_MISMATCH_"+key)
        try:
            records=AlphaVantagePitUniverseProvider.parse_csv(raw.decode("utf-8-sig"),as_of=day)
        except (RuntimeError,UnicodeError) as exc:
            raise ValueError("HISTORICAL_MONTH_CSV_INVALID_"+key) from exc
        if (manifest.get("source")!="ALPHAVANTAGE_LISTING_STATUS_RESEARCH_ONLY"
            or manifest.get("as_of")!=key or actual!=manifest.get("sha256")
            or len(records)!=manifest.get("qualified_stock_rows")
            or manifest.get("historical_pit_identity_certified") is not False
            or manifest.get("stable_cik_or_figi_mapping_verified") is not False
            or str(manifest.get("retrieved_utc",""))[:4] < "2026"):
            raise ValueError("HISTORICAL_MONTH_MANIFEST_UNTRUSTED_"+key)
        index.append((key,records,manifest,actual))
    if len(index)!=21 or tuple(k[:7] for k,_,_,_ in index)!=PER_MONTH_KEYS:
        raise ValueError("MONTHLY_ARCHIVE_NOT_FULL_21_MONTHS")
    if len(last.get("ledger",[]))!=133:
        raise ValueError("PREVIOUS_133_ACCEPTANCE_GATE_CHANGED")
    allhash=hashlib.sha256((SCHEMA+"|"+price_sha+"|"+
        "|".join(k+":"+sha for k,_,_,sha in index)).encode()).hexdigest()
    return prior,last,index,price_sha,allhash

def _db_init(con):
    con.executescript("""
    PRAGMA journal_mode=DELETE;
    PRAGMA foreign_keys=ON;
    PRAGMA synchronous=FULL;
    CREATE TABLE source_artifacts(
       source_key TEXT PRIMARY KEY, kind TEXT NOT NULL,
       source_sha256 TEXT, retrieved_utc TEXT, source_bytes INTEGER,
       original_private_path TEXT NOT NULL, contemporaneous_PIT INTEGER NOT NULL DEFAULT 0
       CHECK(contemporaneous_PIT=0));
    CREATE TABLE monthly_research_membership(
       month_end TEXT NOT NULL,ticker TEXT NOT NULL,exchange TEXT NOT NULL,
       name TEXT,exchange_mic TEXT,ipo_date TEXT,source_key TEXT NOT NULL,
       source_retrieved_utc TEXT NOT NULL,
       market_member_daily_certified INTEGER NOT NULL DEFAULT 0 CHECK(market_member_daily_certified=0),
       PRIMARY KEY(month_end,ticker,exchange));
    CREATE INDEX idx_staging_month_ticker ON monthly_research_membership(ticker,month_end);
    CREATE TABLE source_daily_price(
       simfin_id TEXT NOT NULL,ticker TEXT NOT NULL,trade_date TEXT NOT NULL,
       source_open REAL,source_high REAL,source_low REAL,source_close REAL,
       source_adj_close REAL,source_volume REAL,source_dividend_column REAL,
       listed_in_same_month_end_archive INTEGER NOT NULL,
       source_adjustment_certified INTEGER NOT NULL DEFAULT 0 CHECK(source_adjustment_certified=0),
       historical_security_identity_certified INTEGER NOT NULL DEFAULT 0 CHECK(historical_security_identity_certified=0),
       PRIMARY KEY(simfin_id,ticker,trade_date));
    CREATE INDEX idx_stage_price_ticker_date ON source_daily_price(ticker,trade_date);
    CREATE TABLE candidate_identity(
       simfin_id TEXT PRIMARY KEY,ticker_strings_json TEXT,
       present_day_CIK_candidates_json TEXT,
       source_first_date TEXT,source_last_date TEXT,
       historical_CIK_identity_certified INTEGER NOT NULL DEFAULT 0 CHECK(historical_CIK_identity_certified=0));
    CREATE TABLE candidate_gate(
       simfin_id TEXT PRIMARY KEY,ticker TEXT NOT NULL,
       priority TEXT NOT NULL,missing_evidence TEXT,
       canonical_approved INTEGER NOT NULL DEFAULT 0 CHECK(canonical_approved=0));
    CREATE TABLE external_SEC_fact_reference(
       source TEXT PRIMARY KEY,external_db_path TEXT,
       source_db_bytes INTEGER,SEC_available_at_audited INTEGER NOT NULL DEFAULT 0 CHECK(SEC_available_at_audited=0),
       market_code_modification INTEGER NOT NULL DEFAULT 0 CHECK(market_code_modification=0));
    """)
    con.commit()

def _writerows(con, sql,buf):
    if buf:
        con.executemany(sql,buf)
        buf.clear()

def build(*,pit_dir:Path,source:Path,phase24:Path,phase25k:Path,
          prod_db:Path,out_root:Path):
    prior,last,months,price_sha,version=_verify_inputs(pit_dir,source,phase24,phase25k)
    folder_name="research_pit_"+version[:16]
    final=out_root/folder_name
    temp=out_root/(folder_name+".building")
    if final.exists():
        report=_load(final/"manifest.json")
        if report.get("schema")!=SCHEMA or report.get("staging_version")!=version:
            raise ValueError("STAGING_VERSION_ALREADY_EXISTS_WRONG_MANIFEST")
        existing=sqlite3.connect((final/"research_pit.sqlite").resolve().as_uri()+"?mode=ro",uri=True)
        try:
            if existing.execute("PRAGMA quick_check").fetchone()[0]!="ok":
                raise ValueError("EXISTING_STAGING_INTEGRITY_FAILED")
        finally:
            existing.close()
        return report
    if out_root.is_symlink() or temp.is_symlink() or temp.exists():
        raise ValueError("STAGING_PENDING_TEMP_OR_SYMLINK_REQUIRES_MANUAL_REVIEW")
    if prod_db.resolve()==(temp/"research_pit.sqlite").resolve():
        raise ValueError("OUTPUT_OVERLAPS_PRODUCTION")
    out_root.mkdir(parents=True,exist_ok=True)
    temp.mkdir()
    db=temp/"research_pit.sqlite"
    con=sqlite3.connect(db)
    con.execute("PRAGMA busy_timeout=20000")
    stat=Counter()
    try:
        _db_init(con)
        con.execute("INSERT INTO source_artifacts(source_key,kind,source_sha256,retrieved_utc,source_bytes,original_private_path) VALUES(?,?,?,?,?,?)",
            ("simfin_daily_price","SIMFIN_VENDOR_ADJUSTED_NOT_VERIFIED",price_sha,None,source.stat().st_size,str(source)))
        memberships=defaultdict(set)
        historical_tickers=set()
        for key,entries,manifest,sha in months:
            con.execute("INSERT INTO source_artifacts(source_key,kind,source_sha256,retrieved_utc,source_bytes,original_private_path) VALUES(?,?,?,?,?,?)",
                (key,"ALPHAVANTAGE_HISTORIC_MONTH_END_RETRIEVED_RETROSPECTIVELY",sha,manifest["retrieved_utc"],
                 manifest["bytes"],str(pit_dir/(key+".csv"))))
            rows=[]
            for x in entries:
                exchange=x.exchange.value
                memberships[key[:7]].add(x.ticker)
                historical_tickers.add(x.ticker)
                rows.append((key,x.ticker,exchange,x.name,x.exchange_mic,
                             x.ipo_date.isoformat() if x.ipo_date else None,
                             key,manifest["retrieved_utc"]))
            con.executemany("INSERT OR IGNORE INTO monthly_research_membership(month_end,ticker,exchange,name,exchange_mic,ipo_date,source_key,source_retrieved_utc) VALUES(?,?,?,?,?,?,?,?)",rows)
            stat["month_snapshot_source_records"]+=len(rows)
        for person in prior["candidate_records"]:
            con.execute("INSERT INTO candidate_identity(simfin_id,ticker_strings_json,present_day_CIK_candidates_json,source_first_date,source_last_date) VALUES(?,?,?,?,?)",
                (str(person["SimFinId"]),json.dumps(person["ticker_strings"],ensure_ascii=False),
                 json.dumps(person["candidate_CIKs_NOT_verified"]),
                 person.get("first_price_date"),person.get("last_price_date")))
        for p in last["ledger"]:
            con.execute("INSERT INTO candidate_gate(simfin_id,ticker,priority,missing_evidence) VALUES(?,?,?,?)",
                (str(p["SimFinId"]),p["ticker"],p["priority"],p["missing_evidence"]))
        if prod_db.is_file() and not prod_db.is_symlink():
            con.execute("INSERT INTO external_SEC_fact_reference(source,external_db_path,source_db_bytes) VALUES(?,?,?)",
                ("READ_ONLY_OPERATIONAL_SEC_FACTS_NOT_PIT_CERTIFIED",str(prod_db),prod_db.stat().st_size))
        con.commit()
        cols_required={"id":"SimFinId","ticker":"Ticker","date":"Date","open":"Open",
                       "high":"High","low":"Low","close":"Close","adjusted":"Adj. Close",
                       "volume":"Volume","dividend":"Dividend"}
        buf=[]
        insert="""INSERT OR IGNORE INTO source_daily_price(
           simfin_id,ticker,trade_date,source_open,source_high,source_low,source_close,
           source_adj_close,source_volume,source_dividend_column,listed_in_same_month_end_archive)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)"""
        with input_text(source) as h:
            r=_reader(h)
            names={str(n).strip().lower():n for n in (r.fieldnames or [])}
            cols={k:names.get(v.lower()) for k,v in cols_required.items()}
            if any(cols[k] is None for k in ("id","ticker","date","open","high","low","close","adjusted")):
                raise ValueError("PRICE_SOURCE_REQUIRED_COLUMNS_MISSING")
            for item in r:
                stat["source_rows_streamed"]+=1
                ds=str(item.get(cols["date"]) or "").strip()
                if not WINDOW["start"]<=ds<=WINDOW["end"] or len(ds)!=10:
                    continue
                stat["window_price_rows"]+=1
                sid=str(item.get(cols["id"]) or "").strip()
                ticker=str(item.get(cols["ticker"]) or "").strip().upper()
                if not sid or not ticker:
                    stat["invalid_identity_or_ticker"]+=1
                    continue
                try:
                    d=date.fromisoformat(ds)
                except ValueError:
                    stat["invalid_dates"]+=1
                    continue
                if _classify_ohlc(item,cols)!="VALID":
                    stat["invalid_OHLC"]+=1
                    continue
                try:
                    o,h,l,c,adj=[float(item[cols[k]]) for k in ("open","high","low","close","adjusted")]
                    vol=float(item.get(cols["volume"]) or 0) if cols["volume"] else 0.0
                    div=float(item.get(cols["dividend"]) or 0) if cols["dividend"] else 0.0
                except (TypeError,ValueError):
                    stat["non_numeric_price_or_volume"]+=1
                    continue
                if (not all(math.isfinite(x) for x in (o,h,l,c,adj,vol,div))
                    or not adj>0 or not vol>=0):
                    stat["nonpositive_adj_or_invalid_volume"]+=1
                    continue
                listed=int(ticker in memberships.get(ds[:7],set()))
                buf.append((sid,ticker,ds,o,h,l,c,adj,vol,div,listed))
                stat["valid_rows_in_window"]+=1
                stat["valid_listed_month_row"]+=listed
                if not listed: stat["valid_unlisted_month_row"]+=1
                if d.weekday()>=5:stat["weekday_calendar_warning_rows"]+=1
                if len(buf)>=10000:
                    con.executemany(insert,buf);buf.clear()
                    if stat["valid_rows_in_window"]%500000<10000:
                        print("PHASE25Q_QUALIFIED_SOURCE_ROWS="+str(stat["valid_rows_in_window"]),file=sys.stderr,flush=True)
            _writerows(con,insert,buf)
        con.commit()
        price_count=con.execute("SELECT COUNT(*) FROM source_daily_price").fetchone()[0]
        mem_count=con.execute("SELECT COUNT(*) FROM monthly_research_membership").fetchone()[0]
        status={
           "schema":SCHEMA,"status":LABEL,"staging_version":version,
           "period":WINDOW,"source_price_sha256":price_sha,
           "price_source_size_bytes":source.stat().st_size,
           "month_end_snapshots":len(months),
           "month_end_retrieved_after_backtest_window":True,
           "monthly_membership_rows":mem_count,
           "distinct_month_end_ticker_strings":len(historical_tickers),
           "source_daily_valid_price_rows":price_count,
           "source_duplicate_identity_date_rows_ignored":
               stat["valid_rows_in_window"]-price_count,
           "source_counts":dict(stat),
           "phase24_candidate_identity_rows":con.execute("SELECT COUNT(*) FROM candidate_identity").fetchone()[0],
           "phase25k_research_gate_rows":con.execute("SELECT COUNT(*) FROM candidate_gate").fetchone()[0],
           "price_data_original_path":str(source),"staging_db":str(final/"research_pit.sqlite"),
           "backup_db":str(final/"research_pit.backup.sqlite"),
           "external_sec_db_referenced_not_imported":prod_db.is_file(),
           "independent_PIT_identity_certs":0,
           "independent_adjusted_price_certs":0,
           "backtest_eligible_securities":0,
           "canonical_ready":False,"WF9_executed":False,"Learning_V3_executed":False,
           "production_DB_modified":False,"SEC_or_price_source_modified":False,
           "network_requests":0,
           "warnings":[
              "2026-retrospective AV month-end membership is not 2024 contemporaneous availability.",
              "Stock-only/month-end and symbol-based historical lists do not establish a complete delisted security universe.",
              "Source SimFin Adj.Close may be hindsight-revised and cannot be used as 2024 PIT features.",
              "Missing historical class-level SEC identity, issuer actions, delisting terminal payoffs and SEC accepted/available_at certifications block canonical promotion.",
              "Do not infer a day's PIT membership from same calendar month's END date (lookahead).",
           ],
        }
        if con.execute("PRAGMA quick_check").fetchone()[0]!="ok":
            raise ValueError("STAGING_SQLITE_INTEGRITY_FAILED")
        con.close()
        backup=temp/"research_pit.backup.sqlite"
        with closing(sqlite3.connect(db)) as source_con, closing(sqlite3.connect(backup)) as target_con:
            source_con.backup(target_con,pages=2500)
        with closing(sqlite3.connect(backup)) as check_con:
            if check_con.execute("PRAGMA quick_check").fetchone()[0]!="ok":
                raise ValueError("STAGING_BACKUP_SQLITE_INTEGRITY_FAILED")
        report_path=temp/"manifest.json"
        with report_path.open("x",encoding="utf-8") as f:
            json.dump(status,f,ensure_ascii=False,indent=2)
            f.write("\n")
            f.flush();os.fsync(f.fileno())
        temp.replace(final)
        return status
    finally:
        try: con.close()
        except sqlite3.Error:pass


def main():
    root=Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))/"S153ResearchTerminal/runtime"
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--pit-dir",type=Path,default=root/"phase19/pit_staging")
    p.add_argument("--phase24",type=Path,default=root/"phase24/simfin_sec_cik_candidates.json")
    p.add_argument("--phase25k",type=Path,default=root/"phase25k/canonical_acceptance_133_research_ledger.json")
    p.add_argument("--operational-db",type=Path,default=root/"data/runtime/operational.db")
    p.add_argument("--out-root",type=Path,default=root/"phase25q/staged_datasets")
    a=p.parse_args()
    try:
        out=build(pit_dir=a.pit_dir,source=a.input,phase24=a.phase24,
                  phase25k=a.phase25k,prod_db=a.operational_db,out_root=a.out_root)
    except (ValueError,KeyError,OSError,sqlite3.Error,UnicodeError) as err:
        # Return only controlled error codes; no SEC API keys/credentials.
        print("PHASE25Q_BLOCKED: "+type(err).__name__+":"+str(err)[:100],file=sys.stderr)
        return 2
    print(json.dumps({k:v for k,v in out.items() if k not in {"warnings"}},
                     indent=2,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
