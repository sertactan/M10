"""Phase25h: reconcile 15 source-factor diagnostics against documented official distributions.

Research-only conditional source ratio math. Official announcement and effective
dates are *external reference facts*, not price adjustment, CIK, delisting or
look-ahead-free evidence. No network, no DB changes, no model training.
"""
from __future__ import annotations
import argparse
import csv
from datetime import date
import hashlib
import io
import json
import math
import os
from pathlib import Path

from scripts.phase25g_source_factor_cash_diagnostic import SCHEMA as G_SCHEMA, COLS as G_COLS

SCHEMA="MERIDYEN_PHASE25H_OFFICIAL_CASH_SOURCE_RATIO_RECONCILIATION_V1"
# Manually curated issuer/OCC primary-source research references. Some issuer
# pages provide only RECORD date (never silently label it an EX-date).
# The same cash event can explain multiple source warning rows; events below
# must NEVER be counted as separate independent distributions.
def _ref(ex_date, amount, url, date_type="EX_DATE", issue="", published=None, detail=""):
    return {"reference_date":ex_date,"reference_date_type":date_type,
            "announced_cash_USD_per_named_security_unit":amount,
            "reference_url":url,"reference_publication_date":published,
            "issue":issue,"detail":detail}
DOYU_2024=_ref("2024-09-03",9.76,"https://ir.douyu.com/Press-Releases/68f8babd610466245f518985",issue="DOYU",published="2024-07-12",detail="USD per ADS; Nasdaq due-bill and $0.05 ADS bank handling fee; company ex date")
DOYU_2025=_ref("2025-02-21",9.94,"https://ir.douyu.com/Press-Releases/68f8babd610466245f518973",issue="DOYU",published="2025-01-27",detail="USD per ADS; Nasdaq due-bill and $0.05 ADS fee")
HUYA_MAY=_ref("2024-05-09",0.66,"https://ir.huya.com/2024-03-19-HUYA-Inc-Reports-Fourth-Quarter-and-Fiscal-Year-2023-Unaudited-Financial-Results-and-Announces-Special-Cash-Dividend",issue="HUYA",published="2024-03-19",detail="USD per ADS; 2024 company announcement explicitly states May 9 ex date")
HUYA_OCT=_ref("2024-10-09",1.08,"https://ir.huya.com/2024-08-13-HUYA-Inc-Reports-Second-Quarter-2024-Unaudited-Financial-Results-and-Announces-Share-Repurchase-Program-Extension-and-Special-Cash-Dividend","RECORD_DATE",issue="HUYA",published="2024-08-13",detail="USD per ADS; issuer page states RECORD date; exact EX date needs independent NYSE evidence")
HUYA_JUL=_ref("2025-07-01",1.47,"https://ir.huya.com/2025-03-20-HUYA-Inc-Announces-Ex-dividend-Date-for-Recently-Announced-Cash-Dividend",issue="HUYA",published="2025-03-20",detail="USD per ADS; NYSE due bill")
IRS_JUN=_ref("2024-06-03",0.630247,"https://www.irsa.com.ar/en/dividend-distribution-record-date-for-gds-holders/","RECORD_DATE",issue="IRS",detail="Issuer-estimated NET cash USD/GDS; issuer states RECORD date; ex-date and gross/net basis unverified")
IRS_NOV=_ref("2024-11-25",0.998325,"https://www.irsa.com.ar/en/dividend-and-treasury-share-distribution-record-payment-date-for-gds-holders/","RECORD_DATE",issue="IRS",detail="Issuer NET cash USD/GDS record date Nov25; SEPARATE ~3.6013447% stock distribution EX Nov29, OCC memo #55581 https://infomemo.theocc.com/infomemos?number=55581")
SITC_JUN=_ref("2025-06-30",1.50,"https://www.miaxglobal.com/sites/default/files/alert-files/SITC_Dividend__56736.pdf",issue="SITC",published="2025-06-18",detail="OCC memo #56736; USD/common share, ex June30")
SITC_SEP=_ref("2025-09-02",3.25,"https://infomemo.theocc.com/infomemos?number=57019",issue="SITC",published="2025-08-06",detail="OCC memo #57019; USD/common share, record Aug15, pay Aug29, ex Sep2")
TDG_OCT=_ref("2024-10-04",75.0,"https://infomemo.theocc.com/infomemos?number=55249",issue="TDG",published="2024-09-23",detail="OCC memo #55249 USD/common share ex Oct4; issuer https://transdigmgroupinc.gcs-web.com/news-releases/news-release-details/transdigm-group-declares-special-cash-dividend-7500-share-and")
TDG_SEP=_ref("2025-09-02",90.0,"https://infomemo.theocc.com/infomemos?number=57110",issue="TDG",published="2025-08-20",detail="OCC memo #57110 USD/common share ex Sep2, pay Sep12")
ZIM_DEC=_ref("2024-12-02",3.65,"https://investors.zim.com/stock-info/default.aspx",issue="ZIM",detail="Current official dividend history (retroactive): 2.81 regular + .84 special USD/share; historical publication timing not independently certified")
ZIM_MAR=_ref("2025-03-24",3.17,"https://investors.zim.com/stock-info/default.aspx",issue="ZIM",detail="Current official dividend history (retroactive); publication timing unknown")

