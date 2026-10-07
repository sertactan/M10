from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from app.bootstrap import AppContainer
from app.bulk_data_bootstrap import (
    ensure_sec_companyfacts_all_known,
    ensure_stooq_raw_all_known,
)
from core.research.walkforward_readiness import WalkForwardReadinessAuditor
from scripts.enrich_historical_ciks import run as enrich_historical_ciks
from scripts.sync_free_pit_universe import run as sync_free_pit_universe


async def run(args) -> int:
    root = Path(__file__).resolve().parents[1]
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    stage_status: dict[str, object] = {}

    universe_code = 0
    if not args.skip_universe:
        universe_code = await sync_free_pit_universe(
            start,
            end,
            overwrite=args.overwrite_universe,
        )
        stage_status["pit_universe_exit_code"] = universe_code

    if not args.skip_cik:
        stage_status["cik_enrichment_exit_code"] = await enrich_historical_ciks()

    app = AppContainer(root)
    app.initialize()
    try:
        if not args.skip_sec:
            try:
                sec_securities, sec_facts = ensure_sec_companyfacts_all_known(
                    app,
                    minimum_coverage_ratio=args.sec_coverage,
                    force_refresh=args.force_sec,
                )
                stage_status["sec_companyfacts"] = {
                    "securities": sec_securities,
                    "facts_written": sec_facts,
                    "status": "OK",
                }
            except Exception as exc:
                stage_status["sec_companyfacts"] = {
                    "status": "BLOCKED",
                    "error": str(exc),
                }

        if not args.skip_stooq:
            try:
                stooq_series, stooq_bars = ensure_stooq_raw_all_known(
                    app,
                    minimum_coverage_ratio=args.stooq_coverage,
                    force_refresh=args.force_stooq,
                )
                stage_status["stooq_raw"] = {
                    "series": stooq_series,
                    "bars_written": stooq_bars,
                    "status": "OK_RAW_ONLY",
                    "backtest_authoritative": False,
                }
            except Exception as exc:
                stage_status["stooq_raw"] = {
                    "status": "BLOCKED",
                    "error": str(exc),
                    "backtest_authoritative": False,
                }

        auditor = WalkForwardReadinessAuditor(app.sqlite)
        dates = [
            value
            for value in auditor.available_snapshot_dates()
            if start <= value <= end
        ]
        readiness = auditor.audit_many(dates)
        stage_status["readiness"] = {
            "snapshot_dates": len(readiness),
            "exact_pit_dates": sum(1 for row in readiness if row.exact_pit_universe),
            "fully_unblocked_dates": sum(1 for row in readiness if not row.blockers),
            "dates": [
                {
                    **asdict(row),
                    "as_of_date": row.as_of_date.isoformat(),
                    "price_coverage_pct": round(row.price_coverage_pct, 2),
                    "fundamental_coverage_pct": round(row.fundamental_coverage_pct, 2),
                    "feature_coverage_pct": round(row.feature_coverage_pct, 2),
                    "v141_upstream_ready_pct": round(row.v141_upstream_ready_pct, 2),
                    "blockers": list(row.blockers),
                }
                for row in readiness
            ],
            "price_coverage_definition": (
                "BACKTEST/BACKTEST_ADJUSTED selections only; "
                "SCANNER_BOOTSTRAP Stooq RAW_ONLY excluded"
            ),
        }

        print(json.dumps(stage_status, indent=2, default=str))
    finally:
        app.close()

    # A free-plan universe request may stop on a provider rate-limit after
    # persisting earlier dates. Preserve that nonzero code so the command is
    # explicitly incomplete and safe to resume.
    return universe_code if universe_code != 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap zero-paid-API WF1 historical evidence and audit readiness"
    )
    parser.add_argument("--start", default="2013-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--skip-universe", action="store_true")
    parser.add_argument("--skip-cik", action="store_true")
    parser.add_argument("--skip-sec", action="store_true")
    parser.add_argument("--skip-stooq", action="store_true")
    parser.add_argument("--overwrite-universe", action="store_true")
    parser.add_argument("--force-sec", action="store_true")
    parser.add_argument("--force-stooq", action="store_true")
    parser.add_argument("--sec-coverage", type=float, default=0.70)
    parser.add_argument("--stooq-coverage", type=float, default=0.70)
    args = parser.parse_args()
    if not (0.0 < args.sec_coverage <= 1.0):
        parser.error("--sec-coverage must be in (0,1]")
    if not (0.0 < args.stooq_coverage <= 1.0):
        parser.error("--stooq-coverage must be in (0,1]")
    if date.fromisoformat(args.end) < date.fromisoformat(args.start):
        parser.error("--end must be >= --start")
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
