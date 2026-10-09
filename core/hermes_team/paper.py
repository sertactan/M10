"""Deterministic paper-position preview only, NEVER a broker order or a backtest."""
from __future__ import annotations

import math
from datetime import datetime


def preview_paper_position(case: dict) -> dict:
    """Use operator-supplied *scenario* assumptions; don't infer live evidence.

    Explicit spread/slippage/fees are included. An unverified price cannot be
    advertised as the current market or as a canonical M10 signal.
    """
    base = {"status": "NO_TRADE", "mode": "SYNTHETIC_SCENARIO_ONLY",
            "live_order_allowed": False, "canonical_signal": False,
            "source_validated": False}
    if not isinstance(case, dict) or set(case) - {
        "symbol", "as_of", "price", "stop", "capital",
        "risk_fraction", "spread_fraction", "slippage_fraction", "fee_usd",
    }:
        return {**base, "reason": "INVALID_INPUT_SCHEMA"}
    try:
        symbol = case["symbol"]
        if not isinstance(symbol, str) or not symbol.isascii() or not symbol.isalnum():
            raise ValueError("symbol")
        when = datetime.fromisoformat(str(case["as_of"]).replace("Z", "+00:00"))
        if when.tzinfo is None:
            raise ValueError("naive as-of")
        keys = ("price", "stop", "capital", "risk_fraction",
                "spread_fraction", "slippage_fraction", "fee_usd")
        values = {k: case[k] for k in keys}
        if any(type(x) not in (int, float) or not math.isfinite(x)
               for x in values.values()):
            raise ValueError("nonfinite")
        price, stop, capital = (float(values[k]) for k in ("price", "stop", "capital"))
        risk = values["risk_fraction"]
        spread, slip, fee = (values[k] for k in
                             ("spread_fraction", "slippage_fraction", "fee_usd"))
        if not (0 < stop < price and price > 0 and capital > 0
                and 0 < risk <= 0.005 and 0 <= spread <= 0.03
                and 0 <= slip <= 0.03 and 0 <= fee <= 100):
            raise ValueError("unsafe prices/risk")
        fill = price * (1 + spread / 2 + slip)
        stop_fill = stop * (1 - spread / 2 - slip)
        risk_per_share = fill - stop_fill
        if risk_per_share <= 0:
            raise ValueError("bad risk")
        # Bound both risk and concentration. No margin/leverage.
        qty = math.floor(min((capital * risk - 2 * fee) / risk_per_share,
                             (capital * 0.10 - fee) / fill))
        if qty < 1:
            return {**base, "reason": "INSUFFICIENT_SIZE_AFTER_COSTS"}
        stop_loss = round(qty * risk_per_share + 2 * fee, 2)
        if stop_loss > capital * risk + 1e-7:
            return {**base, "reason": "RISK_LIMIT"}
        return {**base, "status": "PAPER_PREVIEW_ONLY", "reason": "SCENARIO_NOT_REAL_MARKET",
                "symbol": symbol.upper(), "as_of": when.isoformat(),
                "currency": "USD", "quantity": qty,
                "scenario_entry_fill": round(fill, 4),
                "scenario_stop_fill": round(stop_fill, 4),
                "max_estimated_loss_usd": stop_loss,
                "max_position_fraction": 0.10,
                "per_trade_risk_fraction_limit": 0.005,
                "broker_request_created": False}
    except (KeyError, ValueError, TypeError, OverflowError):
        return {**base, "reason": "INVALID_OR_UNSAFE_SCENARIO"}
