"""Offline evidence completion. No production writes, fetches or new model formulas."""
from __future__ import annotations
from contextlib import closing
from dataclasses import asdict
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import mean, median, pstdev

from app.phase28_real_scoring import (_asof_run, _readonly, _one, _previous_annual,
    _save_feature, _fraction, financial_features, coverage_audit, _extra_financial_rows)
from app.feature_materializer import _score_growth
from core.scoring.math import pos_score, piecewise_score, wa
from core.scoring.dna60 import core48, control12, dna60
from app.recovered_quality import compute_quality, SOURCE_SHA256, INTERPOLATION_SHA256
from core.scoring.s1_s14 import s14, router_scores, gate6, historical_h, n61, false_positive_risk, s1, s2, s3
from core.models.s153_v12 import S153V12Model
from core.models.s153_v14 import S153V14Model
from core.models.s153_v141 import S153V141Model
from core.models.s153_v12_contracts import S153V12Input
from core.models.s153_v14_contracts import S153V14Input
from core.historical.s16_feature_coverage import S16_REQUIRED_FEATURES

SCHEMA = "M10_SCORING_COMPLETION_RESEARCH_V1"
TICKERS = ("INOD", "TMDX", "CRMD", "PENG", "ETON")
BASE_COMMIT = "c0710760e024fd9406c2dbee4312f5f5d1f02dc8"

def digest(path):
    h = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def completion_features(facts, at):
    """Exact fiscal windows; existing materializer rules, explicitly research only."""
    out = {}
    def put(key, value, unit, rows):
        if rows and all(rows):
            _save_feature(out, key, value, unit, rows, period=rows[0]["period_end"], as_of=at,
                          origin="RESEARCH_FROZEN_MATERIALIZER_COMPONENT")
            if key in out:
                out[key]["contract_source"] = "app/feature_materializer.py@" + BASE_COMMIT
    rev = _one(facts, "REVENUE", kind="ANNUAL")
    if not rev:
        return out
    previous = _previous_annual(facts, "REVENUE", rev)
    def aligned(metric, template):
        if not template:
            return None
        return _one(facts, metric, kind="ANNUAL", start=template["period_start"], end=template["period_end"])
    # 3Y/5Y means actual anniversary endpoints, never list[-4] across gaps.
    for metric, prefix in (("REVENUE", "REVENUE"), ("DILUTED_EPS", "EPS")):
        current = aligned(metric, rev)
        for years in (3, 5):
            start = str(int(rev["period_start"][:4])-years)+rev["period_start"][4:]
            end = str(int(rev["period_end"][:4])-years)+rev["period_end"][4:]
            older = _one(facts, metric, kind="ANNUAL", start=start, end=end)
            if current and older and current["value"] > 0 and older["value"] > 0:
                value = (current["value"]/older["value"])**(1/years)-1
                put(f"{prefix}_CAGR_{years}Y", value, "fraction", [current, older])
                put(f"{prefix}_CAGR_{years}Y_SCORE", _score_growth(value), "0_100", [current, older])
    if not previous or previous["value"] <= 0 or rev["value"] <= 0:
        return out
    op, old_op = aligned("OPERATING_INCOME", rev), aligned("OPERATING_INCOME", previous)
    if op and old_op and old_op["value"] > 0:
        ol = ((_fraction(op["value"], old_op["value"]) - _fraction(rev["value"],previous["value"])) * 100)
        put("OL_Q", pos_score(ol, 0, 60), "0_100", [rev, previous, op, old_op])
    margins = {}
    for metric, key, upper in (("OPERATING_INCOME","OM",15), ("GROSS_PROFIT","GM",10)):
        curr, old = aligned(metric, rev), aligned(metric, previous)
        if curr and old:
            delta = 100*(curr["value"]/rev["value"]-old["value"]/previous["value"])
            rows = [rev, previous, curr, old]
            put(key+"_DELTA_PP", delta, "percentage_points", rows)
            put(key+"_Q",pos_score(delta,0,upper),"0_100",rows)
            margins[key] = rows
    cashrows = [aligned(m, p) for p in (rev, previous) for m in ("OPERATING_CASH_FLOW","CAPEX")]
    if all(cashrows):
        c, cap, old_c, old_cap = cashrows
        fcf, prior_fcf = c["value"]-abs(cap["value"]), old_c["value"]-abs(old_cap["value"])
        rows = [rev, previous, *cashrows]
        margin, prior_margin = fcf/rev["value"], prior_fcf/previous["value"]
        delta = (margin-prior_margin)*100
        put("FCF_ANNUAL_YOY", _fraction(fcf,prior_fcf), "fraction", rows)
        put("FCFM_DELTA_PP",delta,"percentage_points",rows)
        put("FCFM_Q",pos_score(delta,0,15),"0_100",rows)
        put("FCFI_Q",wa({"Level":(.5,pos_score(margin*100,-10,20)),
                         "Change":(.5,pos_score(delta,0,20))}),"0_100",rows)
        margins["FCFM"] = rows
    # Full MI requires all three exact-period legs for completion reporting.
    if all(k+"_Q" in out for k in ("OM","GM","FCFM")):
        rows = [r for group in margins.values() for r in group]
        put("MI_Q",wa({k:(w,out[k+"_Q"]["value"]) for k,w in
                       (("OM",.4),("GM",.3),("FCFM",.3))}),"0_100",rows)
    return out


