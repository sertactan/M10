"""SEC public companyfacts shard collector for PRIVATE, temporary Actions artifacts.

Never changes M10 production databases or canonical scoring. Outputs are
source-only research evidence, NOT historical PIT certification.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, date
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

CATALOG_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
FACTS_ROOT = "https://data.sec.gov/api/xbrl/companyfacts/"
SCHEMA = "MERIDYEN_SEC_SHARD_RESEARCH_V1"
ALLOWED_HOSTS = {"www.sec.gov", "data.sec.gov"}


class IntakeBlocked(Exception):
    pass


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(path)


def _json(path: Path, value: object) -> None:
    _atomic(path, (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _fetch(url: str, user_agent: str, limit: int) -> bytes:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
        raise IntakeBlocked("SOURCE_URL_NOT_ALLOWLISTED")
    request = Request(url, headers={
        "User-Agent": user_agent,
        "Accept": "application/json",
        "Accept-Encoding": "identity",
    })
    with urlopen(request, timeout=45) as response:
        final = urlsplit(response.geturl())
        if final.scheme != "https" or final.hostname not in ALLOWED_HOSTS:
            raise IntakeBlocked("UNEXPECTED_SOURCE_REDIRECT")
        if response.status != 200:
            raise IntakeBlocked("HTTP_STATUS_" + str(response.status))
        length = response.headers.get("Content-Length", "")
        if length.isdigit() and int(length) > limit:
            raise IntakeBlocked("SOURCE_SIZE_LIMIT")
        data = response.read(limit + 1)
        if len(data) > limit:
            raise IntakeBlocked("SOURCE_SIZE_LIMIT")
        return data


def catalog_rows(payload: bytes) -> list[dict]:
    try:
        raw = json.loads(payload)
        columns = raw["fields"]
        rows = raw["data"]
        assert all(name in columns for name in ("cik", "ticker", "exchange"))
    except (ValueError, KeyError, TypeError, AssertionError) as exc:
        raise IntakeBlocked("SEC_CATALOG_SCHEMA_INVALID") from exc
    found = {}
    for entry in rows:
        record = dict(zip(columns, entry))
        exchange = str(record.get("exchange", "")).upper()
        if exchange not in {"NASDAQ", "NYSE", "NYSE AMERICAN", "NYSEAMERICAN", "AMEX"}:
            continue
        try:
            cik = int(record["cik"])
        except (ValueError, TypeError):
            continue
        if cik <= 0:
            continue
        ticker = str(record["ticker"]).strip().upper()
        if not ticker:
            continue
        found[(cik, ticker)] = {"cik": cik, "ticker": ticker, "exchange": exchange}
    if not found:
        raise IntakeBlocked("NO_ELIGIBLE_SEC_CATALOG_ROWS")
    return sorted(found.values(), key=lambda row: (row["cik"], row["ticker"]))


def fact_dates(payload: bytes, cik: int, start: date, end: date) -> dict:
    try:
        data = json.loads(payload)
        if int(data["cik"]) != cik or not isinstance(data.get("facts"), dict):
            raise ValueError("CIK or facts")
    except (KeyError, TypeError, ValueError) as exc:
        raise IntakeBlocked("SEC_COMPANYFACTS_SCHEMA_OR_CIK_MISMATCH") from exc
    entries = 0
    distinct_filed = set()
    for namespace in data["facts"].values():
        if not isinstance(namespace, dict):
            continue
        for concept in namespace.values():
            if not isinstance(concept, dict):
                continue
            for units in (concept.get("units") or {}).values():
                for fact in units:
                    if not isinstance(fact, dict):
                        continue
                    filed = fact.get("filed")
                    if not isinstance(filed, str):
                        continue
                    try:
                        filing_date = date.fromisoformat(filed)
                    except ValueError:
                        continue
                    if start <= filing_date <= end:
                        entries += 1
                        distinct_filed.add(filed)
    return {"source_fact_rows_filed_in_window": entries,
            "distinct_filing_dates_in_window": len(distinct_filed)}


def _user_agent(value: str) -> str:
    value = value.strip()
    if len(value) < 12 or "@" not in value or "example." in value.lower():
        raise IntakeBlocked("REAL_SEC_USER_AGENT_REQUIRED")
    if "\n" in value or "\r" in value:
        raise IntakeBlocked("INVALID_USER_AGENT")
    return value


def run(args, fetch=_fetch, sleep=time.sleep) -> dict:
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    if end < start or not (1 <= args.shard_size <= 100) or args.shard_index < 0:
        raise IntakeBlocked("INVALID_WINDOW_OR_SHARD")
    if not (1 <= args.max_total_mib <= 250) or not (1 <= args.max_source_mib <= 25):
        raise IntakeBlocked("INVALID_SIZE_LIMIT")
    if args.pause < 0.5:
        raise IntakeBlocked("SEC_REQUEST_INTERVAL_BELOW_POLICY")
    out = Path(args.out_dir).resolve()
    if out.is_symlink():
        raise IntakeBlocked("SYMLINK_OUTPUT_DIR_NOT_ALLOWED")
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "status.json"
    report = {
        "schema": SCHEMA, "status": "PREVIEW_ONLY", "start": start.isoformat(),
        "end": end.isoformat(), "shard_index": args.shard_index,
        "shard_size": args.shard_size, "source": "SEC_COMPANYFACTS_RESEARCH_ONLY",
        "historical_pit_certified": False, "adjusted_price_certified": False,
        "model_training_performed": False, "production_database_modified": False,
        "canonical_formula_modified": False, "downloaded": 0, "reused": 0,
        "failed": [], "results": [], "total_catalog_us_equity_rows": None,
        "catalog_sha256": None,
    }
    if not args.execute:
        report["status"] = "PREVIEW_ONLY_NO_NETWORK"
        _json(report_path, report)
        return report
    try:
        agent = _user_agent(os.environ.get("SEC_USER_AGENT", ""))
        catalog_path = out / "sec_catalog.json"
        if catalog_path.is_file():
            raw_catalog = catalog_path.read_bytes()
            catalog_rows(raw_catalog)  # validate restored artifact
        else:
            raw_catalog = fetch(CATALOG_URL, agent, 8 * 1024 * 1024)
            catalog_rows(raw_catalog)
            _atomic(catalog_path, raw_catalog)
            sleep(args.pause)
        report["catalog_sha256"] = _sha(raw_catalog)
        all_rows = catalog_rows(raw_catalog)
        report["total_catalog_us_equity_rows"] = len(all_rows)
        # Current SEC listings are an issuer lookup, never 2024/2025 PIT membership.
        report["catalog_is_historical_pit"] = False
        begin = args.shard_index * args.shard_size
        targets = all_rows[begin:begin + args.shard_size]
        report["shard_target_count"] = len(targets)
        if not targets:
            raise IntakeBlocked("SHARD_BEYOND_CURRENT_CATALOG")
        manifest_path = out / "source_manifest.json"
        manifest = _load(manifest_path) if manifest_path.is_file() else {}
        if not isinstance(manifest, dict):
            raise IntakeBlocked("INVALID_EXISTING_MANIFEST")
        used_bytes = sum(int(v.get("bytes", 0)) for v in manifest.values())
        if used_bytes < 0 or used_bytes > args.max_total_mib * 1024 * 1024:
            raise IntakeBlocked("STORED_SHARD_EXCEEDS_SIZE_LIMIT")
        for row in targets:
            cik = row["cik"]
            key = str(cik)
            path = out / "companyfacts" / ("CIK%010d.json" % cik)
            url = FACTS_ROOT + ("CIK%010d.json" % cik)
            try:
                if path.is_file():
                    old = manifest.get(key)
                    if not old or old.get("sha256") != _sha(path.read_bytes()):
                        raise IntakeBlocked("UNVERIFIED_OR_CHANGED_RESTORED_FILE")
                    payload = path.read_bytes()
                    report["reused"] += 1
                else:
                    if key in manifest:
                        raise IntakeBlocked("MANIFEST_REFERENCES_MISSING_FILE")
                    if used_bytes >= args.max_total_mib * 1024 * 1024:
                        raise IntakeBlocked("SHARD_TOTAL_BYTE_BUDGET_EXHAUSTED")
                    limit = min(args.max_source_mib * 1024 * 1024,
                                args.max_total_mib * 1024 * 1024 - used_bytes)
                    payload = fetch(url, agent, limit)
                    metrics = fact_dates(payload, cik, start, end)
                    _atomic(path, payload)
                    manifest[key] = {
                        "sha256": _sha(payload), "bytes": len(payload),
                        "url": url,
                        "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    }
                    _json(manifest_path, manifest)
                    used_bytes += len(payload)
                    report["downloaded"] += 1
                    sleep(args.pause)
                metrics = fact_dates(payload, cik, start, end)
                report["results"].append({"cik": cik, "ticker": row["ticker"], **metrics})
            except (IntakeBlocked, OSError, ValueError, TimeoutError, Exception) as exc:
                # Fail closed and checkpoint completed files; never silently skip an issuer.
                report["failed"].append({"cik": cik, "ticker": row["ticker"],
                                          "reason": type(exc).__name__,
                                          "detail": str(exc)[:140]})
                break
        report["status"] = (
            "SEC_SOURCE_SHARD_COMPLETE_NOT_PIT_CERTIFIED"
            if not report["failed"] and len(report["results"]) == len(targets)
            else "PARTIAL_RESUMABLE_NOT_PIT_CERTIFIED"
        )
    except (IntakeBlocked, OSError, ValueError, TimeoutError, Exception) as exc:
        report["status"] = "BLOCKED_OR_PARTIAL_NOT_PIT_CERTIFIED"
        report["failed"].append({"reason": type(exc).__name__, "detail": str(exc)[:140]})
    finally:
        _json(report_path, report)
    return report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start", default="2024-01-01")
    p.add_argument("--end", default="2025-09-30")
    p.add_argument("--shard-index", type=int, default=0)
    p.add_argument("--shard-size", type=int, default=10)
    p.add_argument("--max-total-mib", type=int, default=80)
    p.add_argument("--max-source-mib", type=int, default=20)
    p.add_argument("--pause", type=float, default=1.0)
    p.add_argument("--out-dir", type=Path, default=Path("phase19_sec_shard"))
    p.add_argument("--execute", action="store_true")
    a = p.parse_args()
    report = run(a)
    print(json.dumps({k: v for k, v in report.items()
                      if k not in ("results",)}, ensure_ascii=False))
    return 0 if report["status"] in (
        "PREVIEW_ONLY_NO_NETWORK", "SEC_SOURCE_SHARD_COMPLETE_NOT_PIT_CERTIFIED"
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
