from __future__ import annotations

from dataclasses import dataclass

from core.prices.models import AdjustmentStatus, PriceSeriesDescriptor


DEFAULT_PROVIDER_PRIORITY = (
    "MASSIVE",
    "STOOQ",
    "SIMFIN",
    "YAHOO_COMPAT",
    "MARKETPARQUET",
)


class PriceSourceMixingError(RuntimeError):
    pass


@dataclass(frozen=True)
class PriceSelection:
    source: str
    source_symbol: str
    reason: str


class PriceSelectionPolicy:
    """Select one complete provider series for a requested window.

    This class intentionally never stitches missing dates from another provider.
    Cross-provider data may be compared for validation, but not silently blended.
    """

    def __init__(self, priority: tuple[str, ...] = DEFAULT_PROVIDER_PRIORITY) -> None:
        self.priority = priority

    def select(
        self,
        series: list[PriceSeriesDescriptor],
        *,
        require_adjusted: bool = True,
        authoritative: bool = True,
    ) -> PriceSelection:
        if not series:
            raise PriceSourceMixingError("No provider series available")
        rank = {name: i for i, name in enumerate(self.priority)}
        candidates = sorted(series, key=lambda s: (rank.get(s.source, 999), -s.row_count))
        for item in candidates:
            if authoritative and item.quality_status.value == "FALLBACK_ONLY":
                continue
            if require_adjusted and item.adjustment_status in {
                AdjustmentStatus.RAW_ONLY,
                AdjustmentStatus.UNKNOWN,
            }:
                continue
            return PriceSelection(
                source=item.source,
                source_symbol=item.source_symbol,
                reason=f"single-provider selection by priority ({item.source})",
            )
        raise PriceSourceMixingError(
            "No eligible single-provider series is available; refusing fallback-only authority or cross-provider stitching"
        )

    @staticmethod
    def assert_single_source(bars: list) -> None:
        keys = {(bar.source, bar.source_symbol) for bar in bars}
        if len(keys) > 1:
            raise PriceSourceMixingError(
                f"Historical price window contains multiple source series: {sorted(keys)}"
            )
