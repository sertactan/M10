"""Verified V9-only Research-score overlay; all V8 predecessor receipts replayed.

Retains the original V8 staging snapshot byte-for-byte as an independent
baseline input. Each new score is recovered from original pinned private SEC
sources on every load, never accepted merely from an inline JSON status.
"""
from __future__ import annotations
import copy, json, os, zipfile
from hashlib import sha256
from pathlib import Path
from app.scoring_completion import load_report, save_report, TICKERS
from app.scoring_v9_inod import calculate as calculate_inod
from app.scoring_v8_model_gates import verify_v7_baseline

V8_REPORT=Path("E:/M10/.scoring_v8_private/scoring_completion/v8_source_pinned_report.json")
PRIVATE_ROOT=Path("E:/M10/.scoring_v9_private")
NEW_REPORT=PRIVATE_ROOT/"scoring_completion"/"v9_research_report.json"


def _official_inod_bytes(runtime:Path):
    with zipfile.ZipFile(runtime/"bulk/sec/companyfacts.zip") as z:
        facts=z.read("CIK0000903651.json")
    body=runtime/"scoring_completion"/"v3_filing_bodies"
    return (facts,(runtime/"sec_submissions/CIK0000903651.json").read_bytes(),
            (body/"000110465926020655_inod-20251231x10k.htm").read_bytes(),
            (body/"000141057825000194_inod-20241231x10k.htm").read_bytes())


def _official_crmd_bytes(runtime:Path):
    from app.scoring_v9_crmd import CURRENT_10K_URL,PRIOR_10K_URL
    from scripts.scoring_v8_s9_audit import _cached_response
    with zipfile.ZipFile(runtime/"bulk/sec/companyfacts.zip") as z:
        facts=z.read("CIK0001410098.json")
    submissions=_cached_response(Path("E:/M10/.scoring_v6_private/task9_jones_eton"),
        "https://data.sec.gov/submissions/CIK0001410098.json")
    current=_cached_response(Path("E:/M10/.scoring_v8_private/task9_jones_v8_piotroski"),
        CURRENT_10K_URL)
    prior=_cached_response(PRIVATE_ROOT/"crmd/task9_jones_v9_crmd",PRIOR_10K_URL)
    return (facts,submissions,current,prior)


def _authenticated_receipt(receipt_path:Path, recomputed:dict) -> str:
    raw=receipt_path.read_bytes()
    digest=sha256(raw).hexdigest()
    seal=Path(str(receipt_path)+".sha256")
    if receipt_path.is_symlink() or not seal.is_file() or seal.is_symlink():
        raise ValueError("V9_ORIGINAL_PRIVATE_RECEIPT_AND_SEAL_REQUIRED")
    if seal.read_text(encoding="ascii").strip()!=digest:
        raise ValueError("V9_SOURCE_RECEIPT_SEAL_CHANGED")
    if json.loads(raw)!=recomputed:
        raise ValueError("V9_OFFICIAL_SEC_SOURCE_REPLAY_CHANGED")
    return digest


def attach_accepted_score(report:dict,ticker:str,verified:dict,receipt_sha:str):
    if (report.get("canonical_securities")!=0 or report.get("canonical_dates")!=0
            or ticker not in ("INOD","CRMD")
            or verified.get("ticker")!=ticker or verified.get("model")!="S9"
            or verified.get("score_status")!="REAL_SCORE_ACCEPTED_RESEARCH"
            or verified.get("canonical_accepted") is not False
            or verified.get("historical_pit_accepted") is not False
            or verified.get("verified_signals")!=9
            or len(verified.get("signals",{}))!=9
            or any(type(v) is not int or v not in (0,1) for v in verified["signals"].values())
            or sum(verified["signals"].values())!=verified.get("positive_signal_count")
            or abs(float(verified["score"])-100*sum(verified["signals"].values())/9)>1e-12):
        raise ValueError("V9_FROZEN_S9_ACCEPTANCE_RULES_FAILED")
    stock=next(s for s in report["stocks"] if s["ticker"]==ticker)
    model=next(m for m in stock["models"] if m["model"]=="S9")
    if model["score"] is not None:
        raise ValueError("V9_MUST_NOT_REPLACE_PREVIOUS_SCORE")
    model.update(score=verified["score"],status="REAL_SCORE_ACCEPTED_RESEARCH",
        present=9,required=9,coverage_pct=100.0,missing=[],
        research_as_of="2026-10-11",historical_pit_accepted=False,
        canonical_accepted=False,evidence={"v9_official_sec_source_replay":verified,
                                          "private_receipt_sha256":receipt_sha})
    stock["v9_s9_research"]={"ticker":ticker,"score":verified["score"],
                              "original_source_replayed":True,"receipt_sha256":receipt_sha}
    stock["full_model_count"]=sum(m["score"] is not None for m in stock["models"])


