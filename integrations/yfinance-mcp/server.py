"""Meridyen YFinance READ-ONLY Streamable HTTP MCP server on Render Free.
Six Yahoo research tools. Unofficial DAILY quotes; no PIT, orders, or canonical scores.
Public anonymous endpoint with per-process rate limiter, not a secure private service.
"""
import contextlib
import threading
import time
from collections import defaultdict, deque

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Mount, Route
from yfinance_readonly import invoke
from oauth_gate import OAUTH_ROUTES, OAuthGate

mcp = FastMCP(
    "meridyen-yfinance-readonly",
    host="0.0.0.0",
    stateless_http=True,
    json_response=True
)

def _bounded_history(data, max_bars):
    if data.get("status") == "OK_UNOFFICIAL_HISTORICAL":
        data = dict(data)
        data["bars"] = data["bars"][-max_bars:]
        data["returned_bars"] = len(data["bars"])
        data["truncated"] = data["bar_count"] > len(data["bars"])
        data["point_in_time_canonical"] = False
    return data

@mcp.tool(meta={"securitySchemes": [{"type": "oauth2", "scopes": ["yfinance:read"]}]})
def get_stock_quote(symbol: str) -> dict:
    """Read unofficial most recent DAILY bar. Not verified real-time."""
    return invoke("quote", symbol=symbol)

@mcp.tool(meta={"securitySchemes": [{"type": "oauth2", "scopes": ["yfinance:read"]}]})
def get_company_overview(symbol: str) -> dict:
    """Unofficial public company profile and selected financial metrics."""
    return invoke("overview", symbol=symbol)

@mcp.tool(meta={"securitySchemes": [{"type": "oauth2", "scopes": ["yfinance:read"]}]})
def get_time_series_daily(symbol: str, outputsize: str = "compact") -> dict:
    """Non-PIT daily OHLCV. compact up to 120, full up to 500 bars."""
    if outputsize not in ("compact", "full"):
        return {"status": "INVALID_OUTPUTSIZE", "allowed": ["compact", "full"]}
    period = "3mo" if outputsize == "compact" else "2y"
    return _bounded_history(invoke("history", symbol=symbol, period=period),
                            120 if outputsize == "compact" else 500)

@mcp.tool(meta={"securitySchemes": [{"type": "oauth2", "scopes": ["yfinance:read"]}]})
def search_symbol(keywords: str) -> dict:
    """Unofficial Yahoo symbol search; not an exchange universe listing."""
    return invoke("search", query=keywords)

@mcp.tool(meta={"securitySchemes": [{"type": "oauth2", "scopes": ["yfinance:read"]}]})
def get_recommendations(symbol: str) -> dict:
    """Unofficial analyst recommendations; historical vintage not verified."""
    return invoke("recommendations", symbol=symbol)

@mcp.tool(meta={"securitySchemes": [{"type": "oauth2", "scopes": ["yfinance:read"]}]})
def get_insider_transactions(symbol: str) -> dict:
    """Unofficial insider transactions; verify SEC Forms 4 independently."""
    return invoke("insider", symbol=symbol)

async def health(request):
    return JSONResponse({
        "status": "ready", "transport": "streamable-http", "tools": 6,
        "public_anonymous": False, "oauth_required": True, "live_yahoo_tested": False,
        "point_in_time_canonical": False
    })

async def root(request):
    return PlainTextResponse("Meridyen YFinance MCP. Connect your MCP client to /mcp.\n")

class SimpleRateLimit:
    """Best-effort per-process cap; no authentication or DDoS protection."""
    def __init__(self, app, limit=20, period=60):
        self.app = app
        self.limit, self.period = limit, period
        self.clients = defaultdict(deque)
        self.lock = threading.Lock()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path", "").rstrip("/") != "/mcp":
            return await self.app(scope, receive, send)
        key = str((scope.get("client") or ("unknown", 0))[0])
        now = time.monotonic()
        with self.lock:
            hits = self.clients[key]
            while hits and hits[0] < now - self.period:
                hits.popleft()
            denied = len(hits) >= self.limit
            if not denied:
                hits.append(now)
        if denied:
            return await PlainTextResponse(
                "Rate limit exceeded", status_code=429, headers={"Retry-After": "60"}
            )(scope, receive, send)
        return await self.app(scope, receive, send)

@contextlib.asynccontextmanager
async def lifespan(app):
    async with mcp.session_manager.run():
        yield

app = Starlette(
    routes=OAUTH_ROUTES + [
        Route("/health", endpoint=health),
        Route("/", endpoint=root),
        Mount("/", app=mcp.streamable_http_app()),
    ],
    lifespan=lifespan,
)
app = OAuthGate(SimpleRateLimit(app))
