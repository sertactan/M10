"""Deterministic flat CSV and complete source/provenance JSON reports."""
from __future__ import annotations

import csv
import json
from pathlib import Path


def export_report(report: dict, prefix) -> tuple[Path, Path]:
    prefix = Path(prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path, csv_path = prefix.with_suffix(".json"), prefix.with_suffix(".csv")
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False,
                                    sort_keys=True, allow_nan=False), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "ticker", "cik", "period_end", "model", "original_status",
            "personal_status", "personal_score", "numeric_result_type",
            "missing", "evidence_sha256"])
        writer.writeheader()
        for name, result in report.get("models", {}).items():
            writer.writerow({
                "ticker": report.get("ticker"), "cik": report.get("cik"),
                "period_end": report.get("period_end"), "model": name,
                "original_status": result.get("original_status", "N/A"),
                "personal_status": result.get("status", "UNRESOLVED"),
                "personal_score": result.get("score"),
                "numeric_result_type": result.get("numeric_result_type"),
                "missing": "; ".join(result.get("missing", [])),
                "evidence_sha256": result.get("receipt_sha256"),
            })
    return json_path, csv_path
