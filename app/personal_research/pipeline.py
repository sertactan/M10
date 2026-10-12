"""Offline five-issuer research pipeline; only sidecar persistence."""
from __future__ import annotations

import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .contracts import digest
from .read_only_adapter import imported_legacy_diagnostics, load_sealed_json
from .s6_assessed import assess_s6
from .source_extractor import load_evidence_packet, verify_source_rows
from .quality_aggregator import assess_personal_s14

TARGETS = ("INOD", "CRMD", "ETON", "PENG", "TMDX")
CIKS = {"INOD": "903651", "CRMD": "1410098", "ETON": "1710340",
        "PENG": "1616533", "TMDX": "1756262"}
MODEL_NAMES = ("S6", "B_Q", "S13", "PERSONAL_S14_SCENARIO")


def _read_baseline(root: Path, ticker: str) -> tuple[dict, dict]:
    path = root / ".master_tasks_v12_private/comparison/five_stock_v2.json"
    try:
        report = load_sealed_json(path)
    except (OSError, ValueError, IndexError, json.JSONDecodeError):
        return {}, {"status": "BASELINE_RECEIPT_UNAVAILABLE"}
    if report.get("full_research_scores") != 17:
        raise ValueError("Original 17-score research baseline changed")
    if report.get("s16_e_production_enabled") is not False:
        raise ValueError("Unexpected S16-E activation in source baseline")
    if report.get("canonical_pit_features") != 0:
        raise ValueError("Unexpected PIT feature baseline change")
    stock = next((s for s in report["stocks"] if s["ticker"] == ticker), None)
    if stock is None:
        raise ValueError("Issuer missing from sealed baseline")
    return stock, {"status": "SEALED_ORIGINAL_READ_ONLY", "score_count": 17,
                   "s16_pit": 0, "s16_e": False, "source_sha256": digest(report)}


def _s6_periods(rows, periods=None):
    if periods:
        return periods
    ends = sorted({r.get("period_end") for r in rows if r.get("period_end")})
    names = set(__import__("app.recovered_dechow", fromlist=["REQUIRED"]).REQUIRED)
    collected = []
    for end in ends:
        found = [r for r in rows if r.get("period_end") == end
                 and r.get("metric") in names]
        if not found:
            continue
        starts = {r.get("period_start") for r in found if r.get("period_start")}
        if len(starts) != 1:
            continue
        facts = {}
        for row in found:
            name = row["metric"]
            if name in facts:
                facts.pop(name, None)
                continue
            facts[name] = {
                "value": row["value"], "period_end": end,
                "source": "SEC_EDGAR", "source_ref": row["source_ref"],
                "accession": row["accession"],
                "available_at": row.get("captured_at"),
                "evidence_hash": row["source_sha256"],
            }
        collected.append({"start": next(iter(starts)), "end": end, "facts": facts})
    return collected[-3:]


