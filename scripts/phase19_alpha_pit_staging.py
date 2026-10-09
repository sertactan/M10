"""Stage historical Alpha Vantage LISTING_STATUS CSVs without touching M10 SQLite.

Reconstructs a *research-only* listing universe. Retroactive API responses are
not proof of original date-time availability or stable issuer identity.
"""
from __future__ import annotations

import argparse
import calendar
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from core.config.env import load_local_env
from data.providers.alpha_vantage_pit_universe import AlphaVantagePitUniverseProvider


class PITStageBlocked(ValueError):
    pass


def month_ends(start: date, end: date) -> list[date]:
    if end < start:
        raise PITStageBlocked("END_BEFORE_START")
    year, month = start.year, start.month
    result: list[date] = []
    while (year, month) <= (end.year, end.month):
        last = date(year, month, calendar.monthrange(year, month)[1])
        if start <= last <= end:
            result.append(last)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return result


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    with part.open("xb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    part.replace(path)


def atomic_json(path: Path, data: dict) -> None:
    content = (json.dumps(data, sort_keys=True, indent=2) + "\n").encode("utf-8")
    atomic_bytes(path, content)


def _raw_response(provider: AlphaVantagePitUniverseProvider, as_of: date) -> bytes:
    """One request. Intentionally do not expose query URL (contains API key)."""
    import httpx

    # Alpha Vantage's established M10 adapter follows HTTP redirects. Preserve
    # that behavior, but never send the query (which includes the key) to an
    # unapproved redirect host. A redirect is still one logical provider call.
    with httpx.Client(timeout=90.0, follow_redirects=False) as client:
        request = client.build_request(
            "GET", "https://www.alphavantage.co/query",
            params={"function": "LISTING_STATUS", "date": as_of.isoformat(),
                    "state": "active", "apikey": provider.api_key},
            headers={"User-Agent": "S15.3 Research Terminal", "Accept": "text/csv"},
        )
        for _ in range(4):
            response = client.send(request, follow_redirects=False)
            if response.status_code in (301, 302, 303, 307, 308):
                next_request = response.next_request
                if next_request is None:
                    raise PITStageBlocked("PROVIDER_REDIRECT_MISSING_LOCATION")
                if (next_request.url.scheme != "https" or
                    next_request.url.host not in {"www.alphavantage.co", "alphavantage.co"}):
                    raise PITStageBlocked("PROVIDER_REDIRECT_HOST_NOT_ALLOWED")
                request = next_request
                continue
            if response.status_code != 200:
                raise PITStageBlocked("PROVIDER_HTTP_STATUS_" + str(response.status_code))
            if len(response.content) > 10 * 1024 * 1024:
                raise PITStageBlocked("CSV_SOURCE_OVER_10MIB")
            return response.content
        raise PITStageBlocked("PROVIDER_REDIRECT_LIMIT_EXCEEDED")


def stage(*, start: date, end: date, root: Path, execute: bool,
          max_requests: int = 1, fetch=None) -> dict:
    if not 1 <= max_requests <= 5:
        raise PITStageBlocked("MAX_REQUESTS_LIMIT_1_TO_5")
    dates = month_ends(start, end)
    if not dates:
        raise PITStageBlocked("NO_MONTH_ENDS_IN_WINDOW")
    if root.is_symlink():
        raise PITStageBlocked("OUTPUT_ROOT_SYMLINK")
    status = {
        "schema": "MERIDYEN_PHASE19_AV_PIT_STAGING_V1",
        "status": "OFFLINE_PREVIEW_ONLY" if not execute else "PARTIAL_RESEARCH_SOURCE_ONLY",
        "start": start.isoformat(), "end": end.isoformat(),
        "requested_month_ends": len(dates),
        "api_requests": 0, "saved": 0, "reused": 0,
        "remaining": [], "snapshots": [], "error": None, "error_code": None,
        "production_database_modified": False,
        "historical_pit_identity_certified": False,
        "canonical_adjusted_price_certified": False,
        "model_training_performed": False,
    }
    provider = None
    if execute:
        provider = AlphaVantagePitUniverseProvider()
        if not provider.configured:
            raise PITStageBlocked("ALPHAVANTAGE_API_KEY_NOT_CONFIGURED")
    get_source = fetch or _raw_response
    for as_of in dates:
        name = as_of.isoformat()
        path = root / (name + ".csv")
        manifest_path = root / (name + ".manifest.json")
        if path.is_file() != manifest_path.is_file():
            raise PITStageBlocked("UNPAIRED_CSV_OR_MANIFEST_" + name)
        if path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload = path.read_bytes()
            if (manifest.get("as_of") != name or manifest.get("sha256") != sha256(payload)
                or manifest.get("source") != "ALPHAVANTAGE_LISTING_STATUS_RESEARCH_ONLY"):
                raise PITStageBlocked("RESTORED_SOURCE_CHECKSUM_MISMATCH_" + name)
            # Validate source CSV again, without a new provider call.
            records = AlphaVantagePitUniverseProvider.parse_csv(payload.decode("utf-8-sig"),
                                                                  as_of=as_of)
            if manifest.get("qualified_stock_rows") != len(records):
                raise PITStageBlocked("RESTORED_SOURCE_ROW_COUNT_MISMATCH_" + name)
            status["reused"] += 1
        elif not execute or status["api_requests"] >= max_requests:
            status["remaining"].append(name)
            continue
        else:
            try:
                # Count attempted provider calls even when a response fails.
                status["api_requests"] += 1
                payload = get_source(provider, as_of)
                records = AlphaVantagePitUniverseProvider.parse_csv(
                    payload.decode("utf-8-sig"), as_of=as_of
                )
            except Exception as exc:
                # Never print provider exception text or request URL (may contain API key).
                status["error"] = type(exc).__name__
                if isinstance(exc, PITStageBlocked):
                    code = str(exc)
                    status["error_code"] = (code if code.isascii() and
                        code.replace("_", "").isalnum() and len(code) <= 80
                        else "PROVIDER_REQUEST_BLOCKED")
                else:
                    status["error_code"] = "PROVIDER_TRANSPORT_OR_RESPONSE_ERROR"
                status["remaining"].append(name)
                status["remaining"].extend(d.isoformat() for d in dates if d > as_of)
                break
            counts = {market: sum(1 for r in records if r.exchange.value == market)
                      for market in ("NASDAQ", "NYSE", "AMEX")}
            manifest = {
                "schema": "MERIDYEN_PHASE19_AV_LISTING_SOURCE_V1",
                "source": "ALPHAVANTAGE_LISTING_STATUS_RESEARCH_ONLY",
                "as_of": name,
                "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                "sha256": sha256(payload),
                "bytes": len(payload),
                "qualified_stock_rows": len(records),
                "exchange_counts": counts,
                "historical_pit_identity_certified": False,
                "stable_cik_or_figi_mapping_verified": False,
                "canonicity": "STAGING_NOT_FOR_MODEL_TRAINING",
                "production_database_modified": False,
            }
            atomic_bytes(path, payload)
            atomic_json(manifest_path, manifest)
            status["saved"] += 1
        status["snapshots"].append({
            "as_of": name, "qualified_stocks": len(records),
            "exchange_counts": manifest.get("exchange_counts", {
                x: sum(1 for r in records if r.exchange.value == x)
                for x in ("NASDAQ", "NYSE", "AMEX")
            }),
            "source_sha256": sha256(payload),
        })
    if execute:
        if status["error"]:
            status["status"] = "PROVIDER_BLOCKED_RESUMABLE_NONCANONICAL"
        elif status["remaining"]:
            status["status"] = "PARTIAL_RESUMABLE_RESEARCH_ONLY"
        else:
            status["status"] = "SOURCE_MONTHS_SAVED_NOT_PIT_CERTIFIED"
    return status


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start", default="2024-01-01")
    p.add_argument("--end", default="2025-09-30")
    default_root = Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / (
        "S153ResearchTerminal/runtime/phase19/pit_staging"
    )
    p.add_argument("--out-dir", type=Path, default=default_root)
    p.add_argument("--max-requests", type=int, default=1)
    p.add_argument("--execute", action="store_true", help="Explicit opt-in; default is offline preview")
    args = p.parse_args()
    load_local_env(Path(__file__).resolve().parents[1] / ".env")
    try:
        result = stage(start=date.fromisoformat(args.start),
                       end=date.fromisoformat(args.end),
                       root=args.out_dir.expanduser().resolve(),
                       max_requests=args.max_requests, execute=args.execute)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["error"] is None else 2
    except (PITStageBlocked, OSError, ValueError) as exc:
        # Only show controlled error class; no sensitive provider URL/credentials.
        print("PHASE19_PIT_STAGING_BLOCKED:", type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
