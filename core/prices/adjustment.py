from __future__ import annotations

from dataclasses import replace

from core.prices.models import AdjustmentStatus, SourcePriceBar, SplitEvent
from core.prices.policy import PriceSourceMixingError


def split_adjust_raw_close(
    bars: list[SourcePriceBar], splits: list[SplitEvent]
) -> list[SourcePriceBar]:
    """Create split-adjusted closes from one provider's raw series.

    Cross-provider actions are deliberately rejected. Dividends are not applied because
    S15.3 forward-magnitude labels are price-multiple labels, not total-return labels.
    """
    if not bars:
        return []
    source_keys = {(b.source, b.source_symbol) for b in bars}
    if len(source_keys) != 1:
        raise PriceSourceMixingError("Cannot normalize a mixed provider price series")
    source, symbol = next(iter(source_keys))
    if any((s.source, s.source_symbol) != (source, symbol) for s in splits):
        raise PriceSourceMixingError("Cannot apply corporate actions from a different provider")

    ordered_splits = sorted(splits, key=lambda x: x.execution_date)
    out: list[SourcePriceBar] = []
    for bar in bars:
        factor = 1.0
        for split in ordered_splits:
            if bar.trade_date < split.execution_date:
                factor *= split.split_from / split.split_to
        out.append(replace(
            bar,
            adjusted_close=bar.raw_close * factor,
            adjustment_status=AdjustmentStatus.PROVIDER_ADJUSTED,
        ))
    return out
