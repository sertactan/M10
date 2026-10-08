"""Keyless, read-only Yahoo/yfinance adapter for Meridyen. Unofficial and non-PIT."""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone

SOURCE = "YFINANCE_YAHOO_UNOFFICIAL"
SYMBOL_RE = re.compile(r"^[A-Za-z0-9^][A-Za-z0-9.^_\-=]{0,31}$")

def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def symbol_check(symbol):
    if not isinstance(symbol, str) or not SYMBOL_RE.fullmatch(symbol):
        raise ValueError("invalid_symbol")
    return symbol.upper()

def safe_number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None

def scalar(value):
    if value is None:
        return None
    if isinstance(value, (str, bool, int)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    result = safe_number(value)
    return result if result is not None else str(value)

def empty_frame(frame):
    return frame is None or bool(getattr(frame, "empty", True))

def _yf():
    import yfinance
    return yfinance

def quote(symbol, yf=None):
    symbol = symbol_check(symbol)
    yf = yf or _yf()
    ticker = yf.Ticker(symbol)
    frame = ticker.history(period="5d", interval="1d", auto_adjust=False)
    if empty_frame(frame):
        return {"status": "DATA_UNAVAILABLE", "symbol": symbol, "source": SOURCE}
    row = frame.iloc[-1]
    price = safe_number(row.get("Close"))
    return {
        "status": "OK_UNOFFICIAL_DAILY_BAR" if price is not None else "DATA_UNAVAILABLE",
        "symbol": symbol, "price": price, "volume": safe_number(row.get("Volume")),
        "bar_date": scalar(frame.index[-1]), "source": SOURCE,
        "retrieved_at_utc": utc_now(), "real_time_verified": False,
        "note": "Daily bar, potentially delayed; retrieval UTC is not exchange time."
    }

def overview(symbol, yf=None):
    symbol = symbol_check(symbol)
    yf = yf or _yf()
    info = yf.Ticker(symbol).info or {}
    names = {
        "name": "longName", "sector": "sector", "industry": "industry",
        "currency": "currency", "exchange": "exchange", "market_cap": "marketCap",
        "trailing_pe": "trailingPE", "forward_pe": "forwardPE",
        "dividend_yield": "dividendYield",
        "fifty_two_week_high": "fiftyTwoWeekHigh",
        "fifty_two_week_low": "fiftyTwoWeekLow"
    }
    metrics = {dst: scalar(info.get(src)) for dst, src in names.items()}
    return {
        "status": "OK_UNOFFICIAL" if any(v is not None for v in metrics.values()) else "DATA_UNAVAILABLE",
        "symbol": symbol, "metrics": metrics, "source": SOURCE,
        "retrieved_at_utc": utc_now()
    }

def history(symbol, period="3mo", yf=None):
    symbol = symbol_check(symbol)
    if period not in {"5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "20y", "max"}:
        raise ValueError("invalid_period")
    yf = yf or _yf()
    frame = yf.Ticker(symbol).history(
        period=period, interval="1d", auto_adjust=False, actions=True
    )
    if empty_frame(frame):
        return {"status": "DATA_UNAVAILABLE", "symbol": symbol, "source": SOURCE, "bars": []}
    bars = []
    for when, row in frame.iterrows():
        bars.append({
            "date": scalar(when), "symbol": symbol,
            "open": safe_number(row.get("Open")), "high": safe_number(row.get("High")),
            "low": safe_number(row.get("Low")), "close": safe_number(row.get("Close")),
            "adj_close": safe_number(row.get("Adj Close")),
            "volume": safe_number(row.get("Volume")),
            "dividends": safe_number(row.get("Dividends")),
            "splits": safe_number(row.get("Stock Splits"))
        })
    return {
        "status": "OK_UNOFFICIAL_HISTORICAL", "symbol": symbol,
        "source": SOURCE, "retrieved_at_utc": utc_now(), "period": period,
        "bar_count": len(bars), "retrospective_adjustment": True,
        "point_in_time_canonical": False, "bars": bars
    }

def search(query, yf=None):
    if not isinstance(query, str) or not query.strip() or len(query) > 100:
        raise ValueError("invalid_search_query")
    yf = yf or _yf()
    if not hasattr(yf, "Search"):
        return {"status": "SEARCH_NOT_SUPPORTED", "source": SOURCE, "matches": []}
    result = yf.Search(query, max_results=10)
    matches = [
        {"symbol": item.get("symbol"), "name": item.get("shortname") or item.get("longname"),
         "type": item.get("quoteType"), "exchange": item.get("exchange")}
        for item in (getattr(result, "quotes", None) or [])
    ]
    return {"status": "OK_UNOFFICIAL_SEARCH", "source": SOURCE,
            "retrieved_at_utc": utc_now(), "matches": matches}

def recs(symbol, yf=None):
    symbol = symbol_check(symbol)
    yf = yf or _yf()
    frame = yf.Ticker(symbol).recommendations
    if empty_frame(frame):
        return {"status": "DATA_UNAVAILABLE", "symbol": symbol, "source": SOURCE,
                "recommendations": []}
    columns = ("strongBuy", "buy", "hold", "sell", "strongSell")
    values = [
        {"period": scalar(when), **{c: safe_number(row.get(c)) for c in columns}}
        for when, row in frame.iterrows()
    ]
    return {"status": "OK_UNOFFICIAL_RECOMMENDATIONS", "symbol": symbol,
            "source": SOURCE, "recommendations": values,
            "consensus_vintage_verified": False, "retrieved_at_utc": utc_now()}

def insider(symbol, yf=None):
    symbol = symbol_check(symbol)
    yf = yf or _yf()
    frame = yf.Ticker(symbol).insider_transactions
    if empty_frame(frame):
        return {"status": "DATA_UNAVAILABLE", "symbol": symbol, "source": SOURCE,
                "transactions": []}
    entries = [
        {"index": scalar(index),
         "fields": {str(k): scalar(v) for k, v in row.items()}}
        for index, row in frame.iterrows()
    ]
    return {"status": "OK_UNOFFICIAL_INSIDER", "symbol": symbol, "source": SOURCE,
            "transactions": entries, "sec_form4_verified": False,
            "retrieved_at_utc": utc_now()}

def invoke(command, symbol=None, period=None, query=None, yf=None):
    methods = {
        "quote": lambda: quote(symbol, yf),
        "overview": lambda: overview(symbol, yf),
        "history": lambda: history(symbol, period or "3mo", yf),
        "search": lambda: search(query, yf),
        "recommendations": lambda: recs(symbol, yf),
        "insider": lambda: insider(symbol, yf),
    }
    try:
        if command not in methods:
            raise ValueError("unknown_command")
        return methods[command]()
    except Exception as exc:
        return {"status": "DATA_UNAVAILABLE_OR_INVALID_INPUT", "command": command,
                "symbol": symbol, "error": str(exc)[:240], "source": SOURCE,
                "retrieved_at_utc": utc_now(), "canonical_ready": False}
