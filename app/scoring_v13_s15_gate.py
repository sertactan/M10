"""Source-bound S15.3 readiness diagnostics; no synthetic destination or score."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, localcontext
from hashlib import sha256
import json
import re

from core.models.s153_v14_recovered import V13_REQUIRED_FEATURES
from core.routes.s153_v12 import essential_legs, essential_coverage

HEX = re.compile(r"^[0-9a-f]{64}$")
MODELS = ("S15.3 V1.2", "S15.3 V1.4", "S15.3 V1.4.1")


def market_cap_candidate(stock: dict) -> dict:
    """Independent dated price × shares research calculation, not SupportedMC."""
    row = stock.get("features", {}).get("SHARES_OUTSTANDING_DATED")
    price = stock.get("price")
    if not isinstance(row, dict) or price is None:
        return {"value_usd": None, "status": "SOURCE_MISSING"}
    if not HEX.fullmatch(row.get("evidence_hash", "")) or row.get("unit") not in ("shares", "SHARES"):
        raise ValueError("SHARE_EVIDENCE_OR_UNIT_INVALID")
    if row.get("quality_status") != "RESEARCH_ONLY_ACCEPTED_AT_UNVERIFIED":
        raise ValueError("UNEXPECTED_SHARE_QUALITY_STATUS")
    at = datetime.fromisoformat(stock["as_of"])
    price_at = datetime.fromisoformat(stock["price_time"])
    available = datetime.fromisoformat(row["available_at"])
    if any(x.tzinfo is None for x in (at, price_at, available)) or not available <= price_at <= at:
        raise ValueError("PRICE_SHARE_SOURCE_TIME_INCONSISTENT")
    if datetime.fromisoformat(row["period_end"]).date() > price_at.date():
        raise ValueError("SHARE_PERIOD_AFTER_PRICE")
    with localcontext() as ctx:
        ctx.prec = 50
        p, n = Decimal(str(price)), Decimal(str(row["value"]))
        if p <= 0 or n <= 0 or n != n.to_integral_value():
            raise ValueError("PRICE_OR_SHARES_NOT_POSITIVE")
        candidate = p * n
        existing = stock["features"].get("MARKET_CAP_RESEARCH_DATED_SHARES_USD")
        if existing and existing.get("value") is not None:
            if abs(candidate - Decimal(str(existing["value"]))) > Decimal("0.01"):
                raise ValueError("EXISTING_RESEARCH_MARKET_CAP_DISAGREES")
    return {"value_usd": str(candidate), "price_time": stock["price_time"],
            "shares_period_end": row["period_end"],
            "shares_evidence_hash": row["evidence_hash"],
            "shares_quality_status": row["quality_status"],
            "status": "DATED_RESEARCH_CANDIDATE_ONLY",
            "canonical_pit_accepted": False,
            "destination_supported_mc": None}


def audit_stock(stock: dict) -> dict:
    models = {m["model"]: m for m in stock["models"] if m["model"] in MODELS}
    if set(models) != set(MODELS):
        raise ValueError("THREE_S15_VERSIONS_REQUIRED")
    v12 = models[MODELS[0]]["evidence"]["result"]
    components = v12["components"]
    route = v12["primary_route"]
    if route is None or route not in v12["routes"]:
        raise ValueError("ORIGINAL_PRIMARY_ROUTE_REQUIRED")
    legs = essential_legs(route, components)
    coverage = essential_coverage(route, components)
    if abs(coverage - components["ROUTE_ESSENTIAL_COVERAGE"]) > 1e-10:
        raise ValueError("ORIGINAL_ROUTE_COVERAGE_CHANGED")
    present = sorted(k for k, value in legs.items() if value is not None)
    missing = sorted(k for k, value in legs.items() if value is None)
    # Original threshold is >=70%; with five essential legs this means four.
    needed = max(0, (7 * len(legs) + 9) // 10 - len(present))
    v14 = models[MODELS[1]]
    v141 = models[MODELS[2]]
    normalized = set(v14["evidence"].get("normalized_input_keys", ()))
    required_v14 = sorted(k for k in V13_REQUIRED_FEATURES if k not in normalized)
    if any(m["score"] is not None for m in models.values()):
        raise ValueError("PREVIOUSLY_ACCEPTED_SCORE_REQUIRES_SEPARATE_REVIEW")
    return {
        "ticker": stock["ticker"], "as_of": stock["as_of"],
        "dated_current_market_cap": market_cap_candidate(stock),
        "v12": {"route": route, "essential_coverage_pct": coverage,
                "essential_present": present, "essential_missing": missing,
                "additional_essential_legs_to_70_pct": needed,
                "S15_2_present": components.get("S15.2") is not None,
                "M10_present": components.get("M10") is not None,
                "T10_present": components.get("T10") is not None,
                "confidence_present": v12.get("confidence") is not None,
                "route_gate": v12.get("route_gate") is True,
                "engine_missing": models[MODELS[0]]["missing"],
                "accepted_score": None},
        "v14": {"missing_13_feature_inputs": required_v14,
                "model_fit_present": components.get("CONFIDENCE") is not None,
                "supported_mc_source_bound": False,
                "engine_missing": v14["missing"], "accepted_score": None},
        "v141": {"V12_READY": False, "engine_missing": v141["missing"],
                 "accepted_score": None},
    }


def audit_report(raw: bytes, seal: bytes) -> dict:
    if seal.decode("ascii").strip() != sha256(raw).hexdigest():
        raise ValueError("ORIGINAL_REPORT_SEAL_CHANGED")
    report = json.loads(raw)
    if report.get("contract_sha256") != "53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794":
        raise ValueError("FROZEN_CONTRACT_RECEIPT_CHANGED")
    if len(report.get("stocks", ())) != 5 or len({s["ticker"] for s in report["stocks"]}) != 5:
        raise ValueError("FIVE_ISSUER_SOURCE_REQUIRED")
    rows = [audit_stock(s) for s in report["stocks"]]
    return {"schema": "V13_S15_3_DATED_SOURCE_AND_ROUTE_AUDIT_V1",
            "input_sha256": sha256(raw).hexdigest(),
            "source_sha256": report["source_sha256"],
            "scope": "CURRENT_RESEARCH_NOT_CANONICAL_PIT",
            "stocks": rows, "dated_market_cap_candidates": sum(r["dated_current_market_cap"]["value_usd"] is not None for r in rows),
            "new_accepted_S15_3_scores": 0, "task12": "PARTIAL"}