def build_report(base:dict, receipts:dict[str,tuple[dict,str]])->dict:
    verify_v7_baseline(base)
    if (base["full_model_count"]!=15 or [s["ticker"] for s in base["stocks"]]!=list(TICKERS)
            or any(s["ticker"] in ("INOD","CRMD") and next(m for m in s["models"] if m["model"]=="S9")["score"] is not None for s in base["stocks"])):
        raise ValueError("V9_VERIFIED_V8_FIFTEEN_SCORE_BASE_REQUIRED")
    new=copy.deepcopy(base)
    for ticker,(verified,seal) in sorted(receipts.items()):
        attach_accepted_score(new,ticker,verified,seal)
    new["full_model_count"]=sum(s["full_model_count"] for s in new["stocks"])
    new["full_score_securities"]=sum(s["full_model_count"]>0 for s in new["stocks"])
    new["v9"]={"accepted_new_models":{ticker:"S9" for ticker in receipts},
       "new_full_research_scores":len(receipts),"full_research_scores":new["full_model_count"],
       "canonical_pit_securities":0,"canonical_pit_dates":0,
       "s16_c_pit_features":0,"s16_e_status":"PENDING_APPROVAL",
       "as_of":"2026-10-11","scope":"CURRENT_RESEARCH_ONLY"}
    return new


def verified_v9_report(phase27:Path,phase28:Path, *, crmd_inputs=None)->dict:
    base=load_report(V8_REPORT,phase27,phase28)
    rt=Path(os.environ["LOCALAPPDATA"])/"S153ResearchTerminal"/"runtime"
    inod=calculate_inod(*_official_inod_bytes(rt))
    signed={"INOD":(inod,_authenticated_receipt(PRIVATE_ROOT/"inod_s9/report.json",inod))}
    if crmd_inputs is None and (PRIVATE_ROOT/"crmd/report.json").is_file():
        crmd_inputs=_official_crmd_bytes(rt)
    if crmd_inputs is not None:
        from app.scoring_v9_crmd import calculate as calculate_crmd
        crmd=calculate_crmd(*crmd_inputs)
        signed["CRMD"]=(crmd,_authenticated_receipt(PRIVATE_ROOT/"crmd/report.json",crmd))
    return build_report(base,signed)


def create_report(phase27:Path,phase28:Path, *, crmd_inputs=None,
                  output:Path=NEW_REPORT):
    if output.resolve()!=NEW_REPORT.resolve() or output.exists():
        raise ValueError("NEW_PRIVATE_V9_REPORT_OUTPUT_REQUIRED")
    report=verified_v9_report(phase27,phase28,crmd_inputs=crmd_inputs)
    save_report(report,output)
    return report


def load_v9_report(path:Path,phase27:Path,phase28:Path,*,crmd_inputs=None):
    path=Path(path)
    if path.resolve()!=NEW_REPORT.resolve() or not path.is_file() or path.is_symlink():
        raise ValueError("EXACT_V9_PRIVATE_STAGING_REPORT_REQUIRED")
    raw=path.read_bytes(); seal=Path(str(path)+".sha256")
    if not seal.is_file() or seal.read_text("ascii").strip()!=sha256(raw).hexdigest():
        raise ValueError("V9_PRIVATE_STAGING_REPORT_SEAL_CHANGED")
    expected=verified_v9_report(phase27,phase28,crmd_inputs=crmd_inputs)
    actual=json.loads(raw)
    if expected!=actual:
        raise ValueError("V9_CACHED_RESEARCH_REPORT_OFFICIAL_SOURCE_REPLAY_CHANGED")
    return actual
