from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from core.historical.s16_feature_coverage import assess_feature_coverage


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--positives",
        type=Path,
        default=Path("data/seeds/s16_positive_events.csv"),
    )
    parser.add_argument(
        "--controls",
        type=Path,
        default=Path("data/seeds/s16_matched_control_manifest.csv"),
    )
    parser.add_argument("--features", type=Path)
    args = parser.parse_args()

    positives = _read(args.positives)
    controls = _read(args.controls)
    filled_controls = [
        row for row in controls
        if row.get("control_security_id") and row.get("control_ticker")
    ]
    status = {
        "positive_seed_count": len(positives),
        "control_slot_count": len(controls),
        "filled_control_count": len(filled_controls),
        "positive_seed_ready": len(positives) == 31,
        "control_manifest_ready": len(controls) == 1550,
        "real_controls_ready": len(filled_controls) == 1550,
        "feature_rows": 0,
        "score_ready_feature_rows": 0,
        "status": "BLOCKED_REAL_PIT_CONTROLS",
    }

    if args.features and args.features.exists():
        rows = _read(args.features)
        ready = 0
        for row in rows:
            features = {
                key: (
                    None if row.get(key, "") == ""
                    else float(row[key])
                )
                for key in (
                    "float_scarcity", "short_pressure", "float_turnover",
                    "liquidity_elasticity", "ownership_lock", "catalyst",
                    "volume_ignition", "momentum_acceleration", "social_velocity",
                    "news_velocity", "regime_sympathy", "attention", "compression",
                    "catalyst_proximity", "theme", "anomaly", "dilution_risk",
                    "extension_risk", "data_risk", "liquidity_risk",
                    "manipulation_risk",
                )
            }
            ready += int(assess_feature_coverage(features).score_ready)
        status["feature_rows"] = len(rows)
        status["score_ready_feature_rows"] = ready

    if status["real_controls_ready"]:
        status["status"] = (
            "READY_FOR_SCORE_JOIN"
            if status["score_ready_feature_rows"] >= 1581
            else "BLOCKED_PIT_FEATURE_COVERAGE"
        )

    print(json.dumps(status, indent=2))
    return 0 if status["status"] == "READY_FOR_SCORE_JOIN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
