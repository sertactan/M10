"""Authenticated read-only OpenBB V5 FREE MCP sidecar; never alters M10."""
import asyncio
import hmac
import os
import re
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from importlib.metadata import PackageNotFoundError, version
from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Mount, Route

NAME = "Meridyen OpenBB V5 FREE"
mcp = FastMCP(NAME)
PROBE = {"status": "NOT_RUN", "symbol": "SPY", "provider": "cboe"}
PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")

def _get_history(provider, symbol, start_date, end_date):
    symbol = symbol.strip().upper()
    if not PATTERN.fullmatch(symbol):
        raise ValueError("INVALID_SYMBOL")
    try:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    except (TypeError, ValueError) as exc:
        raise ValueError("INVALID_ISO_DATES") from exc
    if not start <= end <= date.today() or (end - start).days > 93:
        raise ValueError("INVALID_DATE_WINDOW")
    if provider not in ("cboe", "nasdaq"):
        raise ValueError("PROVIDER_NOT_ALLOWED")
    from openbb import obb
    if provider == "cboe":
        result = obb.cboe.equity.historical(
            symbol=symbol, start_date=start_date, end_date=end_date, provider="cboe")
        command = "obb.cboe.equity.historical"
    elif symbol == "SPY":
        result = obb.nasdaq.etf.historical(
            symbol=symbol, start_date=start_date, end_date=end_date, provider="nasdaq")
        command = "obb.nasdaq.etf.historical"
    else:
        result = obb.nasdaq.equity.historical(
            symbol=symbol, start_date=start_date, end_date=end_date, provider="nasdaq")
        command = "obb.nasdaq.equity.historical"
    rows = getattr(result, "results", None) or []
    bars = []
    for row in rows[:65]:
        item = row.model_dump(mode="json") if hasattr(row, "model_dump") else (
            row.dict() if hasattr(row, "dict") else {})
        bars.append({k: item.get(k) for k in ("date", "open", "high", "low", "close", "volume")})
    return {
        "status": "UPSTREAM_FETCH_VERIFIED" if bars else "OPENBB_FREE_BLOCKED_NO_DATA",
        "symbol": symbol, "provider": "openbb." + provider, "source_command": command,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "currency": "USD_UNVERIFIED", "adjusted": "unknown",
        "pit_valid": False, "canonical_eligible": False,
        "dataset_role": "NONCANONICAL_RESEARCH_ONLY",
        "bar_count": len(bars), "bars": bars,
        "note": "Source vintage and price adjustment unverified. No S15/S16 score computed.",
    }

def _safe_history(provider, symbol, start_date, end_date):
    try:
        return _get_history(provider, symbol, start_date, end_date)
    except Exception as exc:
        return {"status": "OPENBB_FREE_BLOCKED", "provider": provider, "symbol": symbol,
                "error_type": type(exc).__name__, "error": str(exc)[:240],
                "canonical_eligible": False}

@mcp.tool()
def openbb_status() -> dict:
    """OpenBB V5 installed package inventory and evidence-based SPY probe status."""
    packages = {}
    for name in ("openbb-core", "openbb-cboe", "openbb-nasdaq", "openbb-sec"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = "NOT_INSTALLED"
    return {"module": NAME, "packages": packages, "paid_api_budget_usd": 0,
            "read_only": True, "canonical_integration": False, "spy_probe": dict(PROBE)}

@mcp.tool()
def openbb_history(symbol: str = "SPY", start_date: str = "2026-09-01",
                   end_date: str = "2026-09-30", provider: str = "cboe") -> dict:
    """Actual keyless OpenBB V5 Cboe/Nasdaq daily bars (max 93 days), noncanonical."""
    return _safe_history(provider, symbol, start_date, end_date)

@mcp.tool()
def openbb_spy_test() -> dict:
    """Execute an actual Cboe historical-bar fetch for SPY without synthetic prices."""
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=12)
    return _safe_history("cboe", "SPY", start.isoformat(), end.isoformat())

async def healthz(_request: Request):
    tools = await mcp.get_tools()
    return JSONResponse({"service": NAME, "status": "READY", "mcp_path": "/mcp",
                         "registered_tools": sorted(tools.keys()),
                         "upstream_spy_probe": dict(PROBE)})

async def _probe():
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=12)
    value = await asyncio.to_thread(_safe_history, "cboe", "SPY", start.isoformat(), end.isoformat())
    PROBE.update({"status": value.get("status", "OPENBB_FREE_BLOCKED"),
                  "checked_at": datetime.now(timezone.utc).isoformat(),
                  "bar_count": value.get("bar_count", 0),
                  "last_bar_date": (value.get("bars") or [{}])[-1].get("date"),
                  "error_type": value.get("error_type"), "error": value.get("error")})

mcp_app = mcp.http_app(path="/mcp", stateless_http=True)

@asynccontextmanager
async def lifespan(app):
    async with mcp_app.lifespan(app):
        asyncio.create_task(_probe())
        yield

base_app = Starlette(routes=[Route("/healthz", healthz), Mount("/", app=mcp_app)],
                     lifespan=lifespan)

class BearerGate:
    def __init__(self, application):
        self.application = application
        self.token = os.environ.get("MERIDYEN_MCP_BEARER_TOKEN", "")
        if len(self.token) < 32:
            raise RuntimeError("MERIDYEN_MCP_BEARER_TOKEN missing: fail closed")
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path", "").startswith("/mcp"):
            authorization = dict(scope.get("headers", [])).get(b"authorization", b"")
            expected = ("Bearer " + self.token).encode()
            if not hmac.compare_digest(authorization, expected):
                response = PlainTextResponse("Unauthorized", status_code=401,
                                             headers={"WWW-Authenticate": "Bearer"})
                await response(scope, receive, send)
                return
        await self.application(scope, receive, send)

app = BearerGate(base_app)