def daily_features(bars, at):
    """Raw daily metrics only; a five-stock sample is not a canonical percentile universe."""
    valid=[]
    for row in bars:
        stamp=datetime.fromisoformat(row["retrieved_at"].replace("Z","+00:00"))
        if not stamp.tzinfo or stamp>at or date.fromisoformat(row["trade_date"])>at.date():
            raise ValueError("future/naive daily evidence")
        if any(not math.isfinite(float(row[k])) for k in ("o","h","l","c","volume")):
            raise ValueError("non-finite daily evidence")
        if row["c"]<=0 or row["l"]<=0 or row["volume"]<0 or row["h"]<max(row["o"],row["c"],row["l"]):
            raise ValueError("invalid OHLCV")
        if len(row["evidence_hash"])!=64:
            raise ValueError("missing source hash")
        valid.append(row)
    valid.sort(key=lambda r:r["trade_date"])
    if len({r["trade_date"] for r in valid}) != len(valid):
        raise ValueError("duplicate daily session")
    if len(valid)<61:
        return {"status":"DATA_MISSING","metrics":{},"bars":len(valid)}
    closes=[r["c"] for r in valid]
    ret=[closes[i]/closes[i-1]-1 for i in range(1,len(closes))]
    last=valid[-1]
    prevvol=mean(r["volume"] for r in valid[-21:-1])
    vols={n:pstdev(ret[-n:]) for n in (10,20,60)}
    ranges=[r["h"]-r["l"] for r in valid[-21:-1]]
    metrics={"return_1d":ret[-1],"momentum5":closes[-1]/closes[-6]-1,
        "momentum20":closes[-1]/closes[-21]-1,"avg_volume20":prevvol,
        "rvol20":last["volume"]/prevvol if prevvol else None,
        "median_dollar_volume20":median(r["c"]*r["volume"] for r in valid[-20:]),
        "range_expansion":(last["h"]-last["l"])/mean(ranges) if mean(ranges)>0 else None,
        "close_location":(last["c"]-last["l"])/(last["h"]-last["l"]) if last["h"]>last["l"] else None,
        "compression_ratio":vols[10]/vols[60] if vols[60]>0 else None,
        **{f"volatility{n}":v for n,v in vols.items()}}
    return {"status":"RAW_RESEARCH_ONLY","metrics":metrics,"bars":len(valid),
        "start":valid[0]["trade_date"],"end":last["trade_date"],
        "source":last["source"],"source_ref":last["source_ref"],
        "retrieved_at":max(r["retrieved_at"] for r in valid),
        "evidence_hashes":sorted({r["evidence_hash"] for r in valid}),
        "limitations":["Uncertified corporate-action adjustment", "No historical provider available_at",
                        "No canonical cross-sectional universe", "Daily bars are not intraday bars"]}


def s16_matrix(daily, financial):
    raw=daily.get("metrics",{})
    links={"volume_ignition":["rvol20"],"momentum_acceleration":["return_1d","momentum5","range_expansion","close_location"],
           "compression":["compression_ratio"],"extension_risk":["momentum5"],
           "liquidity_risk":["median_dollar_volume20"],"liquidity_elasticity":["volatility20","avg_volume20"]}
    result=[]
    for key in S16_REQUIRED_FEATURES:
        metrics={n:raw[n] for n in links.get(key,[]) if raw.get(n) is not None}
        result.append({"key":key,"score":None,"accepted":False,"status":"PARTIAL" if metrics else "DATA_MISSING",
            "raw":metrics,"source":daily.get("source") if metrics else None,
            "source_time":daily.get("end") if metrics else None,
            "hashes":daily.get("evidence_hashes",[]) if metrics else [],
            "normalization":"core/historical/s16_reconstruction.py@"+BASE_COMMIT,
            "missing":"Independent PIT cross-sectional population and source certification" if metrics else
                      "Dated independent raw evidence and all normalized subfeatures",
            "pit_usable":False,"source_quality":"RESEARCH_ONLY"})
    return result


def model_execution(data, features, at):
    raw={k:v["value"] for k,v in features.items()}
    disc={}
    # D01/02 are partial legs; do not relabel them as fully complete factors.
    for key,idx in (("D01_REVENUE_GROWTH_1Y_LEG",1),("D02_EPS_GROWTH_1Y_LEG",2),
                    ("D03_REVENUE_ACCELERATION_LEG",3),("OL_Q",5),("MI_Q",6)):
        if key in raw: disc[idx]=raw[key]
    for index,one,three in ((1,"D01_REVENUE_GROWTH_1Y_LEG","REVENUE_CAGR_3Y_SCORE"),
                            (2,"D02_EPS_GROWTH_1Y_LEG","EPS_CAGR_3Y_SCORE")):
        value=wa({"1Y":(.35,raw.get(one)),"3Y":(.35,raw.get(three)),"Forward":(.30,None)})
        if value is not None:disc[index]=value
    controls={"DIL":raw["F54_DIL_RESEARCH_LEG"]} if "F54_DIL_RESEARCH_LEG" in raw else {}
    gp=wa({"G1Y":(.20,raw.get("D01_REVENUE_GROWTH_1Y_LEG")),
           "G3Y":(.20,raw.get("REVENUE_CAGR_3Y_SCORE")),"G5Y":(.15,raw.get("REVENUE_CAGR_5Y_SCORE")),
           "GForward":(.20,None),"Structure":(.15,None),
           "DecelerationQuality":(.10,raw.get("D03_REVENUE_ACCELERATION_LEG"))})
    if gp is not None:controls["GP"]=gp
    f={k:raw[k] for k in ("OL_Q","MI_Q","FCFI_Q") if k in raw}
    if gp is not None:f["SG"]=gp
    cashflow=raw.get("TTM_FCF_USD")
    if cashflow is not None and cashflow>=0:f["CASH"]=100.0
    elif cashflow is not None and raw.get("CASH_LATEST_USD") is not None:
        f["CASH"]=piecewise_score(raw["CASH_LATEST_USD"]/(abs(cashflow)/12),((3,0),(6,25),(9,45),(12,65),(18,85),(24,100)))
    if "OL_Q" in raw: f["OL_ROUTER"]=raw["OL_Q"]
    if "MI_Q" in raw: f["MI_ROUTER"]=raw["MI_Q"]
    if "D03_REVENUE_ACCELERATION_LEG" in raw: f["GA_ROUTER"]=raw["D03_REVENUE_ACCELERATION_LEG"]
    c48,_=core48(disc); c12=control12(controls); dna=dna60(c48,c12)
    routes=router_scores(f); router=max((v for v in routes.values() if v is not None),default=None)
    h=historical_h(None,None)
    chain={"core48_partial":c48,"control12_partial":c12,"dna60_partial":dna,
           "discovery_inputs_present":len(disc),"discovery_complete_factors":sum(i in disc for i in (3,5,6)),
           "partial_discovery_factors":[i for i in (1,2) if i in disc],
           "forward_estimates_used":False,"control_GP_partial":gp,
           "control_GP_missing":["Forward growth","Structural growth evidence"],"discovery_required":48,"control_inputs_present":len(controls),"control_required":12,
           "router_partial":routes,"gate6_partial":gate6(f),"historical_h":h,
           "n61":n61(f),"false_positive_risk":false_positive_risk(f),
           "missing":["Complete DNA60", "Complete router/gate6", "Dated winner/control similarities", "N61/FPR risk evidence"]}
    aud,_=coverage_audit(data["ticker"],data["quote_price"],at,features)
    lookup={a["model"]:a for a in aud}
    recovered_missing={
        "S4":["Matched Beneish raw accounting fields and manipulation calibration"],
        "S5":["Seven component accounting risks and evidenced interactions"],
        "S8":["Matched distress model liabilities/equity inputs and Ohlson size deflator"],
        "S9":["Nine exact fiscal binary signals including independently evidenced no issuance"],
        "S10":["Valid cash-flow/accrual regression panel and residual-quality normalization"],
    }
    for name,missing in recovered_missing.items():
        lookup[name].update(status="CONTRACT_RECOVERED_INPUTS_MISSING",missing=missing,
                            evidence={"contract_sha256":SOURCE_SHA256,"engine_executed":False,
                                      "note":"Definition recovered; complete-input implementation not qualified."})
    for name,val in (("S1",s1(dna,router,h,n61(f))), ("S2",s2(dna,gate6(f),h,false_positive_risk(f))),
                     ("S3",s3(dna,router,h))):
        lookup[name]["evidence"]={"engine_executed":True,"raw_result":val,"chain":chain}
    common=dict(security_id=data["security_id"],ticker=data["ticker"],as_of=at,
                discovery_factors=disc,control_factors=controls,features=f,current_price=data["quote_price"])
    for name,engine,contract in (("S15.3 V1.2",S153V12Model,S153V12Input),
                                ("S15.3 V1.4",S153V14Model,S153V14Input),
                                ("S15.3 V1.4.1",S153V141Model,S153V14Input)):
        result=asdict(engine().analyze(contract(**common)))
        result["as_of"]=result["as_of"].isoformat()
        lookup[name]["evidence"]={"engine_executed":True,"result":result,
            "normalized_input_keys":sorted(f),"raw_accounting_values_excluded":True}
        lookup[name]["missing"]=list(result["missing_requirements"])
        lookup[name]["status"]="PARTIAL_RESEARCH_INPUTS"
        # Even a renormalized engine number cannot satisfy complete-input acceptance.
    return aud,chain


