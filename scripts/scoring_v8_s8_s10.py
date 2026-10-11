"""Offline S8/S10 missing-input audit against five pinned SEC bulk ZIP members."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v8_s8_s10 import audit_bulk, missing_matrix


def default_archive() -> Path:
    return (Path(os.environ.get("LOCALAPPDATA", ""))
            / "S153ResearchTerminal" / "runtime" / "bulk"
            / "sec" / "companyfacts.zip")


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--archive", type=Path, default=default_archive(),
                     help="existing offline SEC bulk companyfacts.zip")
    cli.add_argument("--full", action="store_true",
                     help="print all fact hashes/accessions in addition to blockers")
    opts = cli.parse_args()
    report = audit_bulk(opts.archive)
    if opts.full:
        output = report
    else:
        output = {k: v for k, v in report.items() if k != "stocks"}
        output["matrix"] = missing_matrix(report)
        output["source_sha256_by_ticker"] = {
            ticker: stock["companyfacts_sha256"]
            for ticker, stock in report["stocks"].items()
        }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
