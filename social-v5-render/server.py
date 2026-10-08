"""Render Free MCP sidecar for the unchanged Social V5 FREE research engine.

Read-only and noncanonical. No trade/broker calls, paid APIs, databases,
background polling, authentication credentials, or model modifications.
"""
import datetime as dt
import json
import os
import threading
import time
from collections import deque
from pathlib import Path
import sys

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse
from starlette.routing import Route

sys.path.insert(0, str(Path(__file__).resolve().parent))
import social_v5_free as core

_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME", "meridyen-social-v5-free.onrender.com")
_security = TransportSecuritySettings(
    allowed_hosts=[_HOST, _HOST + ":*", "localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*"],
    allowed_origins=[],
)
mcp = FastMCP(
    "Meridyen Social V5 FREE",
    instructions=(
        "Only public Bluesky and allowlisted Mastodon one-shot GET. Never assume "
        "whole-market coverage. Social indicators are RESEARCH_NONCANONICAL_SOCIAL_V5; "
        "S15/S16/S16-EA stay frozen, scores unavailable without separate canonical inputs."
    ),
    stateless_http=True,
    json_response=True,
    transport_security=_security,
)

# One global egress budget protects a public no-auth free service from abuse.
# No scheduled or background collection is performed.
_lock = threading.Lock()
_calls = deque()
_cache = {}
_MAX_PER_HOUR = 24
_CACHE_SECONDS = 180


def _guarded_collect(key, collector):
    now = time.monotonic()
    with _lock:
        cached = _cache.get(key)
        if cached and now - cached[0] <= _CACHE_SECONDS:
            return cached[1]
        while _calls and now - _calls[0] > 3600:
            _calls.popleft()
        if len(_calls) >= _MAX_PER_HOUR:
            return {"status": "RATE_LIMIT_FREE", "reason": "Global 24 public requests/hour cap"}, []
        _calls.append(now)
    try:
        rows = collector()
    except Exception as exc:
        # No paid fallbacks, no retries, no fabricated observations.
        return {"status": "PUBLIC_SOURCE_UNAVAILABLE", "reason": str(exc)[:250]}, []
    result = {"status": "OK", "captured": len(rows)}, rows
    with _lock:
        _cache[key] = (now, result)
        if len(_cache) > 100:
            _cache.clear()
    return result


def _bluesky_public_appview_get(url):
    """Keyless Bluesky search through api.bsky.app when cached public host denies it.

    Strict URL allowlist, HTTPS only, no redirect, no credentials, <=2 MB response.
    The immutable Social V5 parsing/validation remains core.collect_bluesky.
    """
    prefix = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?"
    if not url.startswith(prefix):
        raise ValueError("Bluesky endpoint rejected by allowlist")
    from urllib.request import Request, build_opener
    target = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?" + url[len(prefix):]
    req = Request(target, headers={
        "User-Agent": "MeridyenSocialV5Free/0.26.0 (+research; no automation)",
        "Accept": "application/json",
    })
    with build_opener(core._NoRedirect()).open(req, timeout=8) as res:
        if res.status != 200:
            raise RuntimeError(f"Bluesky API HTTP {res.status}")
        raw = res.read(core.LIMIT_BYTES + 1)
        if len(raw) > core.LIMIT_BYTES:
            raise ValueError("Bluesky response too large")
        return json.loads(raw.decode("utf-8"))


def _collect_bluesky(ticker, limit):
    return core.collect_bluesky(ticker, limit=limit, fetch=_bluesky_public_appview_get)


def _safe_rows(rows):
    # Public information only, bounded; no raw author IDs.
    return [
        {k: p[k] for k in ("platform", "source_id", "created_at",
                           "observed_at", "ticker", "text", "source_url",
                           "capture_proof", "engagement")}
        for p in rows
    ]


@mcp.tool()
def social_status() -> dict:
    """Report true Social V5 capability status, free-only constraints, and source availability."""
    s = core.status()
    s.update({
        "remote_mcp_tool_server": True,
        "collector_executed": False,
        "source_health": "not tested until a one-shot tool call",
        "max_public_outbound_requests_per_hour": _MAX_PER_HOUR,
        "local_storage": "ephemeral in-memory 180-second cache",
        "authentication": "public read-only; global egress limiter",
        "s15_s16": "READ_ONLY_UNCHANGED",
    })
    return s


@mcp.tool()
def social_bluesky(ticker: str, limit: int = 15) -> dict:
    """Fetch up to 15 current public Bluesky cashtag posts once; source coverage is incomplete."""
    ticker = core.valid_symbol(ticker)
    limit = max(1, min(int(limit), 15))
    meta, rows = _guarded_collect(("bluesky", ticker, limit),
        lambda: _collect_bluesky(ticker, limit))
    return {"module": "MERIDYEN_SOCIAL_V5_FREE", "source": "bluesky",
            "ticker": ticker, **meta, "posts": _safe_rows(rows),
            "canonical_status": "UNCHANGED_UNCOMPUTED"}


@mcp.tool()
def social_mastodon(ticker: str, hashtag: str = "stocks", limit: int = 15) -> dict:
    """Read a public Mastodon hashtag timeline once; this is not whole-platform search."""
    ticker = core.valid_symbol(ticker)
    if not isinstance(hashtag, str) or len(hashtag) > 35 or not hashtag.replace("_", "").isalnum():
        raise ValueError("invalid hashtag")
    limit = max(1, min(int(limit), 15))
    meta, rows = _guarded_collect(("mastodon", ticker, hashtag, limit),
        lambda: core.collect_mastodon(ticker, "mastodon.social", hashtag, limit))
    return {"module": "MERIDYEN_SOCIAL_V5_FREE", "source": "mastodon.social",
            "ticker": ticker, "hashtag": hashtag, **meta, "posts": _safe_rows(rows),
            "canonical_status": "UNCHANGED_UNCOMPUTED"}


@mcp.tool()
def social_scan(ticker: str) -> dict:
    """One-shot keyless multi-source collection plus noncanonical Social V5 analysis."""
    ticker = core.valid_symbol(ticker)
    b, bp = _guarded_collect(("bluesky", ticker, 15),
        lambda: _collect_bluesky(ticker, 15))
    m, mp = _guarded_collect(("mastodon", ticker, "stocks", 15),
        lambda: core.collect_mastodon(ticker, "mastodon.social", "stocks", 15))
    now = core.iso(dt.datetime.now(dt.timezone.utc))
    rows = bp + mp
    # No invented baseline: recent public search != verified historical coverage.
    result = core.analyze(rows, ticker, now)
    result["source_status"] = {"bluesky": b, "mastodon": m}
    result["posts"] = _safe_rows(rows)
    result["pit_status"] = "CAPTURED_NOW_ONLY_NO_VERIFIED_HISTORICAL_BASELINE"
    result["s16_e_status"] = "NOT_AVAILABLE"
    result["s16_c_status"] = "NOT_AVAILABLE"
    result["is_trade_signal"] = False
    return result


async def _health(request):
    return JSONResponse({
        "service": "meridyen-social-v5-free", "healthy": True,
        "data_status": "not checked", "paid_api_budget_usd": 0,
        "s15_s16": "READ_ONLY_UNCHANGED",
    })


app = mcp.streamable_http_app()
app.router.routes.append(Route("/health", endpoint=_health, methods=["GET"]))