# Exact observation-pair identity; fail-closed if the Phase25f source record changes.
# Both DOYU_2024 and SITC_SEP appear twice in different source warning intervals.
REFERENCES={
 ("DOYU","2024-08-12","2024-08-19"):DOYU_2024,
 ("DOYU","2024-08-30","2024-09-03"):DOYU_2024,
 ("DOYU","2025-02-03","2025-02-21"):DOYU_2025,
 ("HUYA","2024-05-03","2024-05-29"):HUYA_MAY,
 ("HUYA","2024-10-08","2024-10-22"):HUYA_OCT,
 ("HUYA","2025-06-30","2025-07-01"):HUYA_JUL,
 ("IRS","2024-05-31","2024-06-03"):IRS_JUN,
 ("IRS","2024-11-19","2024-11-27"):IRS_NOV,
 ("SITC","2025-06-02","2025-06-30"):SITC_JUN,
 ("SITC","2025-08-13","2025-08-25"):SITC_SEP,
 ("SITC","2025-08-29","2025-09-02"):SITC_SEP,
 ("TDG","2024-10-03","2024-10-23"):TDG_OCT,
 ("TDG","2025-08-29","2025-09-02"):TDG_SEP,
 ("ZIM","2024-11-29","2024-12-02"):ZIM_DEC,
 ("ZIM","2025-03-18","2025-03-28"):ZIM_MAR,
}

EXTRA=[
 "official_date","official_date_type","official_cash_USD_per_security_unit",
 "official_source_url","official_source_published_date","official_detail",
 "source_pair_crosses_reference_date","cash_delta_USD","cash_delta_pct",
 "numeric_2pct_proximity_only","manual_review_class",
 "source_vendor_adjustment_certified","historical_CIK_certified",
 "delisting_handling_certified","PIT_backtest_eligible",
]

def evaluate(path:Path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("MISSING_PRIVATE_PHASE25G_REPORT")
    raw=path.read_bytes()
    g=json.loads(raw)
    if not isinstance(g,dict) or (
        g.get("schema")!=G_SCHEMA
        or g.get("status")!="SOURCE_FACTOR_CASH_IMPLICATIONS_RESEARCH_ONLY_NOT_OFFICIAL_VERIFICATION"
        or g.get("p1_source_event_rows")!=15 or len(g.get("p1_tickers",[]))!=6
        or g.get("independent_corporate_actions_matched")!=0
        or g.get("canonical_backtest_eligible_securities")!=0
        or g.get("vendor_adjustment_methodology_verified") is not False
        or g.get("production_DB_modified") is not False
        or g.get("SEC_records_modified") is not False
        or g.get("models_modified") is not False
        or g.get("network_requests")!=0
        or g.get("paid_API_requests")!=0
        or g.get("training_performed") is not False
    )):
        raise ValueError("PHASE25G_RESEARCH_PROVENANCE_FAILURE")
    originals=g.get("source_math")
    if not isinstance(originals,list) or len(originals)!=len(REFERENCES):
        raise ValueError("PHASE25G_EVENT_COUNT_CHANGE")
    if set(g["p1_tickers"])!=set(name for name,_,_ in REFERENCES):
        raise ValueError("PHASE25G_UNEXPECTED_P1_TICKERS")
    results=[]
    visited=set()
    for rec in originals:
        key=(rec.get("ticker"),rec.get("source_before_date"),rec.get("source_after_date"))
        if key not in REFERENCES or key in visited:
            raise ValueError("UNMAPPED_OR_DUPLICATE_PHASE25G_EVENT")
        visited.add(key)
        source=REFERENCES[key]
        amt=source["announced_cash_USD_per_named_security_unit"]
        implied=rec.get("conditional_implied_single_cash_per_share")
        p0=rec.get("source_before_raw_close")
        a0=rec.get("source_before_adj_close")
        p1=rec.get("source_after_raw_close")
        a1=rec.get("source_after_adj_close")
        if not all(isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x) and x>0 for x in (p0,a0,p1,a1,amt)):
            raise ValueError("PHASE25G_NONPOSITIVE_NUMERIC")
        f0=p0/a0
        f1=p1/a1
        d=p0*(1-f1/f0)
        if not isinstance(implied,(int,float)) or not math.isclose(d,implied,rel_tol=1e-6,abs_tol=1e-5):
            raise ValueError("PHASE25G_IMPLIED_CASH_PROVENANCE_MISMATCH")
        if rec.get("canonical_adjusted_price_approved") is not False:
            raise ValueError("UNSAFE_ADJUSTED_PRICE_CERTIFICATION")
        reference_date=source["reference_date"]
        cross=rec["source_before_date"]<reference_date<=rec["source_after_date"]
        delta=implied-amt
        delta_pct=delta/amt*100
        near=abs(delta_pct)<=2.0
        if not cross:
            category="REFERENCE_DATE_OUTSIDE_PRICE_OBSERVATIONS"
        elif source["reference_date_type"]!="EX_DATE":
            category="OFFICIAL_RECORD_DATE_ONLY_EX_DATE_NOT_CERTIFIED"
        elif not near:
            category="SOURCE_IMPLIED_AMOUNT_NOT_WITHIN_2PCT_OF_DISTRIBUTION"
        else:
            category="NUMERIC_AMOUNT_NEAR_REFERENCE_NOT_CANONICAL"
        results.append({
            **{k:rec[k] for k in G_COLS},
            "official_date":reference_date,
            "official_date_type":source["reference_date_type"],
            "official_cash_USD_per_security_unit":amt,
            "official_source_url":source["reference_url"],
            "official_source_published_date":source["reference_publication_date"],
            "official_detail":source["detail"],
            "source_pair_crosses_reference_date":cross,
            "cash_delta_USD":round(delta,5),
            "cash_delta_pct":round(delta_pct,3),
            "numeric_2pct_proximity_only":near,
            "manual_review_class":category,
            "source_vendor_adjustment_certified":False,
            "historical_CIK_certified":False,
            "delisting_handling_certified":False,
            "PIT_backtest_eligible":False,
        })
    if visited!=set(REFERENCES):
        raise ValueError("MISSING_EXPECTED_PHASE25G_OBSERVATIONS")
    from collections import Counter
    return {
      "schema":SCHEMA,
      "status":"15_PRIMARY_REFERENCE_COMPARISONS_RESEARCH_ONLY_PRICE_AND_PIT_NOT_CERTIFIED",
      "phase25g_source_SHA256":hashlib.sha256(raw).hexdigest(),
      "reference_provenance":"Research-curated issuer/SEC/OCC URLs; independent historical issuer-CIK and public-release replay NOT proven",
      "reference_count_unique_primary_cash_events":len({(v["issue"],v["reference_date"],v["announced_cash_USD_per_named_security_unit"]) for v in REFERENCES.values()}),
      "source_warning_rows":15,
      "comparisons_by_class":dict(Counter(r["manual_review_class"] for r in results)),
      "numeric_close_rows_not_certified":sum(r["numeric_2pct_proximity_only"] and r["source_pair_crosses_reference_date"] for r in results),
      "review_rows":results,
      "official_event_reference_data_collected":True,
      "official_event_archive_and_publication_PIT_certified":False,
      "corporate_action_price_adjustment_certified":0,
      "historical_issuer_CIK_certified":0,
      "split_dividend_canonical_prices_certified":0,
      "delisting_price_proceeds_certified":0,
      "canonical_backtest_eligible_securities":0,
      "walk_forward_backtest_allowed":False,
      "Learning_V3_allowed":False,
      "SEC_records_modified":False,"original_source_modified":False,
      "production_DB_modified":False,"models_modified":False,
      "network_requests":0,"paid_API_requests":0,"training_performed":False
    }

