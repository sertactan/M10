from __future__ import annotations

from dataclasses import dataclass

from core.fundamentals.models import FundamentalFactRow


REGULATORY_SOURCE_PRIORITY = {
    "SEC_EDGAR": 1,
    "FINNHUB": 2,
    "SIMFIN": 3,
    "FMP": 4,
}


@dataclass(frozen=True)
class CanonicalFactChoice:
    fact: FundamentalFactRow
    reason: str


class FundamentalPrecedencePolicy:
    """SEC facts dominate regulatory history. Secondary data never overwrites SEC."""

    def choose_regulatory(
        self,
        facts: list[FundamentalFactRow],
        *,
        allow_secondary_fallback: bool = True,
    ) -> CanonicalFactChoice:
        if not facts:
            raise ValueError("No fundamental facts supplied")
        sec = [f for f in facts if f.source == "SEC_EDGAR"]
        if sec:
            winner = max(sec, key=lambda f: (f.available_at, f.retrieved_at))
            return CanonicalFactChoice(winner, "SEC EDGAR authoritative precedence")
        if not allow_secondary_fallback:
            raise ValueError("SEC fact unavailable and secondary fallback disabled")
        ranked = sorted(
            facts,
            key=lambda f: (
                REGULATORY_SOURCE_PRIORITY.get(f.source, 999),
                -f.available_at.timestamp(),
            ),
        )
        return CanonicalFactChoice(ranked[0], "explicit secondary fallback; SEC unavailable")
