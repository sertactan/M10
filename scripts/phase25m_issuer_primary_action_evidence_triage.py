"""Phase25M: issuer-published distribution evidence for three of the 127 P2/P3 names.

This creates an independently sourced *issuer-level event* research register;
it does NOT certify ex-date/ADR conversion, link a vendor adjustment jump to
a dividend, approve historical SimFinId↔CIK, or authorize backtests.

All evidence URLs are official issuer SEC or IR pages. Retrieved after
the historical period, not evidence of point-in-time market availability.
"""
from __future__ import annotations
import argparse,csv,io,json,os,math
from pathlib import Path
from collections import Counter

SCHEMA="MERIDYEN_PHASE25M_OFFICIAL_ISSUER_DISTRIBUTION_TRIAGE_V1"
REFERENCES=[
  {"ticker":"CRCT","official_issuer_CIK":"0001828962","event_id":"CRCT_2024_JUL",
   "action_type":"CASH_DIVIDEND_SPECIAL_AND_REGULAR",
   "declared_amounts":{"special":0.40,"semiannual":0.10},"currency":"USD",
   "per_unit":"Class A/B common share",
   "record_date":"2024-07-02","payment_date":"2024-07-19",
   "ex_date":None,"source_url":"https://www.sec.gov/Archives/edgar/data/1828962/000182896225000039/crct-20241231.htm",
   "independent_fact":"Issuer 2024 10-K confirms May 6 2024 declaration, $0.40 special and $0.10 semiannual cash dividend, Jul 2 record / Jul 19 payment."},
  {"ticker":"CRCT","official_issuer_CIK":"0001828962","event_id":"CRCT_2025_JAN",
   "action_type":"CASH_DIVIDEND_REGULAR",
   "declared_amounts":{"semiannual":0.10},"currency":"USD",
   "per_unit":"Class A/B common share",
   "record_date":"2025-01-07","payment_date":"2025-01-21",
   "ex_date":None,"source_url":"https://www.sec.gov/Archives/edgar/data/1828962/000182896225000039/crct-20241231.htm",
   "independent_fact":"Issuer 2024 10-K confirms $0.10 recurring dividend Jan 7 record and Jan 21 payment."},
  {"ticker":"CRCT","official_issuer_CIK":"0001828962","event_id":"CRCT_2025_JUL",
   "action_type":"CASH_DIVIDEND_SPECIAL_AND_REGULAR",
   "declared_amounts":{"special":0.75,"semiannual":0.10},"currency":"USD",
   "per_unit":"Class A/B common share",
   "record_date":"2025-07-07","payment_date":"2025-07-21",
   "ex_date":None,"source_url":"https://investor.cricut.com/news-releases/news-release-details/cricut-inc-reports-first-quarter-2025-financial-results",
   "independent_fact":"Issuer first-quarter 2025 results declare $0.75 special and $0.10 semiannual dividend, Jul 7 record and Jul 21 payment."},
  {"ticker":"IEP","official_issuer_CIK":"0000813762","event_id":"IEP_2025_MAY",
   "action_type":"ELECTIVE_CASH_OR_DEPOSITARY_UNIT_PARTNERSHIP_DISTRIBUTION",
   "declared_amounts":{"cash_or_units":0.50},"currency":"USD",
   "per_unit":"LP depositary unit (NOT ordinary corporate share)",
   "record_date":"2025-05-19","payment_date":"2025-06-25",
   "ex_date":None,"source_url":"https://ielp.gcs-web.com/news-releases/news-release-details/icahn-enterprises-lp-nasdaq-iep-today-announced-its-first-0",
   "independent_fact":"Issuer first-quarter 2025 release describes $0.50 per depositary unit payable cash OR additional depositary units (election). No single simple cash factor certifiable."},
  {"ticker":"EC","official_issuer_CIK":"0001444406","event_id":"EC_2024_COP",
   "action_type":"ORDINARY_AND_EXTRAORDINARY_LOCAL_CASH_DIVIDEND_TWO_INSTALLMENTS",
   "declared_amounts":{"ordinary":278,"extraordinary":34},"currency":"COP",
   "per_unit":"Colombian local share (NOT US ADS)",
   "record_date":None,"payment_date":"2024-04-03",
   "additional_payment_dates":["2024-06-26"],"ex_date":None,
   "source_url":"https://www.ecopetrol.com.co/wps/wcm/connect/8f07b7a3-b160-483f-a5e6-e5a17bd732bc/dividendos-eng.pdf?CVID=oVXCQ8k&MOD=AJPERES",
   "independent_fact":"March 22, 2024 annual meeting approved COP 278 ordinary plus COP 34 extraordinary/local share, installments Apr 3 and Jun 26. ADS conversion and FX/ex-date not independently proven."},
  {"ticker":"EC","official_issuer_CIK":"0001444406","event_id":"EC_2025_COP",
   "action_type":"ORDINARY_LOCAL_CASH_DIVIDEND_TWO_INSTALLMENTS",
   "declared_amounts":{"ordinary":214},"currency":"COP",
   "per_unit":"Colombian local share (NOT US ADS)",
   "record_date":None,"payment_date":"2025-04-04",
   "additional_payment_dates":["2025-04-29"],"ex_date":None,
   "source_url":"https://www.ecopetrol.com.co/wps/portal/Home/en/investors/information-for-shareholders/dividends",
   "independent_fact":"March 28, 2025 shareholder approval for COP 214/local share, minority payment Apr 4 and Apr 29. ADS conversion/FX/ex-date not independently proven."},
]