def analyze(ticker: str, *, evidence_root: str | Path, packet_path=None,
            fiscal_period: str | None = None, at: datetime | None = None) -> dict:
    """Analyze offline research inputs without touching original acceptance."""
    ticker = ticker.upper()
    if ticker not in TARGETS:
        raise ValueError("Only target issuer set enabled in V1: " + ", ".join(TARGETS))
    at = at or datetime.now(timezone.utc)
    if at.tzinfo is None:
        raise ValueError("as-of must be timezone-aware")
    root = Path(evidence_root)
    stock, baseline = _read_baseline(root, ticker)
    legacy = imported_legacy_diagnostics(ticker, root)
    evidence_fy = (legacy.get("B_Q", {}).get("fiscal_end")
                   or stock.get("financial_period") or "2025-12-31")
    packet = load_evidence_packet(packet_path) if packet_path else {
        "ticker": ticker, "cik": CIKS[ticker], "period_end": fiscal_period or evidence_fy,
        "rows": [], "filings": [], "source_findings": [], "ai_reviews": [],
    }
    if packet["ticker"] != ticker or str(packet["cik"]).lstrip("0") != CIKS[ticker]:
        raise ValueError("Packet issuer/CIK mismatch")
    validated_rows, rejected = verify_source_rows(packet)
    # Recovered calculators accept a much smaller schema; only fully checked
    # source-exact inputs enter their numerical computations.
    rows = [
        {**row, "source": "SEC_EDGAR", "evidence_hash": row["source_sha256"],
         "available_at": row["captured_at"],
         "form_type": row["form_type"], "ticker": ticker}
        for row in validated_rows if row["evidence_class"] == "SOURCE_EXACT"
    ]
    fy = packet.get("period_end", evidence_fy)
    if fiscal_period and fy != fiscal_period:
        raise ValueError("Requested fiscal period does not match the source packet")
    original = stock.get("models", {})
    status = lambda name: original.get(name, {}).get("acceptance", "N/A")
    s6 = assess_s6(_s6_periods(rows), at,
                    original_status=status("S6"),
                    source_rsst=legacy.get("S6", {}).get("RSST_candidate"))
    s6["components"]["legacy"] = legacy.get("S6", {})
    from .beneish_assessed import analyze_beneish
    default_start = ("2023-08-26" if ticker == "PENG" and fy == "2024-08-30"
                     else "2024-08-31" if ticker == "PENG" and fy == "2025-08-29"
                     else f"{int(fy[:4])}-01-01")
    bq = analyze_beneish(rows, fy, packet.get("period_start", default_start))
    bq["original_status"] = status("B_Q")
    bq["components"] = {**bq.get("components", {}),
                        "legacy": legacy.get("B_Q", {})}
    # A source-sealed and independently re-computed partial ratio may be
    # displayed with its provenance. The full B_Q score stays null.
    dep_partial = legacy.get("B_Q", {}).get("verified_partial_DEPI", {})
    if dep_partial and fy == dep_partial.get("fiscal_end"):
        if bq.get("ratios", {}).get("DEPI") is None:
            bq.setdefault("ratios", {})["DEPI"] = dep_partial["ratio"]
            bq.setdefault("risks", {})["DEPI"] = dep_partial["normalized_risk"]
            bq.setdefault("results", {})["DEPI"] = {
                "ratio": dep_partial["ratio"],
                "risk": dep_partial["normalized_risk"],
                "status": "SEALED_RESEARCH_COMPONENT_ONLY",
                "evidence": dep_partial,
                "whole_model_accepted": False,
            }
    from .s13_assessed import assess_s13
    s13 = assess_s13({
        **packet, "as_of": at.isoformat(),
        "source_packet": packet.get(
            "source_packet", legacy.get("S13", {}).get("source_packet", {})),
    })
    s13["original_status"] = status("S13")
    s13["components"]["legacy_unsigned_form"] = legacy.get("S13", {})
    models = {"S6": s6, "B_Q": bq, "S13": s13}
    anchored = fy == evidence_fy
    s14 = assess_personal_s14(models,
        s7=original.get("S7", {}).get("score") if anchored else None,
        s11=original.get("S11", {}).get("score") if anchored else None,
        s12=original.get("S12", {}).get("score") if anchored else None)
    s14["original_status"] = status("S14")
    models["PERSONAL_S14_SCENARIO"] = s14
    for name, value in models.items():
        value["model"] = name
        value["canonical_accepted"] = False
        value["historical_pit_accepted"] = False
        value["scope"] = "PERSONAL_AI_ASSESSED_RESEARCH_ONLY"
        value["receipt_sha256"] = digest({k: v for k, v in value.items()
                                           if k != "receipt_sha256"})
    result = {
        "run_id": uuid.uuid4().hex, "ticker": ticker, "cik": CIKS[ticker],
        "period_end": fy, "created_at": at.isoformat(),
        "company": stock.get("ticker", ticker), "price": stock.get("price"),
        "price_time": stock.get("price_time"),
        "baseline": baseline, "original_models": original,
        "models": models, "input_count": len(rows), "rows": rows,
        "rejected_sources": rejected, "legacy_diagnostics": legacy,
        "llm_provider": "OFFLINE_MANUAL_STRUCTURED",
        "code_commit": _code_commit(),
        "prompt_version": "PERSONAL_RESEARCH_V1",
        "scenario_version": "PERSONAL_RESEARCH_V1",
        "user_review_status": "NOT_EXPERT_REVIEWED",
        "canonical_accepted": False,
        "historical_pit_accepted": False,
    }
    result["receipt_sha256"] = digest(result)
    return result


def _code_commit():
    """Store an actual repo revision when Git is available, else explain null."""
    try:
        code_root = Path(__file__).resolve().parents[2]
        process = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=code_root,
            check=True, capture_output=True, text=True, timeout=3)
        return process.stdout.strip()
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
