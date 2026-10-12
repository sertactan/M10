"""Read-only V1.2 source inventory; this module never manufactures scores."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sqlite3


REQUIRED_DB_KEYS = (
    "SUPPORTED_MC_12_R", "SUPPORTED_MC_12_FI", "SUPPORTED_MC_12_D",
    "SUPPORTED_MC_12_B", "PLAUSIBLE_CEILING_MC", "MODEL_FIT",
    "CT", "H10", "HMG10", "XR",
)
MODEL_NAMES = ("S15.3 V1.2", "S15.3 V1.4", "S15.3 V1.4.1")


def original_gate(result: dict) -> dict:
    """Apply the mandatory full-acceptance checks to an original model result."""
    c = result["components"]
    missing = [key for key in ("S15.2", "M10", "T10") if c.get(key) is None]
    if c.get("ROUTE_ESSENTIAL_COVERAGE", 0) < 70:
        missing.append("ROUTE_ESSENTIAL_COVERAGE_70")
    if result.get("route_gate") is not True:
        missing.append("ROUTE_GATE")
    if result.get("confidence") is None:
        missing.append("CONFIDENCE")
    if c.get("S15.3") is None:
        missing.append("FINAL_SCORE")
    return {"ready": not missing, "missing": missing}


def audit(report_path: Path, db_path: Path) -> dict:
    report_raw = report_path.read_bytes()
    digest = sha256(report_raw).hexdigest()
    if Path(str(report_path) + ".sha256").read_text("ascii").strip() != digest:
        raise ValueError("ORIGINAL_REPORT_SEAL_CHANGED")
    report = json.loads(report_raw)
    if len(report.get("stocks", ())) != 5 or len({s["ticker"] for s in report["stocks"]}) != 5:
        raise ValueError("FIVE_ORIGINAL_ISSUERS_REQUIRED")
    if not db_path.is_file() or db_path.is_symlink():
        raise ValueError("OPERATIONAL_DB_NOT_PLAIN_FILE")
    connection = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
    connection.execute("PRAGMA query_only=ON")
    try:
        rows = []
        for stock in report["stocks"]:
            models = {m["model"]: m for m in stock["models"] if m["model"] in MODEL_NAMES}
            if set(models) != set(MODEL_NAMES):
                raise ValueError("THREE_ORIGINAL_VERSIONS_REQUIRED")
            v12 = models[MODEL_NAMES[0]]["evidence"]["result"]
            gate = original_gate(v12)
            ticker = stock["ticker"]
            ids = [r[0] for r in connection.execute(
                "SELECT security_id FROM security_master WHERE ticker=?", (ticker,))]
            saved = []
            for sid in ids:
                saved.extend(connection.execute(
                    "SELECT feature_key, feature_as_of, available_at, source_phase, "
                    "quality_status, source_ref FROM canonical_model_features "
                    "WHERE security_id=? AND feature_as_of<=? AND available_at<=? "
                    "ORDER BY feature_key, feature_as_of, available_at",
                    (sid, stock["as_of"], stock["as_of"])).fetchall())
            keys = sorted({r[0] for r in saved})
            rows.append({"ticker": ticker, "report_as_of": stock["as_of"],
                         "original_v12_gate": gate,
                         "original_v12_engine_missing": models[MODEL_NAMES[0]]["missing"],
                         "v14_score": models[MODEL_NAMES[1]]["score"],
                         "v141_score": models[MODEL_NAMES[2]]["score"],
                         "db_security_ids": len(ids), "db_asof_feature_keys": keys,
                         "db_asof_rows_sha256": sha256(json.dumps(saved, sort_keys=True).encode()).hexdigest(),
                         "db_required_keys_present": sorted(set(keys) & set(REQUIRED_DB_KEYS))})
        global_counts = {key: connection.execute(
            "SELECT COUNT(*) FROM canonical_model_features WHERE feature_key=?", (key,)
        ).fetchone()[0] for key in REQUIRED_DB_KEYS}
    finally:
        connection.close()
    if any(row["original_v12_gate"]["ready"] or row["v14_score"] is not None
           or row["v141_score"] is not None for row in rows):
        raise ValueError("PREVIOUSLY_ACCEPTED_SCORE_REQUIRES_SEPARATE_REVIEW")
    return {"schema": "M10_V14_S15_SOURCE_INVENTORY_V1", "report_sha256": digest,
            "db_bytes": db_path.stat().st_size,
            "db_last_modified_ns": db_path.stat().st_mtime_ns,
            "required_key_global_counts": global_counts,
            "stocks": rows, "new_verified_version_gates": [],
            "new_full_scores": 0, "task12": "PARTIAL"}