def sec_acceptance_map(path, cik):
    payload=json.loads(Path(path).read_text(encoding="utf8"))
    if str(payload.get("cik","")).lstrip("0") != str(cik).lstrip("0"):
        raise ValueError("SEC issuer mismatch")
    recent=payload["filings"]["recent"]
    accessions=recent["accessionNumber"]; times=recent["acceptanceDateTime"]
    if len(accessions)!=len(times):raise ValueError("SEC parallel arrays mismatch")
    return dict(zip(accessions,times))


def build_report(source:Path, phase28:Path, archive:Path | None = None, sec_submissions:Path | None = None):
    hashes={"phase27":digest(source),"phase28":digest(phase28)}
    sec_hash=digest(sec_submissions) if sec_submissions else None
    stocks=[]
    inod_verified=set()
    archive_stat=(archive.stat().st_size,archive.stat().st_mtime_ns) if archive else None
    with closing(_readonly(phase28)) as db:
        old=db.execute("SELECT report_json FROM phase28_runs WHERE ticker='INOD'").fetchone()
        prior=json.loads(old[0]) if old else None
    for ticker in TICKERS:
        data,facts,_,at=_asof_run(source,ticker)
        if data["quote_status"]!="SUCCESS":
            raise ValueError("Source quote unavailable: "+ticker)
        if archive:
            facts += _extra_financial_rows(archive,data["security_id"],at)
        # Reuse INOD's completed feature cache; independent other-stock preparation is now authorized.
        if ticker=="INOD" and prior and (prior["price_time"]!=data["quote_time"] or prior["as_of"]!=at.isoformat()):
            raise ValueError("Phase28 cache no longer matches Phase27")
        features=dict(prior["features"]) if ticker=="INOD" and prior else financial_features(facts,at)
        new=completion_features(facts,at); features.update(new)
        with closing(_readonly(source)) as db:
            bars=[dict(r) for r in db.execute("SELECT * FROM research_bars WHERE ticker=? ORDER BY trade_date",(ticker,))]
        # checked_at precedes the request; retrieval completion is the research snapshot clock.
        retrieved=[datetime.fromisoformat(r["retrieved_at"].replace("Z","+00:00")) for r in bars]
        if any(t.tzinfo is None or t>datetime.now(timezone.utc) for t in retrieved):
            raise ValueError("Invalid retrieval clock")
        snapshot_at=max([at,*retrieved])
        daily=daily_features(bars,snapshot_at)
        daily["research_snapshot_at"]=snapshot_at.isoformat()
        models,chain=model_execution(data,features,at)
        quality=compute_quality(facts,at)
        eligible={k for k,v in quality.items() if v["score"] is not None and v["status"]=="VERIFIED_DONE"}
        if ticker=="INOD":
            inod_verified=eligible
        else:
            for key in eligible-inod_verified:
                quality[key]["components"]["unaccepted_calculation"]=quality[key]["score"]
                quality[key]["score"]=None
                quality[key]["status"]="WAITING_INOD_MODEL_ACCEPTANCE"
        for model in models:
            if model["model"] in quality:
                q=quality[model["model"]]
                model.update(score=q["score"],status=q["status"],version=q["version"],
                             evidence=q["evidence"],missing=q["missing"],
                             coverage_pct=100.0 if q["score"] is not None else None,
                             present=len(q["evidence"]["inputs"]),required=4)
        legs={k:v["score"] for k,v in quality.items()}
        s14_value,s14_components=s14(legs)
        s14_row=next(m for m in models if m["model"]=="S14")
        s14_row.update(score=s14_value,status="VERIFIED_DONE" if s14_value is not None else "DATA_MISSING",
                       present=sum(v is not None for v in legs.values()),
                       coverage_pct=100*sum(v is not None for v in legs.values())/6,
                       missing=[k for k,v in legs.items() if v is None],
                       evidence={"engine_executed":True,"legs":quality,"components":s14_components})
        acceptance={}
        if ticker=="INOD" and sec_submissions:
            times=sec_acceptance_map(sec_submissions,data["cik"])
            used={x["accession"] for q in quality.values() for x in q["evidence"]["inputs"]}
            acceptance={a:{"accepted_at":times[a],"source_sha256":sec_hash,
                          "public_dissemination_at":None,"historical_provider_available_at":None}
                        for a in sorted(used) if a in times}
        stocks.append({"ticker":ticker,"price":data["quote_price"],"price_time":data["quote_time"],
            "currency":data["quote_currency"],"financial_period":data["financial_period"],"as_of":at.isoformat(),
            "scope":"CURRENT_RESEARCH_ONLY","features":features,"new_feature_keys":sorted(new),
            "daily":daily,"models":models,"control_chain":chain,"s16_features":s16_matrix(daily,features),
            "sec_acceptance_verifications":acceptance,"quality":quality,"s16_accepted":0,"full_model_count":sum(m["score"] is not None for m in models),"provider_status":data["finance_status"],
            "sec_accepted_at_present":sum(bool(x.get("accepted_at")) for x in facts),"sec_facts":len(facts)})
    if archive and archive_stat!=(archive.stat().st_size,archive.stat().st_mtime_ns):
        raise ValueError("Read-only archive changed")
    if hashes!={"phase27":digest(source),"phase28":digest(phase28)}:
        raise ValueError("Source changed during completion run")
    return {"schema":SCHEMA,"generated_at":datetime.now(timezone.utc).isoformat(),
        "source_sha256":hashes,"sec_submissions_sha256":sec_hash,"stocks":stocks,"canonical_securities":0,"canonical_dates":0,
        "full_model_count":sum(s["full_model_count"] for s in stocks),
        "full_score_securities":sum(s["full_model_count"]>0 for s in stocks),
        "contract_sha256":SOURCE_SHA256,"interpolation_sha256":INTERPOLATION_SHA256,"WF9":"BLOCKED","LearningV3":"NOT_TRAINED",
        "S16_E_activation":"PENDING_APPROVAL","S16_EA":"DATA_MISSING_1M_5M_NEWS_AND_SAME_CLOCK_BASELINE"}


