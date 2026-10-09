"""Read-only independent checks of an EXISTING Phase25Q research stage.

Never promote retrospectively retrieved vendor data to real PIT membership.
No writes, imports, market calls, credentials, or model training.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def audit_stage(folder: Path) -> dict[str, Any]:
    blocked = {"status": "INCONCLUSIVE", "canonical_pit": False,
               "walk_forward_allowed": False, "Learning_V3_allowed": False}
    manifest = folder / "manifest.json"
    database = folder / "research_pit.sqlite"
    if folder.is_symlink() or manifest.is_symlink() or database.is_symlink():
        return {**blocked, "reason": "SYMLINK_RESEARCH_SOURCE"}
    if not folder.is_dir() or not manifest.is_file() or not database.is_file():
        return {**blocked, "reason": "RESEARCH_STAGE_MISSING"}
    try:
        obj = json.loads(manifest.read_text(encoding="utf-8"))
        if (obj.get("schema") != "MERIDYEN_PHASE25Q_VERSIONED_RESEARCH_STAGING_V1"
            or obj.get("status") != "RESEARCH_ONLY_NOT_CANONICAL_PIT"
            or obj.get("month_end_snapshots") != 21
            or obj.get("phase25k_research_gate_rows") != 133
            or obj.get("independent_PIT_identity_certs") != 0
            or obj.get("independent_adjusted_price_certs") != 0
            or obj.get("backtest_eligible_securities") != 0
            or obj.get("canonical_ready") is not False
            or obj.get("WF9_executed") is not False
            or obj.get("Learning_V3_executed") is not False):
            return {**blocked, "reason": "STAGING_MANIFEST_UNCERTIFIED"}
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=5) as con:
            if con.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                return {**blocked, "reason": "STAGING_SQLITE_INTEGRITY_FAILED"}
            counts = {}
            for label, table in (
                ("memberships", "monthly_research_membership"),
                ("source_prices", "source_daily_price"),
                ("research_gates", "candidate_gate")):
                counts[label] = int(con.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
            stage_months = con.execute(
                "SELECT count(distinct month_end) FROM monthly_research_membership").fetchone()[0]
            approved = con.execute(
                "SELECT count(*) FROM candidate_gate WHERE canonical_approved != 0").fetchone()[0]
            if (counts["memberships"] != obj.get("monthly_membership_rows")
                or counts["source_prices"] != obj.get("source_daily_valid_price_rows")
                or counts["research_gates"] != 133
                or stage_months != 21 or approved != 0):
                return {**blocked, "reason": "STAGING_MANIFEST_ROW_COUNT_MISMATCH"}
        return {
            "status": "SOURCE_STAGING_VERIFIED_RESEARCH_ONLY",
            "schema": obj["schema"],
            "months": stage_months,
            "counts": counts,
            "version_prefix": str(obj.get("staging_version", ""))[:16],
            "canonical_pit": False,
            "walk_forward_allowed": False,
            "Learning_V3_allowed": False,
            "source_only": True,
            "reason": "RETROSPECTIVE_NOT_AVAILABLE_AT_HISTORICAL_AS_OF",
        }
    except (OSError, ValueError, sqlite3.Error, KeyError, TypeError, UnicodeError):
        return {**blocked, "reason": "READ_ONLY_RESEARCH_AUDIT_ERROR"}
