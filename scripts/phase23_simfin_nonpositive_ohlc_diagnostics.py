"""Phase23: strictly read-only triage of zero/negative SimFin OHLC fields.

Reconciles unchanged SimFin source with the real local Phase22 report. Does not
modify source CSV, models, SEC, prices or PIT and does not call external APIs.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
import json
import math
import os
from pathlib import Path
import re
import zipfile

from scripts.phase21_simfin_price_source_audit import (
    PriceInputBlocked, _file_sha256,
)
from scripts.phase22_simfin_ohlc_monthly_qa import (
    _classify_ohlc, input_text, _reader,
)

SCHEMA = "MERIDYEN_PHASE23_SIMFIN_NONPOSITIVE_OHLC_TRIAGE_V1"
FIELDS = ("open", "high", "low", "close")
SOURCE22 = "MERIDYEN_PHASE22_SIMFIN_OHLC_MONTHLY_PIT_QA_V1"


def _classify_detail(row: dict, columns: dict) -> tuple[str, list[str], dict[str, float]]:
    kind = _classify_ohlc(row, columns)
    if kind != "NONPOSITIVE_OHLC":
        return kind, [], {}
    try:
        prices = {f: float(row[columns[f]]) for f in FIELDS}
    except (ValueError, TypeError, KeyError):
        raise PriceInputBlocked("SOURCE_OHLC_CLASSIFIER_RECONCILIATION_FAILED")
    if not all(math.isfinite(v) for v in prices.values()):
        raise PriceInputBlocked("SOURCE_NONFINITE_CLASSIFIER_RECONCILIATION_FAILED")
    problems = [f"{f.upper()}_{'ZERO' if prices[f] == 0 else 'NEGATIVE'}"
                for f in FIELDS if prices[f] <= 0]
    if not problems:
        raise PriceInputBlocked("SOURCE_NONPOSITIVE_CLASSIFIER_RECONCILIATION_FAILED")
    return kind, problems, prices


def analyze(source: Path, phase22_report: Path) -> dict:
    if not source.is_file() or source.is_symlink():
        raise PriceInputBlocked("SOURCE_MISSING_OR_SYMLINK")
    if not phase22_report.is_file() or phase22_report.is_symlink():
        raise PriceInputBlocked("PHASE22_REPORT_MISSING_OR_SYMLINK")

    base = json.loads(phase22_report.read_text(encoding="utf-8"))
    if (base.get("schema") != SOURCE22 or
            base.get("status") != "RESEARCH_ONLY_OHLC_CAUSE_AND_MONTHLY_PIT_PRICE_COVERAGE_AUDIT"
            or base.get("reconciled_phase21_counts") is not True or
            base.get("verified_months") != 21):
        raise PriceInputBlocked("PHASE22_REPORT_NOT_VALIDATED")
    if base.get("original_price_file_sha256") != _file_sha256(source):
        raise PriceInputBlocked("SOURCE_HASH_MISMATCH")
    start = date.fromisoformat(base["period"]["start"])
    end = date.fromisoformat(base["period"]["end"])

    totals = Counter()
    field_problem_occurrences = Counter()
    exact_field_patterns = Counter()
    by_month = defaultdict(Counter)
    by_ticker = defaultdict(Counter)
    examples = []
    examples_by_pattern = Counter()

    with input_text(source) as handle:
        reader = _reader(handle)
        cols = {f: next((c for c in reader.fieldnames or []
                         if str(c).strip().lower() == f), None)
                for f in FIELDS}
        ticker_col = next((c for c in reader.fieldnames or []
                           if str(c).strip().lower() in ("ticker", "symbol")), None)
        date_col = next((c for c in reader.fieldnames or []
                         if str(c).strip().lower() == "date"), None)
        adjusted_col = next((c for c in reader.fieldnames or []
                             if str(c).strip().lower() in
                             ("adj. close", "adjusted close", "adj close")), None)
        if any(v is None for v in cols.values()) or not ticker_col or not date_col:
            raise PriceInputBlocked("MISSING_SOURCE_OHLC_TICKER_OR_DATE_COLUMNS")

        for row in reader:
            totals["source_rows"] += 1
            ticker = str(row.get(ticker_col) or "").strip().upper()
            ds = str(row.get(date_col) or "").strip()
            if not ticker or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ds):
                continue
            try:
                d = date.fromisoformat(ds)
            except ValueError:
                continue
            if not start <= d <= end:
                continue
            totals["window_rows"] += 1
            classification, issues, values = _classify_detail(row, cols)
            if classification == "VALID":
                totals["valid_rows"] += 1
            else:
                totals["invalid_rows"] += 1
            if classification != "NONPOSITIVE_OHLC":
                continue
            totals["nonpositive_rows"] += 1
            month = ds[:7]
            by_month[month]["invalid_nonpositive_rows"] += 1
            by_ticker[ticker]["nonpositive_rows"] += 1

            # Multiple zero fields in one row count ONCE in nonpositive_rows.
            for label in issues:
                field_problem_occurrences[label] += 1
            pattern = "+".join(issues)
            exact_field_patterns[pattern] += 1
            if all(v == 0 for v in values.values()):
                totals["all_four_ohlc_zero_rows"] += 1
            if values["close"] > 0:
                totals["invalid_nonpositive_with_positive_close"] += 1
            if values["close"] > 0 and adjusted_col:
                try:
                    adj = float(row.get(adjusted_col) or "")
                    if math.isfinite(adj) and adj > 0:
                        totals["invalid_nonpositive_positive_close_and_adjusted"] += 1
                except (TypeError, ValueError):
                    pass
            if examples_by_pattern[pattern] < 2 and len(examples) < 35:
                examples_by_pattern[pattern] += 1
                examples.append({
                    "ticker": ticker, "date": ds,
                    "problem_pattern": pattern,
                    # Private local report: small diagnostic excerpts, no source export.
                    "ohlc": {k: values[k] for k in FIELDS},
                })
    comparisons = {
        "window_rows": (totals["window_rows"], base.get("window_rows")),
        "valid_rows": (totals["valid_rows"], base.get("window_valid_ohlc_rows")),
        "invalid_rows": (totals["invalid_rows"], base.get("window_strict_invalid_ohlc_rows")),
        "nonpositive_rows": (
            totals["nonpositive_rows"],
            (base.get("invalid_ohlc_reason_counts") or {}).get("NONPOSITIVE_OHLC", 0)),
    }
    if any(actual != expected for actual, expected in comparisons.values()):
        raise PriceInputBlocked("PHASE22_TOTALS_MISMATCH")
    return {
        "schema": SCHEMA,
        "status": "RESEARCH_ONLY_NONPOSITIVE_OHLC_FIELD_CAUSES_MEASURED",
        "period": {"start": str(start), "end": str(end)},
        "source_file_sha256": base["original_price_file_sha256"],
        "reconciled_against_phase22": True,
        "window_rows": totals["window_rows"],
        "window_invalid_ohlc_rows": totals["invalid_rows"],
        "window_nonpositive_ohlc_rows": totals["nonpositive_rows"],
        "nonpositive_field_occurrences_not_distinct_rows":
            dict(sorted(field_problem_occurrences.items())),
        "exact_nonpositive_field_pattern_rows":
            dict(sorted(exact_field_patterns.items())),
        "all_four_ohlc_zero_rows": totals["all_four_ohlc_zero_rows"],
        "nonpositive_rows_with_positive_raw_close":
            totals["invalid_nonpositive_with_positive_close"],
        "nonpositive_rows_with_positive_close_and_adjusted_close":
            totals["invalid_nonpositive_positive_close_and_adjusted"],
        "monthly_nonpositive_row_counts":
            [{"month": month, **dict(counts)}
             for month, counts in sorted(by_month.items())],
        "top_tickers_nonpositive_rows_not_security_identity": [
            {"ticker": ticker, "rows": counts["nonpositive_rows"]}
            for ticker, counts in sorted(
                by_ticker.items(),
                key=lambda item: (-item[1]["nonpositive_rows"], item[0])
            )[:25]
        ],
        "sample_rows_small_private_audit_only": examples,
        "provider_zero_field_semantics_verified": False,
        "adjusted_close_corporate_actions_certified": False,
        "historical_CIK_mapping_certified": False,
        "rows_automatically_repaired": 0,
        "rows_deleted": 0,
        "production_database_modified": False,
        "model_training_performed": False,
        "network_requests": 0,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    default = Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / (
        "S153ResearchTerminal/runtime"
    )
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--phase22-report", type=Path,
                   default=default / "phase22/simfin_ohlc_monthly_coverage.json")
    p.add_argument("--out", type=Path,
                   default=default / "phase23/simfin_nonpositive_ohlc_diagnostics.json")
    args = p.parse_args()
    try:
        result = analyze(args.input, args.phase22_report)
        out = args.out.expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        temp = out.with_suffix(".json.tmp")
        temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        temp.replace(out)
    except (ValueError, OSError, KeyError, zipfile.BadZipFile):
        print("PHASE23_BLOCKED: SOURCE_OR_RECONCILIATION_INVALID")
        return 2
    print(json.dumps({
        "status": result["status"],
        "window_nonpositive_ohlc_rows": result["window_nonpositive_ohlc_rows"],
        "field_counts": result["nonpositive_field_occurrences_not_distinct_rows"],
        "exact_field_patterns": result["exact_nonpositive_field_pattern_rows"],
        "all_four_zero": result["all_four_ohlc_zero_rows"],
        "nonpositive_positive_close":result["nonpositive_rows_with_positive_raw_close"],
        "nonpositive_positive_close_and_adj":
            result["nonpositive_rows_with_positive_close_and_adjusted_close"],
        "source_reconciled": result["reconciled_against_phase22"],
        "report_path": str(out),
        "database_modified": False,
        "rows_repaired": 0,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
