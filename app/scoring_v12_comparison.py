"""Source-replayed five-issuer comparison, preserving Research/PIT separation."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from app.scoring_v9_report import load_v9_report, NEW_REPORT

TICKERS = ("INOD", "TMDX", "CRMD", "PENG", "ETON")
ACCEPTED_MODELS = ("S7", "S9", "S11", "S12")
EXPECTED_COUNTS = {"S7": 5, "S9": 5, "S11": 3, "S12": 4}
MODEL_COLUMNS = ("S6", "S7", "S8", "S9", "S10", "S11", "S12", "B_Q", "S14", "S16-E", "S16-C")


def build_comparison(phase27: Path, phase28: Path) -> dict:
    report = load_v9_report(NEW_REPORT, phase27, phase28)
    if (tuple(s["ticker"] for s in report["stocks"]) != TICKERS
            or report["full_model_count"] != 17
            or report["canonical_securities"] != 0
            or report["canonical_dates"] != 0
            or report["v9"]["s16_c_pit_features"] != 0):
        raise ValueError("V12_ORIGINAL_FIVE_STOCK_BASELINE_CHANGED")
    counts = {model: 0 for model in ACCEPTED_MODELS}
    stocks = []
    for stock in report["stocks"]:
        source_models = {m["model"]: m for m in stock["models"]}
        if len(source_models) != len(stock["models"]) or len(source_models) != 20:
            raise ValueError("DUPLICATE_OR_INCOMPLETE_SOURCE_MODEL_SET")
        all_models = {}
        for name, model in source_models.items():
            score = model.get("score")
            if score is not None and name not in ACCEPTED_MODELS:
                raise ValueError("UNREVIEWED_MODEL_SCORE_PROMOTION:" + name)
            all_models[name] = {
                "score": score,
                "acceptance": "CURRENT_RESEARCH_FULL" if score is not None else "N/A",
                "source_status": model.get("status"),
                "reason": model.get("missing") or [],
            }
        models = {}
        for name in MODEL_COLUMNS:
            if name == "B_Q":
                models[name] = {"score": None, "acceptance": "N/A",
                                "reason": "B_Q original DEPI/LVGI/forensic gates incomplete"}
                continue
            model = source_models[name]
            score = model.get("score")
            if name in ACCEPTED_MODELS:
                if score is not None:
                    counts[name] += 1
                    acceptance = "CURRENT_RESEARCH_FULL"
                else:
                    acceptance = "N/A"
            elif score is not None:
                raise ValueError("UNREVIEWED_MODEL_SCORE_PROMOTION:" + name)
            else:
                acceptance = "N/A"
            models[name] = {"score": score, "acceptance": acceptance,
                            "source_status": model.get("status"),
                            "reason": model.get("missing") or []}
        if stock["ticker"] == "INOD" and models["S11"]["score"] != 0:
            raise ValueError("INOD_TRUE_ZERO_S11_CHANGED")
        if models["S16-E"]["score"] is not None or models["S16-C"]["score"] is not None:
            raise ValueError("ESTIMATED_OR_CANONICAL_PROMOTED")
        stocks.append({"ticker": stock["ticker"],
                       "price": stock["price"], "currency": stock["currency"],
                       "price_time": stock["price_time"], "price_label": "DATED_CACHE_NOT_LIVE",
                       "financial_period": stock["financial_period"],
                       "models": models, "all_source_models": all_models})
    if counts != EXPECTED_COUNTS:
        raise ValueError("ORIGINAL_SEVENTEEN_MODEL_DISTRIBUTION_CHANGED")
    return {"schema": "M10_V12_FIVE_STOCK_COMPARISON_V2",
            "source_report_sha256": sha256(NEW_REPORT.read_bytes()).hexdigest(),
            "source_report": str(NEW_REPORT), "scope": "CURRENT_RESEARCH_ONLY",
            "source_replayed": True, "accepted_model_counts": counts,
            "full_research_scores": sum(counts.values()),
            "canonical_pit_features": 0, "s16_e_production_enabled": False,
            "stocks": stocks}


def canonical_bytes(report: dict) -> bytes:
    return (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")