def _read(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("MISSING_PRIVATE_PHASE25J_REPORT")
    return json.loads(path.read_text(encoding="utf-8"))

def evaluate(path:Path):
    report=_read(path)
    if (report.get("schema")!="MERIDYEN_PHASE25J_P1_SEC_FILINGS_127_TRIAGE_V1"
        or report.get("other_research_candidates")!=127
        or report.get("other_source_price_event_rows")!=167
        or report.get("fully_verified_historical_SimFinId_CIK_pairs")!=0
        or report.get("canonical_backtest_eligible_securities")!=0
        or report.get("production_DB_modified") is not False
        or report.get("WF9_allowed") is not False):
        raise ValueError("P25J_PROVENANCE_INVALID")
    source=report.get("other_event_review_queue")
    if not isinstance(source,list) or len(source)!=167:
        raise ValueError("P25J_ALERT_COUNT_MISMATCH")
    ref_by_ticker={}
    for r in REFERENCES:
        ref_by_ticker.setdefault(r["ticker"],[]).append(r)
    matched=[r for r in source if r.get("ticker") in ref_by_ticker]
    if len(matched)!=13 or {r["ticker"] for r in matched}!={"CRCT","IEP","EC"}:
        raise ValueError("OFFICIAL_SECOND_COHORT_SOURCE_ALERTS_CHANGED")
    refs_checked=[]
    for e in REFERENCES:
        if not e.get("source_url","").startswith("https://"):
            raise ValueError("UNSAFE_OFFICIAL_SOURCE_REFERENCE")
        refs_checked.append({**e,
           "source_kind":"OFFICIAL_ISSUER_OR_SEC_REPORT",
           "issuer_disclosed_action":True,
           "verified_ex_date":False,
           "vendor_adjustment_certified":False,
           "historical_crosswalk_certified":False,
           "issuer_disclosure_not_contemporaneous_archive_verified":True})
    comparisons=[]
    for s in matched:
        ticker=s["ticker"]
        actual_refs=ref_by_ticker[ticker]
        ds=sorted([s["source_observation_date_1"],s["source_observation_date_2"]])
        proposals=[]
        for e in actual_refs:
            dates={"record_date":e.get("record_date"),"payment_date":e.get("payment_date")}
            for extra in e.get("additional_payment_dates",[]):
                dates["additional_payment_"+extra]=extra
            hits=[kind for kind,dt in dates.items() if dt and ds[0]<dt<=ds[1]]
            if hits:
                proposals.append({"event_id":e["event_id"],
                    "issuer_documented_dates_between_price_observations":hits,
                    "the_dates_are_NOT_confirmed_ex_date":True,
                    "currency":e["currency"],"per_unit":e["per_unit"]})
        out={
            "ticker":ticker,"SimFinId":s["SimFinId"],
            "prior_current_CIK_candidate_NOT_historical_verified":
                s["present_day_CIK_candidate_NOT_verified"],
            "source_price_interval_start":ds[0],"source_price_interval_end":ds[1],
            "source_event_type":s["source_event_type"],
            "official_issuer_documents_for_ticker":len(actual_refs),
            "issuer_record_or_payment_dates_between_observations":proposals,
            "source_anomaly_explained":False,
            "source_adjusted_price_proven":False,
            "historical_daily_security_identity_proven":False,
            "PIT_backtest_eligible":False,
            "reason":"NO_INDEPENDENT_EX_DATE_AND_CURRENCY_ADS_OR_EVENT_FACTOR_RECONCILIATION",
        }
        comparisons.append(out)
    return {
        "schema":SCHEMA,
        "status":"P2_ISSUER_CASH_AND_UNIT_ACTION_REFERENCES_NOT_VENDOR_PRICE_CERTIFICATION",
        "unique_issuers_with_official_distribution_documents":3,
        "individual_official_issuer_distribution_reference_events":len(REFERENCES),
        "source_warnings_in_these_three_issuers":len(comparisons),
        "remaining_other_issuer_source_warnings_not_reviewed_in_this_phase":167-len(comparisons),
        "other_candidate_issuer_total":127,
        "official_issuer_action_evidence":refs_checked,
        "source_warning_comparisons":comparisons,
        "canonical_adjusted_prices_certified":0,
        "source_warning_events_fully_verified_ex_date_and_adjustment":0,
        "historical_CIK_full_window_certified":0,
        "delisted_terminal_returns_verified":0,
        "canonical_backtest_eligible":0,
        "WF9_executed":False,"Learning_V3_executed":False,
        "models_modified":False,"original_data_modified":False,
        "operational_DB_modified":False,
    }

def main():
    root=Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))/"S153ResearchTerminal/runtime"
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--phase25j",type=Path,default=root/"phase25j/sec_p1_cik_and_p2p3_event_triage.json")
    p.add_argument("--out",type=Path,default=root/"phase25m/issuer_cash_evidence_secondary_P2.json")
    a=p.parse_args()
    try:
        if a.out.resolve()==a.phase25j.resolve() or a.out.is_symlink():
            raise ValueError("UNSAFE_OUTPUT")
        payload=evaluate(a.phase25j)
        a.out.parent.mkdir(parents=True,exist_ok=True)
        temp=a.out.with_name(a.out.name+".tmp")
        if temp.is_symlink():raise ValueError("UNSAFE_TEMP")
        temp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        temp.replace(a.out)
    except (ValueError,TypeError,KeyError,OSError):
        print("PHASE25M_BLOCKED: ISSUER_SOURCE_COHORT_OR_PROVENANCE_INVALID")
        return 2
    print(json.dumps({
        "status":payload["status"],
        "issuer_count":3,
        "independently_issuer_documented_distribution_references":len(REFERENCES),
        "source_alerts_triaged":13,
        "full_adjustment_factor_certifications":0,
        "canonical_eligible":0,"out":str(a.out)},ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