def attach_intraday(report, receipt_path):
    from app.scoring_intraday_research import parse_minutes, five_minute
    receipt_path=Path(receipt_path)
    receipt=json.loads(receipt_path.read_text(encoding="utf8"))
    raw=receipt_path.with_name("response.json").read_bytes()
    if sha256(raw).hexdigest()!=receipt["sha256"]:
        raise ValueError("Intraday source hash changed")
    rows,skipped=parse_minutes(json.loads(raw),"INOD",datetime.fromisoformat(receipt["retrieved_at"]))
    if len(rows)!=receipt["valid_1m"] or len(five_minute(rows))!=receipt["complete_derived_5m"] or skipped!=receipt["skipped"]:
        raise ValueError("Intraday receipt count mismatch")
    if receipt.get("canonical") is not False or receipt.get("alert_generated") is not False:
        raise ValueError("Intraday promotion denied")
    report["intraday_research"]=receipt
    report["S16_EA"]="PARTIAL_RAW_1M_DERIVED_5M_NEWS_AND_BASELINE_MISSING"
    model=next(m for m in report["stocks"][0]["models"] if m["model"]=="S16-EA")
    model["evidence"]={"raw_intraday":receipt,"note":"Raw minute data are not normalized frozen structural/event inputs."}
    model["status"]="PARTIAL"
    return report


def attach_sec_companyfacts_partial(report, receipt_path):
    """Surface new official XBRL ratios without promoting any model score.

    Both the original private SEC response bytes and the derived evidence
    receipt must remain available at attachment time. Report output is sealed
    separately. Source retrieval is current research, never historical PIT.
    """
    from app.sec_companyfacts_quality import (extract_exact_companyfacts,
                                              partial_beneish_diagnostics)
    receipt_path=Path(receipt_path)
    if receipt_path.is_symlink() or receipt_path.name!="quality_partial.json":
        raise ValueError("Expected private SEC XBRL research receipt")
    raw_path=receipt_path.with_name("companyfacts.json")
    if raw_path.is_symlink() or not raw_path.is_file():
        raise ValueError("SEC Companyfacts source missing")
    evidence=json.loads(receipt_path.read_text(encoding="utf8"))
    raw=raw_path.read_bytes()
    if digest(raw_path)!=evidence.get("source_sha256"):
        raise ValueError("SEC Companyfacts raw source hash changed")
    if evidence.get("ticker")!="INOD" or evidence.get("scope")!="CURRENT_RESEARCH_ONLY_NOT_HISTORICAL_PIT":
        raise ValueError("Unknown SEC raw research identity/scope")
    rebuilt=extract_exact_companyfacts(raw,ticker="INOD",cik=evidence["cik"],
        accession=evidence["accession"],retrieved_at=evidence["retrieved_at"],
        fiscal_years=(2024,2025))
    if (rebuilt["selected"]!=evidence.get("selected")
        or rebuilt["missing"]!=evidence.get("missing")
        or partial_beneish_diagnostics(rebuilt["rows"],2025)!=evidence.get("partial_beneish_2025")):
        raise ValueError("SEC partial research receipt no longer matches source")
    if (len(report.get("stocks",[]))!=5 or report["stocks"][0]["ticker"]!="INOD"
            or any(m["model"]=="S14" and m["score"] is not None
                   for m in report["stocks"][0]["models"])):
        raise ValueError("SEC research receipt cannot be attached to promoted S14")
    partial=evidence["partial_beneish_2025"]
    stock=report["stocks"][0]
    stock["sec_companyfacts_partial"]={
        "source":"SEC_EDGAR_COMPANYFACTS", "source_sha256":rebuilt["source_sha256"],
        "accepted_at":evidence.get("accepted_at"),
        "retrieved_at":rebuilt["retrieved_at"],
        "accession":rebuilt["accession"], "fiscal_years":[2024,2025],
        "available_ratio_count":sum(v is not None for v in partial["ratios"].values()),
        "ratios":partial["ratios"], "missing_normalized_tags":rebuilt["missing"],
        "B_Q":None,"S14":None,"historical_pit_accepted":False,
        "receipt_evidence_sha256":digest(receipt_path),
    }
    stock["quality"]["B_Q"].setdefault("components",{})["official_sec_partial_ratios"] = {
        "source_sha256":rebuilt["source_sha256"],"ratios":partial["ratios"],
        "status":"PARTIAL_RAW_XBRL_NOT_FULL_B_Q"}
    return report


