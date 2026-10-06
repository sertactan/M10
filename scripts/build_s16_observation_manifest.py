from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Combine resolved S16 positives and 1,550 controls into one feature manifest."
    )
    parser.add_argument("--positives", required=True, type=Path)
    parser.add_argument("--controls", required=True, type=Path)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    with args.positives.open(newline="", encoding="utf-8") as handle:
        positives = list(csv.DictReader(handle))
    with args.controls.open(newline="", encoding="utf-8") as handle:
        controls = list(csv.DictReader(handle))
    with args.candidates.open(newline="", encoding="utf-8") as handle:
        candidates = list(csv.DictReader(handle))

    candidate_by_key = {
        (row["security_id"], row["as_of_date"]): row
        for row in candidates
    }
    out: list[dict[str, str]] = []

    for row in positives:
        if not row.get("security_id") or not row.get("as_of_date"):
            continue
        candidate = candidate_by_key.get((row["security_id"], row["as_of_date"]))
        if candidate is None:
            continue
        out.append({
            "observation_id": f"POS:{row['event_id']}:{row['ticker']}",
            "cohort": "POSITIVE",
            **candidate,
        })

    for row in controls:
        security_id = row.get("control_security_id") or ""
        as_of_date = row.get("as_of_date") or ""
        if not security_id or not as_of_date:
            continue
        candidate = candidate_by_key.get((security_id, as_of_date))
        if candidate is None:
            continue
        out.append({
            "observation_id": (
                f"CTRL:{row['positive_ticker']}:{row['control_rank']}:"
                f"{row['control_ticker']}"
            ),
            "cohort": "CONTROL",
            **candidate,
        })

    positives_n = sum(row["cohort"] == "POSITIVE" for row in out)
    controls_n = sum(row["cohort"] == "CONTROL" for row in out)
    if positives_n != 31 or controls_n != 1550:
        raise RuntimeError(
            f"incomplete observation manifest: positives={positives_n}, controls={controls_n}; "
            "expected 31/1550"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(out[0]))
        writer.writeheader()
        writer.writerows(out)
    print(f"wrote {len(out)} S16 observations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
