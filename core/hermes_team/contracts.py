"""No-inference financial evidence contracts for Hermes and ChatGPT plugin."""
from __future__ import annotations

from datetime import datetime
import math
from typing import Any


def financial_result(payload: dict[str, Any], *, canonical_trusted: bool = False,
                     estimated_trusted: bool = False) -> dict[str, Any]:
    """Scores require a trusted local formula caller, not JSON assertion flags."""
    ticker = str(payload.get("symbol") or "").upper().strip()
    price = payload.get("price")
    as_of = payload.get("price_timestamp")
    sources = payload.get("sources") or []
    canonical = payload.get("s16_c")
    estimated = payload.get("s16_e")
    approved_evidence = payload.get("canonical_evidence_verified") is True
    timestamp_ok = False
    try:
        dt = datetime.fromisoformat(str(as_of).replace("Z", "+00:00"))
        timestamp_ok = dt.tzinfo is not None
    except (ValueError, TypeError):
        pass
    price_ok = (type(price) in (int, float)
                and math.isfinite(price) and price > 0)
    provenance_ok = isinstance(sources, list) and all(
        isinstance(s, dict) and s.get("source") and s.get("retrieved_at")
        and s.get("available_at") and s.get("source_ref") for s in sources
    ) and bool(sources)
    ready = bool(ticker and ticker.isascii() and ticker.replace(".", "").isalnum()
                 and price_ok and timestamp_ok and provenance_ok)
    canonical_ready = ready and canonical_trusted and approved_evidence and isinstance(
        canonical, (int, float)
    ) and not isinstance(canonical, bool) and math.isfinite(canonical) and 0 <= canonical <= 100
    estimated_ready = (ready and estimated_trusted and type(estimated) in (int, float)
                       and math.isfinite(estimated) and 0 <= estimated <= 100)
    return {
        "schema": "MERIDYEN_HERMES_FINANCIAL_V1",
        "symbol": ticker or None,
        "price": price if ready else None,
        "price_timestamp": as_of if ready else None,
        "s16_e": estimated if estimated_ready else None,
        "s16_e_status": "ESTIMATED" if estimated_ready else "INCONCLUSIVE",
        "s16_c": canonical if canonical_ready else None,
        "s16_c_status": "CANONICAL" if canonical_ready else "INCONCLUSIVE",
        "decision": "RESEARCH_ONLY" if ready else "INCONCLUSIVE",
        "sources": sources if provenance_ok else [],
        "live_trading_enabled": False,
        "model_promotion_allowed": False,
    }