def attach_v3_financial_quality(report, receipt_path, companyfacts_path,
                                submissions_path, filing_body_path=None):
    """Attach SEC-backed partial legs without silently promoting a stock score.

    The V3 receipt must be sealed and reproducible from exact private raw SEC
    bytes; the local 10-K HTML must agree if an attested presentation was used.
    Research partials are never S14 canonical or an implied B_Q score.
    """
    from app.scoring_v3_sec_quality import recover
    from scripts.scoring_v3_quality_probe import verify_presentation
    receipt_path=Path(receipt_path)
    if (receipt_path.name!='quality_v3.json' or receipt_path.is_symlink()
        or not receipt_path.is_file()):
        raise ValueError('Missing sealed V3 SEC financial research receipt')
    if Path(str(receipt_path)+'.sha256').read_text(encoding='ascii').strip()!=digest(receipt_path):
        raise ValueError('V3_SEC_RESEARCH_SEAL_CHANGED')
    receipt=json.loads(receipt_path.read_text(encoding='utf8'))
    c, s=Path(companyfacts_path),Path(submissions_path)
    if not c.is_file() or not s.is_file() or c.is_symlink() or s.is_symlink():
        raise ValueError('Original raw SEC cached sources required')
    source,subs=c.read_bytes(),s.read_bytes()
    if sha256(source).hexdigest()!=receipt.get('source_sha256') or sha256(subs).hexdigest()!=receipt.get('submissions_sha256'):
        raise ValueError('V3_SEC_RESEARCH_SOURCE_CHANGED')
    reviewed=receipt.get('presentation_review',{})
    if reviewed.get('verified') is True:
        path=Path(filing_body_path) if filing_body_path is not None else None
        if not path or path.is_symlink() or not path.is_file():
            raise ValueError('Attested income statement document required')
        if digest(path)!=reviewed.get('document_sha256'):
            raise ValueError('10-K body hash changed')
        if verify_presentation(path.read_bytes(),source,subs)!=reviewed:
            raise ValueError('10-K source presentation review changed')
    recomputed=recover(source,subs,retrieved_at=receipt['retrieved_at'],
                       presentation_review=reviewed)
    if json.loads(json.dumps(recomputed,ensure_ascii=False,allow_nan=False))!=receipt:
        raise ValueError('V3_SEC_RESEARCH_RECOMPUTATION_MISMATCH')
    if (not report.get('stocks') or report['stocks'][0]['ticker']!='INOD'
        or report['stocks'][0].get('quality',{}).get('B_Q',{}).get('score') is not None):
        raise ValueError('V3 financial diagnostics may not overwrite a real B_Q score')
    stock=report['stocks'][0]
    if any(m['score'] is not None and m['model'] in ('S6','S14') for m in stock['models']):
        raise ValueError('V3 research-only diagnostics may not overwrite scored model')
    stock['sec_quality_v3']={
        'schema':receipt['schema'], 'scope':receipt['scope'],
        'source_sha256':receipt['source_sha256'],
        'receipt_sha256':digest(receipt_path),
        'filings':receipt['filings'],
        'source_fiscal_years':[2023,2024,2025],
        'B_Q_risk_components':receipt['beneish']['risk_components'],
        'B_Q_risk_count':receipt['beneish']['verified_risk_count'],
        'B_Q_required_risk_count':7,
        'B_Q_ratios':receipt['beneish']['ratios'],
        'B_Q_score':None,
        'S6_partial':receipt['dechow']['verified_partial'],
        'S6_partial_count':receipt['dechow']['partial_input_count'],
        'S6_score':None,'S14_score':None,
        'missing_beneish':receipt['beneish']['missing'],
        'missing_dechow':receipt['dechow']['missing'],
        'historical_pit_accepted':False}
    return report


def attach_v3_sec_forensic_candidates(report, receipt_path, submissions_path,
                                     filing_cache):
    """Verify 2024–26 SEC body candidates and expose review status, no S13 risk.

    Every displayed candidate's source bytes are independently re-hashed and
    parsed from the local official filing cache. Term hits cannot become
    reviewed risk or independent serious flags.
    """
    from scripts.scoring_v3_sec_filing_evidence import collect
    receipt_path=Path(receipt_path)
    if (receipt_path.is_symlink() or not receipt_path.is_file()
        or receipt_path.suffix.lower()!='.json'):
        raise ValueError('Forensic candidate research receipt missing')
    previous=json.loads(receipt_path.read_text(encoding='utf8'))
    if (previous.get('ticker')!='INOD' or previous.get('status')!='REVIEW_REQUIRED'
        or previous.get('S13') is not None or previous.get('S14') is not None
        or previous.get('canonical_accepted') is not False
        or previous.get('independent_serious_flags_review')!='REVIEW_REQUIRED'):
        raise ValueError('Forensic raw candidates cannot promote S13 score')
    fresh=collect(Path(submissions_path),Path(filing_cache),contact=None,
                  offline=True,max_downloads=0,as_of=previous['as_of'],max_8k=30)
    for key in ('filings','blocks','status','expected_filing_count',
                'body_filing_count','missing_body_accessions'):
        if previous.get(key)!=fresh.get(key):
            raise ValueError('SEC forensic receipt mismatches signed local SEC bodies: '+key)
    if not report.get('stocks') or report['stocks'][0].get('ticker')!='INOD':
        raise ValueError('INOD research collection required')
    stock=report['stocks'][0]
    s13=next((m for m in stock['models'] if m['model']=='S13'),None)
    if s13 is None or s13['score'] is not None:
        raise ValueError('Forensic research candidates cannot overwrite scored S13')
    overview={
        'status':'REVIEW_REQUIRED',
        'body_filing_count':previous['body_filing_count'],
        'expected_filing_count':previous['expected_filing_count'],
        'reviewed_risk_block_count':0,
        'required_risk_block_count':7,
        'passage_filing_counts':{k:v['passage_sources_count'] for k,v in previous['blocks'].items()},
        'review_missing':['HUMAN_SEVEN_BLOCK_RUBRIC',
            'INDEPENDENT_SERIOUS_FLAG_REVIEW',
            'REVENUE_RECOGNITION_CREDIT_RISK_CONTEXT',
            'SHARE_BASED_COMPENSATION_GOVERNANCE_CONTEXT'],
        'source_report_sha256':digest(receipt_path),
        'sources':[{'accession':row['accession'], 'form':row['form'],
                    'source_ref':row['source_ref'],
                    'content_sha256':row['source_content_sha256'],
                    'accepted_at':row['accepted_at'],
                    'retrieved_at':row['retrieved_at']}
                   for row in previous['filings']],
        'independent_serious_flags':None,
        'S13_score':None,'canonical_accepted':False,
    }
    stock['sec_forensic_v3']=overview
    s13['status']='REVIEW_REQUIRED'
    s13['missing']=overview['review_missing']
    s13['evidence']={'candidate_sources':overview,
                      'review_risk_scores_are_not_inferred':True,
                      'engine_executed':False}
    events=[{'accession':x['accession'],'form':x['form'],
             'sec_accepted_at':x['accepted_at'],
             'source_ref':x['source_ref'],
             'source_content_sha256':x['content_sha256'],
             'first_publication_at':None,'provider_historical_available_at':None,
             'timestamp_usable_as_verified_news':False}
            for x in overview['sources'] if x['form'] in ('8-K','8-K/A')]
    stock['sec_event_candidates_v3']={
        'status':'SEC_ACCEPTANCE_EVENT_CANDIDATES_ONLY',
        'count':len(events),'events':events,'verified_early_alerts':0,
        'source':'OFFICIAL_SEC_ARCHIVE_FILING_BODY',
        'research_scope_only':True,
        'missing':['FIRST_PUBLICATION_TIMESTAMP','PROVIDER_AS_OF_AVAILABILITY',
                   'SAME_CLOCK_BASELINE','EXCHANGE_CERTIFIED_SESSION_CALENDAR']}
    alert=next((m for m in stock['models'] if m['model']=='S16-EA'),None)
    if alert is not None:
        if alert['score'] is not None:
            raise ValueError('Cannot promote research filing candidates as S16-EA')
        alert.setdefault('evidence',{})['sec_event_candidates_v3']=stock['sec_event_candidates_v3']
    return report


