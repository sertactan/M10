"""Private stdio MCP transport for Secure MCP Tunnel. No HTTP listener, no OAuth page.
Preserves existing read-only YFinance provider and non-PIT data labels.
"""
from mcp.server.fastmcp import FastMCP
from yfinance_readonly import invoke

mcp = FastMCP("meridyen-yfinance-tunnel-stdio")

def _clip_history(data, limit):
    if data.get("status") == "OK_UNOFFICIAL_HISTORICAL":
        data = dict(data)
        data["bars"] = data["bars"][-limit:]
        data["returned_bars"] = len(data["bars"])
        data["truncated"] = data.get("bar_count", 0) > len(data["bars"])
        data["point_in_time_canonical"] = False
    return data

@mcp.tool()
def get_stock_quote(symbol: str) -> dict:
    """Unofficial most recent DAILY price bar, not a verified real-time trade."""
    return invoke("quote", symbol=symbol)

@mcp.tool()
def get_company_overview(symbol: str) -> dict:
    """Read-only Yahoo company metadata."""
    return invoke("overview", symbol=symbol)

@mcp.tool()
def get_time_series_daily(symbol: str, outputsize: str = "compact") -> dict:
    """Non-PIT OHLCV: compact <=120 bars, full <=500 bars."""
    if outputsize not in ("compact", "full"):
        return {"status": "INVALID_OUTPUTSIZE"}
    return _clip_history(invoke("history", symbol=symbol,
                                period="3mo" if outputsize=="compact" else "2y"),
                          120 if outputsize=="compact" else 500)

@mcp.tool()
def search_symbol(keywords: str) -> dict:
    """Unofficial Yahoo symbol search; not a complete market universe."""
    return invoke("search", query=keywords)

@mcp.tool()
def get_recommendations(symbol: str) -> dict:
    """Read-only Yahoo recommendations, no verified consensus vintage."""
    return invoke("recommendations", symbol=symbol)

@mcp.tool()
def get_insider_transactions(symbol: str) -> dict:
    """Unofficial insider data; verify individual trades using SEC Form 4."""
    return invoke("insider", symbol=symbol)

if __name__ == "__main__":
    mcp.run(transport="stdio")