def _save(path:Path,s:str):
    if path.is_symlink() or path.with_name(path.name+".tmp").is_symlink():
        raise ValueError("OUTPUT_SYMLINK_REFUSED")
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+".tmp")
    temp.write_text(s,encoding="utf-8")
    temp.replace(path)

def main():
    root=Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))/"S153ResearchTerminal/runtime"
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--phase25g",type=Path,default=root/"phase25g/p1_source_factor_cash_diagnostic.json")
    p.add_argument("--out",type=Path,default=root/"phase25h/p1_official_cash_source_reconciliation.json")
    p.add_argument("--csv",type=Path,default=root/"phase25h/p1_official_cash_source_reconciliation.csv")
    a=p.parse_args()
    try:
        outputs={a.out.resolve(),a.csv.resolve()}
        if len(outputs)!=2 or a.phase25g.resolve() in outputs:
            raise ValueError("OUTPUT_PATH_CONFLICT")
        report=evaluate(a.phase25g)
        buf=io.StringIO(newline="")
        writer=csv.DictWriter(buf,fieldnames=G_COLS+EXTRA,lineterminator="\n")
        writer.writeheader()
        for row in report["review_rows"]:
            writer.writerow({field:row.get(field,"") for field in G_COLS+EXTRA})
        _save(a.out,json.dumps(report,ensure_ascii=False,indent=2)+"\n")
        _save(a.csv,buf.getvalue())
    except (ValueError,TypeError,KeyError,OSError,UnicodeError,ZeroDivisionError):
        print("PHASE25H_BLOCKED: SOURCE_EVENT_MAPPING_OR_PROVENANCE_MISMATCH")
        return 2
    print(json.dumps({
        "status":report["status"],
        "source_warning_rows":report["source_warning_rows"],
        "unique_cash_event_references":report["reference_count_unique_primary_cash_events"],
        "comparisons_by_class":report["comparisons_by_class"],
        "numeric_close_rows_NOT_certified":report["numeric_close_rows_not_certified"],
        "PIT_or_canonical_eligible":0,
        "JSON":str(a.out),"CSV":str(a.csv)
    },indent=2,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