def attach_v3_jones_peer_audit(report, receipt_path, companyfacts_path,
                               submissions_path):
    """Show real S11 target-vs-peer coverage, never count incomplete OLS."""
    receipt_path=Path(receipt_path)
    if receipt_path.name!='report.json' or not receipt_path.parent.name.startswith('v3_jones_'):
        raise ValueError('Only isolated SEC Jones research reports accepted')
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise ValueError('Jones research report missing')
    if Path(str(receipt_path)+'.sha256').read_text(encoding='ascii').strip()!=digest(receipt_path):
        raise ValueError('SEC_JONES_RESEARCH_SEAL_CHANGED')
    payload=json.loads(receipt_path.read_text(encoding='utf8'))
    result=payload.get('INOD_S11',{})
    target=result.get('target') or {}
    if (payload.get('scope')!='CURRENT_RESEARCH_ONLY_NOT_HISTORICAL_PIT'
            or payload.get('canonical_accepted') is not False
            or result.get('canonical_accepted') is not False
            or result.get('ticker')!='INOD'
            or result.get('score') is not None
            or target.get('cik')!='0000903651'
            or not isinstance(target.get('selected'),list)
            or result.get('eligible_peer_count') != 0
            or result.get('minimum_peer_count') != 20):
        raise ValueError('Unexpected S11 cohort or unverified score promotion')
    if (digest(companyfacts_path)!=target.get('companyfacts_sha256')
            or digest(submissions_path)!=target.get('submissions_sha256')):
        raise ValueError('SEC_JONES_RESEARCH_RAW_SOURCE_CHANGED')
    if report['stocks'][0]['ticker']!='INOD':
        raise ValueError('INOD report required')
    s11=next(m for m in report['stocks'][0]['models'] if m['model']=='S11')
    if s11['score'] is not None:
        raise ValueError('Cannot replace an accepted numeric S11 model score')
    data={
        'status':'SOURCE_TARGET_COMPLETE_PEER_COHORT_MISSING',
        'target_exact_accounting_fields':len(target['selected']),
        'required_target_exact_accounting_fields':8,
        'eligible_industry_year_peers':result['eligible_peer_count'],
        'minimum_eligible_peers':result['minimum_peer_count'],
        'stock_universe_count':payload['universe']['total_security_master'],
        'missing':result.get('blockers',[]),
        'source_sha256':target['companyfacts_sha256'],
        'report_sha256':digest(receipt_path),
        'S11':None,'historical_pit_accepted':False,
    }
    report['stocks'][0]['sec_jones_v3']=data
    s11['status']='DATA_MISSING'
    s11['missing']=data['missing']
    s11['evidence']={'peer_research_audit':data,'engine_executed':False}
    return report


def attach_task9_issuance_evidence(report, receipt_path, companyfacts_path,
                                   submissions_path, filing_cache):
    """Source-recompute ISSUE=1 into S6 research coverage, not a full S6 score.

    Validates both filed 10-K bytes, exact-year original SEC XBRL records,
    accession acceptance, audited issuance statements and SHA-sealed receipt.
    """
    from app.task9_financial_recovery import recover_task9_evidence
    receipt_path=Path(receipt_path)
    if (receipt_path.name!='financial_recovery.json' or receipt_path.is_symlink()
        or not receipt_path.parent.name.startswith('task9_')
        or not receipt_path.is_file()):
        raise ValueError('Task9 private research receipt missing')
    seal=Path(str(receipt_path)+'.sha256')
    if not seal.is_file() or seal.read_text(encoding='ascii').strip()!=digest(receipt_path):
        raise ValueError('TASK9_FINANCIAL_EVIDENCE_SEAL_CHANGED')
    packet=json.loads(receipt_path.read_text(encoding='utf-8'))
    if (packet.get('schema')!='MERIDYEN_TASK9_FILING_EVIDENCE_V1'
        or packet.get('S6') is not None or packet.get('B_Q') is not None
        or packet.get('S14') is not None or packet.get('historical_pit_accepted') is not False):
        raise ValueError('Task9 receipt attempts to promote research score')
    fact_path=Path(companyfacts_path)
    subs_path=Path(submissions_path)
    if any(not path.is_file() or path.is_symlink() for path in (fact_path,subs_path)):
        raise ValueError('Task9 original SEC sources required')
    facts,subs=fact_path.read_bytes(),subs_path.read_bytes()
    filenames={2024:'000141057825000194_inod-20241231x10k.htm',
               2025:'000110465926020655_inod-20251231x10k.htm'}
    sources={}
    for year,name in filenames.items():
        source=Path(filing_cache)/name
        if not source.is_file() or source.is_symlink():
            raise ValueError('Task9 original 10-K body missing')
        sources[year]=source.read_bytes()
    recomputed=recover_task9_evidence(facts,subs,sources,retrieved_at=packet['as_of'])
    if json.loads(json.dumps(recomputed,allow_nan=False,ensure_ascii=False))!=packet:
        raise ValueError('TASK9_FINANCIAL_EVIDENCE_REPLAY_MISMATCH')
    if (not report.get('stocks') or report['stocks'][0]['ticker']!='INOD'
        or report['stocks'][0].get('quality',{}).get('S14',{}).get('score') is not None):
        raise ValueError('INOD incomplete scoring packet required')
    stock=report['stocks'][0]
    s6=next((m for m in stock['models'] if m['model']=='S6'),None)
    if s6 is None or s6.get('score') is not None:
        raise ValueError('Research ISSUE cannot replace accepted S6 score')
    previous=stock.get('sec_quality_v3')
    if not previous or previous['S6_partial_count']!=4:
        raise ValueError('Prior four independent S6 features required')
    score_input=packet['S6_ISSUE']
    if score_input!=1 or packet['S6_total_verified_components']!=5:
        raise ValueError('Unverified positive cash exercise cannot become ISSUE')
    data={
        'source_scope':'CURRENT_RESEARCH_NOT_HISTORICAL_PIT',
        'receipt_sha256':digest(receipt_path),
        'companyfacts_sha256':packet['companyfacts_sha256'],
        'filing_bodies_sha256':packet['filing_bodies_sha256'],
        'issuance':packet['issuance'],
        'S6_ISSUE':1, 'S6_verified_count':5, 'S6_score':None,
        'credit_facility':packet['credit_facility'],
        'long_term_obligations':packet['long_term_obligations'],
        'ppe_depreciation':packet['ppe_depreciation'],
        'inventory':packet['inventory'], 'RSST':packet['RSST'],
        'LVGI':None,'DEPI':None,'B_Q':None,'S14':None,
        'historical_pit_accepted':False,
    }
    previous['S6_partial']['ISSUE']=1
    previous['S6_partial_count']=5
    previous['missing_dechow']=[k for k in previous['missing_dechow']
                                 if k!='DOCUMENTED_ISSUANCE']
    stock['task9_financial_evidence']=data
    s6.setdefault('evidence',{})['task9_verified_issuance_source']=data
    return report


