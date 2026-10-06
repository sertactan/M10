from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path

from core.historical.s16_controls import S16MatchSnapshot, build_matched_controls


def _read_snapshots(path: Path) -> list[S16MatchSnapshot]:
    rows: list[S16MatchSnapshot] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append(S16MatchSnapshot(
                security_id=row["security_id"],
                ticker=row["ticker"],
                as_of_date=date.fromisoformat(row["as_of_date"]),
                market_cap=float(row["market_cap"]),
                float_shares=float(row["float_shares"]),
                price=float(row["price"]),
                adv20=float(row["adv20"]),
                volatility20=float(row["volatility20"]),
                mom5=float(row["mom5"]),
                mom20=float(row["mom20"]),
                sector=row["sector"],
                listing_age_days=int(row["listing_age_days"]),
                security_type=row.get("security_type", "CS") or "CS",
                ipo_route=(row.get("ipo_route", "false").lower() == "true"),
            ))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build leakage-safe S16 31x50 PIT matched controls."
    )
    parser.add_argument("--positives", required=True, type=Path)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--controls-per-positive", type=int, default=50)
    args = parser.parse_args()

    positives = _read_snapshots(args.positives)
    candidates = _read_snapshots(args.candidates)
    matches = build_matched_controls(
        positives,
        candidates,
        controls_per_positive=args.controls_per_positive,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "positive_security_id", "positive_ticker", "as_of_date",
            "control_rank", "control_security_id", "control_ticker", "distance",
        ])
        for row in matches:
            writer.writerow([
                row.positive_security_id, row.positive_ticker,
                row.as_of_date.isoformat(), row.control_rank,
                row.control_security_id, row.control_ticker,
                f"{row.distance:.10f}",
            ])

    expected = len(positives) * args.controls_per_positive
    if len(matches) != expected:
        raise RuntimeError(f"expected {expected} matches, wrote {len(matches)}")
    print(f"wrote {len(matches)} matched controls to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
