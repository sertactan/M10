"""Fail-closed source inventory for original S1/S2/S3 acceptance."""
from __future__ import annotations

from hashlib import sha256
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3

from app.scoring_v9_s8_s10 import FROZEN_SOURCE_SHA256


DISCOVERY = re.compile(r"^(\d{1,2})\.\s+(.+?)\s*$", re.M)
CONTROL = re.compile(r"^(\d{2})\.\s+(.+?)\s*$", re.M)
SCORE_NAMES = ("S1", "S2", "S3")


def original_inventory(raw: bytes) -> dict:
    if sha256(raw).hexdigest() != FROZEN_SOURCE_SHA256:
        raise ValueError("frozen original source SHA mismatch")
    source = raw.decode("utf-8")
    first = source.split("# 1. 48 TEMEL", 1)[1].split("# 2. 48 DISCOVERY", 1)[0]
    controls = source.split("# 4. FAKTÖR 49", 1)[1].split("## 4.1", 1)[0]
    discovery = {int(i): name.strip() for i, name in DISCOVERY.findall(first)}
    control = {int(i): name.strip() for i, name in CONTROL.findall(controls)}
    if set(discovery) != set(range(1,49)) or set(control) != set(range(49,61)):
        raise ValueError("frozen 48/12 source inventory incomplete")
    return {"discovery": discovery, "control": control,
            "contract_sha256": sha256(raw).hexdigest(),
            "f52_f53_numeric_normalization_in_original": False}


def _verified_json(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    seal_path = path.with_name(path.name + ".sha256")
    if seal_path.read_text(encoding="ascii").strip() != sha256(raw).hexdigest():
        raise ValueError(f"receipt SHA mismatch: {path.name}")
    return json.loads(raw), sha256(raw).hexdigest()


def _offline_counts(db_path: Path) -> dict:
    if not db_path.is_file() or db_path.is_symlink():
        raise ValueError("offline SQLite source missing or symlinked")
    # sqlite3's connection context manager commits or rolls back; it does not
    # close the handle. Windows keeps a temporary DB locked until close().
    with closing(sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {"s153_historical_control_observations", "canonical_model_features"}
        if not required <= names:
            raise ValueError("historical/canonical tables missing")
        cohort_count = db.execute("SELECT COUNT(*) FROM s153_historical_control_observations").fetchone()[0]
        keys = [r[0] for r in db.execute("SELECT DISTINCT feature_key FROM canonical_model_features")]
        factor_keys = sorted(k for k in keys if re.fullmatch(r"D(?:0[1-9]|[1-3][0-9]|4[0-8])", k)
                             or re.fullmatch(r"F(?:49|5[0-9]|60)(?:_.*)?", k))
        all_count = db.execute("SELECT COUNT(*) FROM canonical_model_features").fetchone()[0]
        return {"historical_observations": cohort_count,
                "canonical_feature_rows": all_count,
                "canonical_feature_keys": sorted(keys),
                "canonical_D_F_keys": factor_keys,
                "db_bytes": db_path.stat().st_size,
                "read_mode": "SQLITE_MODE_RO_QUERY_ONLY"}


def build_gate_receipt(*, contract: Path, v12_report: Path,
                       v13_raw_factors: Path, offline_db: Path,
                       v13_sec_binding: Path | None = None) -> dict:
    inventory = original_inventory(contract.read_bytes())
    report, report_hash = _verified_json(v12_report)
    factors, factors_hash = _verified_json(v13_raw_factors)
    if report.get("contract_sha256") != inventory["contract_sha256"]:
        raise ValueError("V12 report frozen contract mismatch")
    if factors.get("frozen_contract_sha256") != inventory["contract_sha256"]:
        raise ValueError("V13 raw factor frozen contract mismatch")
    if factors.get("normalized_quality_scores") != {"F52_RPS": None, "F53_FPS": None}:
        raise ValueError("F52/F53 normalized score unexpectedly promoted")
    storage = _offline_counts(offline_db)
    stocks = []
    for stock in report["stocks"]:
        chain = stock["control_chain"]
        models = {m["model"]: m for m in stock["models"] if m["model"] in SCORE_NAMES}
        if set(models) != set(SCORE_NAMES):
            raise ValueError("missing S1/S2/S3 original model receipts")
        present_discovery = int(chain["discovery_inputs_present"])
        present_control = int(chain["control_inputs_present"])
        if present_discovery > 48 or present_control > 12:
            raise ValueError("factor coverage out of bounds")
        missing = {
            "discovery_count": 48-present_discovery,
            "control_count": 12-present_control,
            "historical_H": chain.get("historical_h") is None,
            "N61": chain.get("n61") is None,
            "FPR": chain.get("false_positive_risk") is None,
            "PIT_factor_rows": not storage["canonical_D_F_keys"],
        }
        if any(models[name].get("score") is not None for name in SCORE_NAMES):
            raise ValueError("unaccepted full S1/S2/S3 score in input report")
        stocks.append({"ticker": stock["ticker"], "as_of": stock["as_of"],
                       "present_discovery": present_discovery,
                       "present_control": present_control,
                       "missing": missing,
                       "S1": None, "S2": None, "S3": None})
    sec_binding = None
    sec_binding_sha = None
    if v13_sec_binding is not None:
        binding, sec_binding_sha = _verified_json(v13_sec_binding)
        rows = binding.get("evidence") or []
        accessions = {row.get("accession") for row in rows}
        legs = {row.get("leg") for row in rows}
        expected_legs = {"D01_REVENUE_GROWTH_1Y_LEG", "D02_EPS_GROWTH_1Y_LEG",
                         "D03_REVENUE_ACCELERATION_LEG", "F54_DIL_RESEARCH_LEG"}
        if (binding.get("ticker") != "INOD" or binding.get("report_sha256") != report_hash
                or binding.get("submissions_sha256") != factors.get("submissions_sha256")
                or len(rows) != 9 or binding.get("evidence_rows_bound") != 9
                or legs != expected_legs or len(accessions) != 4
                or binding.get("partial_legs_bound") != 4
                or binding.get("canonical_pit_accepted") is not False
                or binding.get("s1_s2_s3_complete_scores") != 0
                or not all(re.fullmatch(r"[0-9a-f]{64}", row.get("fact_hash") or "")
                           and row.get("form") in {"10-K", "10-Q"}
                           and row.get("accepted_at") for row in rows)):
            raise ValueError("V13 original SEC partial-leg binding invalid")
        sec_binding = {"ticker": "INOD", "source_rows": len(rows),
                       "partial_legs": sorted(legs), "distinct_accessions": len(accessions),
                       "submissions_sha256": binding["submissions_sha256"],
                       "canonical_pit_accepted": False}
    result = {"schema": "M10_V14_S1_S3_GATE_INVENTORY_V2" if sec_binding else "M10_V14_S1_S3_GATE_INVENTORY_V1",
            "frozen_contract": inventory, "v12_report_sha256": report_hash,
            "v13_f52_f53_sha256": factors_hash,
            "v13_F52_F53_raw_present": sorted(factors["raw_factor_formulas_verified"]),
            "v13_F52_F53_quality_scores": factors["normalized_quality_scores"],
            "offline_storage": storage, "stocks": stocks,
            "new_complete_scores": 0, "task11": "PARTIAL"}
    if sec_binding is not None:
        result["v13_sec_binding_sha256"] = sec_binding_sha
        result["inod_original_sec_binding"] = sec_binding
    return result