def attach_task9_forensic_context(report, receipt_path, filing_cache,
                                  source_v3_report, frozen_s13_contract):
    """Attach 27 contextual findings with source replay, NOT an S13 judgment."""
    from scripts.task9_forensic_review import review_private
    receipt_path=Path(receipt_path)
    if (receipt_path.name not in ('review_v1.json','review_v2.json')
            or receipt_path.parent.name!='task9_forensic'
            or not receipt_path.is_file() or receipt_path.is_symlink()):
        raise ValueError('Only isolated Task9 S13 source review allowed')
    seal=Path(str(receipt_path)+'.sha256')
    if not seal.is_file() or seal.read_text(encoding='ascii').strip()!=digest(receipt_path):
        raise ValueError('TASK9_FORENSIC_REVIEW_SEAL_CHANGED')
    expected=json.loads(receipt_path.read_text(encoding='utf8'))
    if (expected.get('status')!='REVIEW_REQUIRED' or expected.get('S13') is not None
        or expected.get('S14') is not None or expected.get('serious_flag_count') is not None
        or expected.get('independent_serious_flags') is not None
        or expected.get('human_review_packet',{}).get('signed_risk_decisions') is not None):
        raise ValueError('Task9 contextual findings cannot promote unreviewed S13')
    fresh=review_private(Path(filing_cache),Path(source_v3_report),
                         Path(frozen_s13_contract),as_of=expected['as_of'])
    if json.loads(json.dumps(fresh,ensure_ascii=False,allow_nan=False))!=expected:
        raise ValueError('TASK9_CONTEXTUAL_S13_REPLAY_MISMATCH')
    if not report.get('stocks') or report['stocks'][0]['ticker']!='INOD':
        raise ValueError('Missing INOD five-stock research report')
    stock=report['stocks'][0]
    s13=next((x for x in stock['models'] if x['model']=='S13'),None)
    if not s13 or s13['score'] is not None:
        raise ValueError('Cannot replace an accepted S13 score')
    counts={k:r['source_verified_findings'] for k,r in expected['blocks'].items()}
    total=sum(counts.values())
    packet={
        'status':'SOURCE_CONTEXT_VERIFIED_RUBRIC_REVIEW_REQUIRED',
        'filing_bodies_verified':expected['filing_bodies_verified'],
        'context_block_count':sum(v>0 for v in counts.values()),
        'reviewed_numeric_risk_block_count':0,
        'source_findings_count':total,'source_findings_per_block':counts,
        'source_review_sha256':digest(receipt_path),
        'serious_flag_count':None,'S13':None,
        'human_review_required':expected['human_review_packet'],
        'contextual_findings':{k:r['findings'] for k,r in expected['blocks'].items()},
        'canonical_accepted':False,
    }
    stock['task9_forensic_context']=packet
    s13.setdefault('evidence',{})['task9_context_review']=packet
    s13['status']='REVIEW_REQUIRED'
    return report


def attach_task9_jones_real_score(report, receipt_path, sec_cache):
    """Admit independently replayed official FY2025 S11=0 as REAL Research.

    Zero is an actual full model score, not a missing value. Mandatory six-leg
    S14 frozen aggregator remains N/A at 3/6: S6/B_Q/S13 are still unscored.
    """
    from app.task9_jones_acceptance import verify_jones_task9_receipt
    from app.recovered_quality import _result
    verified=verify_jones_task9_receipt(Path(receipt_path),cache=Path(sec_cache))
    if verified['score_status']!='REAL_SCORE_ACCEPTED_RESEARCH':
        raise ValueError('Only independent real Jones research accepted')
    if (len(report.get('stocks',[]))!=5
        or report['stocks'][0]['ticker']!='INOD'
        or report.get('canonical_securities')!=0 or report.get('canonical_dates')!=0):
        raise ValueError('Task9 source must attach only to five-stock Research staging')
    stock=report['stocks'][0]
    model=next((m for m in stock['models'] if m['model']=='S11'),None)
    frozen_s14=next((m for m in stock['models'] if m['model']=='S14'),None)
    if not model or model['score'] is not None or not frozen_s14 or frozen_s14['score'] is not None:
        raise ValueError('Existing Jones/S14 score must not be overwritten')
    q=stock['quality']
    if any(q[k]['score'] is not None for k in ('B_Q','S6','S11','S13')):
        raise ValueError('Inconsistent six-leg S14 evidence')
    if any(q[k]['score'] is None for k in ('S7','S12')):
        raise ValueError('Cannot advance Jones coverage with invalid prior legs')
    at=datetime.fromisoformat(stock['as_of'])
    scored=_result('S11',at,score=verified['score'],period='2025-12-31',
                   missing=[],components=verified['components'],
                   status='VERIFIED_DONE')
    scored['evidence']['independently_replayed_official_sec']=verified
    evidence_payload={'model':'S11','as_of':at.isoformat(),'score':scored['score'],
                      'version':scored['version'],'evidence':scored['evidence'],
                      'components':scored['components']}
    scored['evidence_hash']=sha256(json.dumps(evidence_payload,sort_keys=True).encode()).hexdigest()
    q['S11']=scored
    model.update(score=verified['score'],status='REAL_SCORE_ACCEPTED_RESEARCH',
                 version=scored['version'],evidence=scored['evidence'],
                 missing=[],coverage_pct=100.0,present=8,required=8,
                 research_as_of=verified['as_of'],
                 historical_pit_accepted=False,canonical_accepted=False)
    legs={k:r['score'] for k,r in q.items()}
    s14_score,s14_components=s14(legs)
    if s14_score is not None or sum(x is not None for x in legs.values())!=3:
        raise ValueError('Frozen S14 six-leg completeness violated')
    frozen_s14.update(score=None,status='DATA_MISSING',present=3,coverage_pct=50.0,
                       missing=[k for k,x in legs.items() if x is None],
                       evidence={'engine_executed':True,'legs':q,'components':s14_components})
    stock['task9_jones_research']=verified
    stock['full_model_count']=sum(m['score'] is not None for m in stock['models'])
    report['full_model_count']=sum(x['full_model_count'] for x in report['stocks'])
    report['full_score_securities']=sum(x['full_model_count']>0 for x in report['stocks'])
    if stock['full_model_count']!=3 or report['full_model_count']!=10:
        raise ValueError('Incomplete Jones score count recomputation')
    old_audit=stock.get('sec_jones_v3')
    if old_audit is not None:
        old_audit['status']='SUPERSEDED_BY_TASK9_SEC_SIC_AND_20_PEER_ACCEPTANCE'
        old_audit['replaced_by_receipt_sha256']=verified['source_file_sha256']
    return report


