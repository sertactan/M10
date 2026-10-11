"""V8 research-only S9 evidence overlay on the immutable V7 score checkpoint."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import copy
import json
import re

from app.scoring_completion import TICKERS

PRESERVED_SCORES = {
    "INOD": {"S7":100.0,"S11":0.0,"S12":91.528866},
    "TMDX": {"S7":100.0,"S9":700/9,"S12":85.403881},
    "CRMD": {"S7":100.0,"S11":86.015359,"S12":95.682132},
    "PENG": {"S7":100.0,"S9":600/9,"S12":83.512058},
    "ETON": {"S7":100.0,"S9":500/9,"S11":7.860332},
}


def attach_v8_s9_audits(report: dict, audits: dict, receipt_sha: str) -> dict:
    """Attach verified inputs without manufacturing unsupported binary signals."""
    if (report.get("full_model_count") != 15
            or report.get("canonical_securities") != 0
            or report.get("canonical_dates") != 0
            or [s["ticker"] for s in report.get("stocks", [])] != list(TICKERS)
            or set(audits) != {"INOD", "CRMD"}
            or not re.fullmatch(r"[0-9a-f]{64}", receipt_sha)):
        raise ValueError("V8_EXPECTED_V7_15_SCORE_CHECKPOINT")
    updated = copy.deepcopy(report)
    for stock in updated["stocks"]:
        by_model = {m["model"]: m for m in stock["models"]}
        for name, expected in PRESERVED_SCORES[stock["ticker"]].items():
            value = by_model[name]["score"]
            if value is None or abs(value - expected) > 0.0000006:
                raise ValueError("V7_REAL_RESEARCH_SCORE_CHANGED:" + stock["ticker"] + ":" + name)
        if stock["ticker"] not in audits:
            continue
        candidate = audits[stock["ticker"]]
        model = by_model["S9"]
        if (model["score"] is not None or candidate["score"] is not None
                or candidate["status"] != "DATA_MISSING"
                or candidate["scope"] != "CURRENT_RESEARCH_ONLY"
                or candidate["canonical_accepted"] is not False
                or candidate["historical_pit_accepted"] is not False
                or not 0 <= candidate["signals_verified"] <= 8
                or candidate["signals_partial"]["F_DELTA_LEVERAGE"] is not None):
            raise ValueError("S9_V8_UNSUPPORTED_MODEL_PROMOTION")
        if (sum(v is not None for v in candidate["signals_partial"].values())
                != candidate["signals_verified"]
                or any(v not in (None,0,1) for v in candidate["signals_partial"].values())
                or len(candidate["signals_partial"]) != 9
                or not any("LONG_TERM_DEBT" in m for m in candidate["missing"])):
            raise ValueError("S9_V8_SIGNAL_COUNT_OR_DEBT_GATE_INVALID")
        checked = candidate["signals_verified"]
        model.update(status="DATA_MISSING", present=checked, required=9,
                     coverage_pct=100*checked/9, score=None,
                     missing=candidate["missing"],
                     evidence={"v8_sec_fact_audit":candidate,
                               "source_receipt_sha256":receipt_sha,
                               "score_must_remain_null":True})
        stock["v8_s9_audit"] = {"verified_signal_count":checked,
                                 "score":None,"missing":candidate["missing"],
                                 "receipt_sha256":receipt_sha}
    updated["v8"] = {"new_full_research_scores":0,
                     "total_full_research_scores":15,
                     "s9_2025_audits":["INOD","CRMD"],
                     "s16_c_normalized_pit_accepted":0,
                     "s16_e_status":"PENDING_CALIBRATION_AND_EXPLICIT_USER_ACTIVATION",
                     "new_scores_canonical":False}
    if (sum(s["full_model_count"] for s in updated["stocks"]) != 15
            or updated["full_model_count"] != 15):
        raise ValueError("V8_15_SCORE_INVARIANT_FAILED")
    return updated


def read_sealed_audit(path: Path) -> tuple[dict,str]:
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("V8_PRIVATE_RESEARCH_RECEIPT_REQUIRED")
    raw = path.read_bytes()
    digest = sha256(raw).hexdigest()
    seal = Path(str(path)+".sha256")
    if not seal.is_file() or seal.is_symlink() or seal.read_text("ascii").strip() != digest:
        raise ValueError("V8_PRIVATE_RESEARCH_SEAL_MISMATCH")
    return json.loads(raw),digest
