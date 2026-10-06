from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path

from core.backtest.s16_benchmark import S16BenchmarkRow, benchmark_grid


BOOL_FIELDS = (
    "hit_3x_high", "hit_5x_high", "hit_10x_high",
    "hit_3x_close", "hit_5x_close", "hit_10x_close",
)


def _bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise ValueError(f"invalid boolean: {value!r}")


def _read(path: Path) -> list[S16BenchmarkRow]:
    out: list[S16BenchmarkRow] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            out.append(S16BenchmarkRow(
                observation_id=raw["observation_id"],
                cohort=raw["cohort"],
                v02_armed=float(raw["v02_armed"]),
                v02_ignition=float(raw["v02_ignition"]),
                v03_armed=float(raw["v03_armed"]),
                v03_ignition=float(raw["v03_ignition"]),
                v1_armed=float(raw.get("v1_armed") or 0.0),
                v1_ignition=float(raw.get("v1_ignition") or 0.0),
                v1_explosive=float(raw.get("v1_explosive") or 0.0),
                **{key: _bool(raw[key]) for key in BOOL_FIELDS},
            ))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--json-output", required=True, type=Path)
    parser.add_argument("--csv-output", required=True, type=Path)
    parser.add_argument("--expected-positives", type=int, default=31)
    parser.add_argument("--expected-controls", type=int, default=1550)
    args = parser.parse_args()

    rows = _read(args.input)
    positives = sum(row.cohort == "POSITIVE" for row in rows)
    controls = sum(row.cohort == "CONTROL" for row in rows)
    if positives != args.expected_positives or controls != args.expected_controls:
        raise RuntimeError(
            f"case-control cohort incomplete: positives={positives}, controls={controls}; "
            f"expected {args.expected_positives}/{args.expected_controls}"
        )

    metrics = benchmark_grid(rows)
    payload = {
        "dataset_kind": "MATCHED_CASE_CONTROL",
        "positives": positives,
        "controls": controls,
        "observations": len(rows),
        "warning": (
            "case_control_precision is sample-design dependent and is NOT a "
            "real-world P(3x/5x/10x). Use recall/FPR for model comparison; "
            "population calibration requires an unbiased market-prevalence run."
        ),
        "metrics": [asdict(item) for item in metrics],
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    args.csv_output.parent.mkdir(parents=True, exist_ok=True)
    rows_dict = [asdict(item) for item in metrics]
    with args.csv_output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows_dict[0]))
        writer.writeheader()
        writer.writerows(rows_dict)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