def save_report(report,path):
    path=Path(path)
    if path.exists() or path.is_symlink() or "scoring_completion" not in {p.casefold() for p in path.resolve().parts}:
        raise ValueError("New isolated scoring_completion output required")
    seal=Path(str(path)+".sha256")
    if seal.exists():raise ValueError("Existing report seal")
    path.parent.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)
    with path.open("x",encoding="utf-8") as f:
        f.write(payload)
    with seal.open("x",encoding="ascii") as f:
        f.write(digest(path))


def load_report(path, source, phase28):
    path=Path(path)
    if not path.is_file() or path.is_symlink(): raise ValueError("MISSING_DATA")
    if Path(str(path)+".sha256").read_text(encoding="ascii").strip()!=digest(path):
        raise ValueError("REPORT_HASH_CHANGED")
    report=json.loads(path.read_text(encoding="utf-8"))
    if report.get("contract_sha256")!=SOURCE_SHA256 or report.get("interpolation_sha256")!=INTERPOLATION_SHA256:
        raise ValueError("Contract binding mismatch")
    if report.get("schema")!=SCHEMA: raise ValueError("Unknown report schema")
    if report.get("source_sha256")!={"phase27":digest(source),"phase28":digest(phase28)}:
        raise ValueError("SOURCE_HASH_CHANGED")
    if any(report.get(k)!=0 for k in ("canonical_securities","canonical_dates")):
        raise ValueError("Unproven score promotion")
    if [s["ticker"] for s in report["stocks"]]!=list(TICKERS): raise ValueError("Invalid cohort")
    if report.get("WF9")!="BLOCKED" or report.get("LearningV3")!="NOT_TRAINED":
        raise ValueError("Canonical status promotion")
    for s in report["stocks"]:
        if s.get("scope")!="CURRENT_RESEARCH_ONLY" or s.get("s16_accepted")!=0:
            raise ValueError("Research scope changed")
        for q in s["quality"].values():
            if q.get("canonical_accepted") is not False or q.get("scope")!="RESEARCH_ONLY_NOT_CANONICAL_PIT":
                raise ValueError("Quality scope changed")
        if len({m["model"] for m in s["models"]})!=20 or len(s["models"])!=20:
            raise ValueError("Invalid model inventory")
        for m in s["models"]:
            if m["score"] is not None:
                if m["model"]=='S11':
                    packet=s.get('task9_jones_research')
                    q11=s['quality']['S11']
                    if (s['ticker']!='INOD' or not packet
                        or packet.get('canonical_accepted') is not False
                        or packet.get('historical_pit_accepted') is not False
                        or m['score']!=packet.get('score')
                        or q11['score']!=m['score']
                        or m['status']!='REAL_SCORE_ACCEPTED_RESEARCH'
                        or m.get('research_as_of')!=packet.get('as_of')):
                        raise ValueError('Jones Research-only evidence invalid')
                    if (q11['evidence'].get('independently_replayed_official_sec')!=packet
                        or m['evidence']!=q11['evidence']
                        or q11['evidence_hash']!=sha256(json.dumps({
                            'model':'S11','as_of':q11['as_of'],
                            'score':q11['score'],'version':q11['version'],
                            'evidence':q11['evidence'],
                            'components':q11['components']},sort_keys=True).encode()).hexdigest()):
                        raise ValueError('Jones research source hash or model input changed')
                    independently=__import__('app.task9_jones_acceptance',
                        fromlist=['verify_jones_task9_receipt']).verify_jones_task9_receipt(
                            Path(packet['private_receipt_path']),
                            cache=Path(packet['cache_path']))
                    if independently!=packet:
                        raise ValueError('Jones independent SEC peer replay changed')
                    continue
                if m["model"] not in ("S7","S12"):
                    raise ValueError("Unproven stock score promotion")
                q=s["quality"][m["model"]]
                recomputed=compute_quality(q["evidence"]["inputs"],datetime.fromisoformat(q["as_of"]))[m["model"]]
                if recomputed["score"]!=m["score"] or q["score"]!=m["score"] or recomputed["evidence_hash"]!=q["evidence_hash"]:
                    raise ValueError("Quality reference mismatch")
        if s["full_model_count"]!=sum(m["score"] is not None for m in s["models"]):
            raise ValueError("Score count mismatch")
        if s.get('task9_jones_research'):
            expected_present=sum(s['quality'][k]['score'] is not None
                                 for k in ('B_Q','S6','S7','S11','S12','S13'))
            model14=next(m for m in s['models'] if m['model']=='S14')
            if (expected_present!=3 or model14['present']!=expected_present
                or model14['score'] is not None or
                any(s['quality'][k]['score'] is not None for k in ('B_Q','S6','S13'))):
                raise ValueError('Frozen S14 completeness must remain at 3/6')
    if report["full_model_count"]!=sum(s["full_model_count"] for s in report["stocks"]):
        raise ValueError("Score count mismatch")
    if report["full_score_securities"]!=sum(s["full_model_count"]>0 for s in report["stocks"]):
        raise ValueError("Stock count mismatch")
    return report
