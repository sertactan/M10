from __future__ import annotations

import argparse
import csv
from datetime import datetime, time, timezone
from pathlib import Path

from core.historical.s16_feature_coverage import (
    S16_REQUIRED_FEATURES,
    build_complete_s16_input,
)
from core.models.s16 import S16V02Model, S16V03Model


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    with args.input.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError("empty S16 historical feature file")

    output: list[dict[str, object]] = []
    skipped = 0
    for row in rows:
        features = {
            key: (None if row.get(key, "") == "" else float(row[key]))
            for key in S16_REQUIRED_FEATURES
        }
        as_of = datetime.combine(
            datetime.fromisoformat(row["as_of_date"]).date(),
            time.max,
            tzinfo=timezone.utc,
        )
        try:
            model_input = build_complete_s16_input(
                security_id=row["security_id"],
                ticker=row["ticker"],
                as_of=as_of,
                route=(row.get("route") or None),
                features=features,
            )
        except Exception:
            skipped += 1
            continue

        v02 = S16V02Model().analyze(model_input)
        v03 = S16V03Model().analyze(model_input)
        output.append({
            "observation_id": row["observation_id"],
            "cohort": row.get("cohort") or "",
            "security_id": row["security_id"],
            "ticker": row["ticker"],
            "as_of_date": row["as_of_date"],
            "v02_armed": f"{v02.armed_score:.10f}",
            "v02_ignition": f"{v02.ignition_score:.10f}",
            "v02_status": v02.status,
            "v03_armed": f"{v03.armed_score:.10f}",
            "v03_ignition": f"{v03.ignition_score:.10f}",
            "v03_status": v03.status,
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not output:
        raise RuntimeError(
            f"no score-ready S16 rows; skipped_incomplete={skipped}"
        )
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    print(f"wrote {len(output)} S16 scored rows; skipped_incomplete={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
