"""Read-only acceptance audit for frozen S1-S3 and S15.3 model receipts.

The input is an existing real-source scoring_completion report. This module
never reconstructs missing factors, writes a model score, or reads live DBs.
"""
from __future__ import annotations

from hashlib import sha256
from datetime import datetime
import json
from pathlib import Path
import re

from app.recovered_quality import SOURCE_SHA256
from core.models.s153_v141 import V141_FORMULA_VERSION
from core.models.s153_v14_recovered import RECOVERED_FORMULA_VERSION, V13_REQUIRED_FEATURES
from core.models.s153_v12 import S153V12Model


NAMES = ("S1", "S2", "S3", "S15.3 V1.2", "S15.3 V1.4", "S15.3 V1.4.1")
VERSIONS = {
    "S1": "S1_FROZEN", "S2": "S2_FROZEN", "S3": "S3_FROZEN",
    "S15.3 V1.2": S153V12Model.canonical_formula_version,
    "S15.3 V1.4": RECOVERED_FORMULA_VERSION,
    "S15.3 V1.4.1": V141_FORMULA_VERSION,
}
S1_COMPONENTS = {
    "S1": ("DNA60", "ROUTER_R", "H", "N61"),
    "S2": ("DNA60", "G6", "H", "FPR"),
    "S3": ("DNA60", "ROUTER_R", "H"),
}
S1_FORMULAS = {
    "S1": lambda c: max(0.0, min(100.0, .55*c["DNA60"]+.25*c["ROUTER_R"]+.20*c["H"]-.15*c["N61"])),
    "S2": lambda c: max(0.0, min(100.0, .50*c["DNA60"]+.30*c["G6"]+.20*c["H"]-.20*c["FPR"])),
    "S3": lambda c: max(0.0, min(100.0, .55*c["DNA60"]+.25*c["ROUTER_R"]+.20*c["H"])),
}

PARTIAL_LEGS = ("D01_REVENUE_GROWTH_1Y_LEG", "D02_EPS_GROWTH_1Y_LEG",
                "D03_REVENUE_ACCELERATION_LEG", "F54_DIL_RESEARCH_LEG")


def _partial_source_rows(features: dict) -> dict:
    """Check the dated SEC research legs actually carried by a report."""
    checked = {}
    for key in PARTIAL_LEGS:
        row = features.get(key)
        if row is None:
            continue
        try:
            at = datetime.fromisoformat(row["as_of"].replace("Z", "+00:00"))
            available = datetime.fromisoformat(row["available_at"].replace("Z", "+00:00"))
            timing = at.tzinfo is not None and available.tzinfo is not None and available <= at
        except (ValueError, KeyError, TypeError):
            timing = False
        value = row.get("value")
        checked[key] = {
            "dated": timing,
            "normalized_range": value is not None and 0 <= float(value) <= 100,
            "source_bound": bool(row.get("source_ref")) and bool(re.fullmatch(r"[0-9a-f]{64}", row.get("evidence_hash") or "")),
            "quality_status": row.get("quality_status"),
        }
    return checked


def _verify_v14_bundle() -> dict[str, str]:
    bundle = Path(__file__).resolve().parents[1] / "specs" / "s153_v14"
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    verified = {}
    for artifact in manifest["artifacts"]:
        path = bundle / artifact["path"]
        if path.resolve().parent != bundle.resolve():
            raise ValueError("V1.4 manifest path escapes bundle")
        digest = sha256(path.read_bytes()).hexdigest()
        if digest != artifact["sha256"]:
            raise ValueError(f"V1.4 specification SHA mismatch: {artifact['name']}")
        verified[artifact["name"]] = digest
    if len(verified) != 5:
        raise ValueError("V1.4 specification bundle incomplete")
    return verified


def audit_report(path: Path) -> dict:
    raw = path.read_bytes()
    report = json.loads(raw)
    if report.get("contract_sha256") != SOURCE_SHA256:
        raise ValueError("frozen S1-S14 source SHA mismatch")
    if not report.get("source_sha256") or not report.get("stocks"):
        raise ValueError("source receipt or stock rows missing")
    v14_artifacts = _verify_v14_bundle()
    results = []
    for stock in report["stocks"]:
        ticker = stock["ticker"]
        models = {m["model"]: m for m in stock["models"] if m["model"] in NAMES}
        if set(models) != set(NAMES):
            raise ValueError(f"{ticker}: expected six frozen model receipts")
        chain = stock.get("control_chain") or {}
        v12 = models["S15.3 V1.2"]["evidence"]["result"]
        components = v12.get("components") or {}
        row = {"ticker": ticker, "as_of": stock["as_of"],
               "partial_source_legs": _partial_source_rows(stock.get("features") or {}),
               "models": {}}
        for name in NAMES:
            model = models[name]
            if model.get("version") != VERSIONS[name]:
                raise ValueError(f"{ticker} {name}: version mismatch")
            old_score = model.get("score")
            gates = {}
            if name in S1_COMPONENTS:
                count48 = chain.get("discovery_inputs_present", 0)
                count12 = chain.get("control_inputs_present", 0)
                gates = {
                    "Core48_exact_inputs": count48 == 48,
                    "Control12_exact_inputs": count12 == 12,
                    "Historical_H": components.get("H") is not None,
                    "required_components": all(components.get(k) is not None for k in S1_COMPONENTS[name]),
                    "PIT_feature_provenance": False,  # aggregate report has no row-level provenance
                    "independent_reference": False,
                }
                if gates["required_components"]:
                    reference = S1_FORMULAS[name](components)
                    gates["independent_reference"] = old_score is not None and abs(reference-old_score) < 1e-9
            elif name == "S15.3 V1.2":
                gates = {
                    "S15.2": components.get("S15.2") is not None,
                    "M10_at_least_5_of_7": components.get("M10") is not None and "M10>=5/7" not in model["missing"],
                    "T10_at_least_5_of_7": components.get("T10") is not None and "T10>=5/7" not in model["missing"],
                    "essential_route_at_least_70": (components.get("ROUTE_ESSENTIAL_COVERAGE") or 0) >= 70,
                    "route_gate": v12.get("route_gate") is True,
                    "source_fit_confidence": v12.get("confidence") is not None,
                    "PIT_feature_provenance": False,
                }
            elif name == "S15.3 V1.4":
                normalized = set(model["evidence"].get("normalized_input_keys") or ())
                gates = {
                    "V1.2_ready": v12.get("score") is not None,
                    "dual_magnitude_inputs": all(k in normalized for k in V13_REQUIRED_FEATURES),
                    "model_fit": components.get("CONFIDENCE") is not None,
                    "PIT_feature_provenance": False,
                }
            else:
                gates = {
                    "V1.2_ready": v12.get("score") is not None,
                    "own_version_receipt": model["version"] == V141_FORMULA_VERSION,
                    "original_route_scenario_evidence": False,
                    "PIT_feature_provenance": False,
                }
            accepted = bool(old_score is not None and all(gates.values()) and not model.get("missing"))
            row["models"][name] = {
                "accepted": accepted, "existing_score_present": old_score is not None,
                "gates": gates, "missing_engine": model.get("missing", []),
                "unmet_acceptance": [k for k, passed in gates.items() if not passed],
                "version": model["version"],
            }
        results.append(row)
    return {
        "input_sha256": sha256(raw).hexdigest(), "source_sha256": report["source_sha256"],
        "frozen_s1_s14_sha256": SOURCE_SHA256,
        "v14_specification_sha256": v14_artifacts,
        "stock_count": len(results), "accepted_count": sum(m["accepted"] for r in results for m in r["models"].values()),
        "stocks": results,
    }
