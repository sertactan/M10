"""One-shot compliant official SEC companyfacts recovery into PRIVATE local cache.

Use only if an equivalent Companyfacts JSON is absent from existing caches.
Never log or copy a SEC contact into any output, and do not retry a denial.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _contact(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise ValueError("A local SEC contact configuration is required")
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.lstrip().startswith(("#", ";")) or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != "SEC_USER_AGENT":
            continue
        value = value.strip().strip('"').strip("'")
        if ("@" not in value or "example" in value.lower() or
                "localhost" in value.lower() or "your" in value.lower()):
            raise ValueError("SEC_USER_AGENT must contain a legitimate configured contact")
        return value
    raise ValueError("SEC_USER_AGENT is unavailable in the supplied local configuration")


def probe(*, user_env: Path, target: Path, cik: str) -> dict:
    if not re.fullmatch(r"\d{1,10}", cik) or int(cik) == 0:
        raise ValueError("Valid CIK required")
    if ("scoring_completion" not in {p.lower() for p in target.resolve().parts}
            or target.name != "companyfacts.json" or target.is_symlink()):
        raise ValueError("Only a new private scoring_completion Companyfacts cache is permitted")
    if target.exists():
        data = target.read_bytes()
        return {"status": "REUSED_EXISTING_CACHE", "sha256": sha256(data).hexdigest(),
                "bytes": len(data), "network_requests": 0}
    contact = _contact(user_env)
    request = Request(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json",
                      headers={"User-Agent": contact, "Accept": "application/json",
                               "Accept-Encoding": "identity"})
    try:
        with urlopen(request, timeout=20) as response:
            if response.status != 200:
                return {"status": "HTTP_NOT_200", "http_status": response.status,
                        "network_requests": 1}
            raw = response.read(50_000_001)
    except HTTPError as exc:
        return {"status": "SEC_ACCESS_DENIED_OR_ERROR", "http_status": exc.code,
                "network_requests": 1}
    except (OSError, URLError) as exc:
        return {"status": "SEC_NETWORK_UNAVAILABLE", "error_type": type(exc).__name__,
                "network_requests": 1}
    if len(raw) > 50_000_000:
        raise ValueError("Unexpected SEC response size")
    decoded = json.loads(raw)
    if not isinstance(decoded, dict) or int(decoded.get("cik", -1)) != int(cik) or not isinstance(decoded.get("facts"), dict):
        raise ValueError("Unexpected SEC JSON issuer or payload")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as handle:
        handle.write(raw)
    return {"status": "SEC_COMPANYFACTS_SAVED_PRIVATE_RESEARCH_CACHE",
            "scope": "CURRENT_RETRIEVABILITY_NOT_HISTORICAL_PIT",
            "sha256": sha256(raw).hexdigest(), "bytes": len(raw),
            "network_requests": 1,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "taxonomies": sorted(decoded["facts"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contact-env", required=True, type=Path)
    parser.add_argument("--private-cache", required=True, type=Path)
    parser.add_argument("--cik", default="0000903651")
    args = parser.parse_args()
    print(json.dumps(probe(user_env=args.contact_env, target=args.private_cache,
                           cik=args.cik), sort_keys=True))
