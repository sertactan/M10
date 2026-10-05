from __future__ import annotations

from datetime import date

from core.contracts.entities import Security
from core.prices.policy import DEFAULT_PROVIDER_PRIORITY, PriceSelectionPolicy, PriceSourceMixingError
from core.prices.validation import compare_adjusted_close
from data.repositories.price_repository import PriceRepository


class HistoricalPriceEngine:
    def __init__(self, repository: PriceRepository, providers: dict[str, object]) -> None:
        self.repository = repository
        self.providers = providers
        self.policy = PriceSelectionPolicy()

    async def sync_history(
        self,
        security: Security,
        start: date,
        end: date,
        *,
        require_adjusted: bool = True,
        provider: str = "AUTO",
        validate_with_fallback: bool = True,
    ):
        order = (provider.upper(),) if provider.upper() != "AUTO" else DEFAULT_PROVIDER_PRIORITY
        downloaded = []
        selection = None

        for name in order:
            p = self.providers.get(name)
            if p is None or getattr(p, "configured", True) is False:
                continue
            try:
                if not await p.validate_symbol(security):
                    continue
                bars = list(await p.get_history(security, start, end))
            except Exception:
                continue
            if not bars:
                continue
            self.policy.assert_single_source(bars)
            descriptor = self.repository.save_series(bars)
            downloaded.append(descriptor)
            try:
                selection = self.policy.select(
                    downloaded, require_adjusted=require_adjusted, authoritative=True
                )
                break
            except PriceSourceMixingError:
                continue

        if selection is None:
            raise PriceSourceMixingError(
                "No authoritative single-provider series satisfies this price request"
            )

        self.repository.select_series(
            security_id=security.security_id,
            start=start,
            end=end,
            source=selection.source,
            source_symbol=selection.source_symbol,
            purpose="BACKTEST_ADJUSTED" if require_adjusted else "RAW_BOOTSTRAP",
            reason=selection.reason,
        )

        if validate_with_fallback:
            await self._validate_selected_with_fallback(
                security, start, end, selection.source, selection.source_symbol
            )
        return selection

    async def _validate_selected_with_fallback(
        self,
        security: Security,
        start: date,
        end: date,
        selected_source: str,
        selected_source_symbol: str,
    ) -> None:
        # Validation is intentionally separate from selection: no rows are stitched.
        candidates = ["YAHOO_COMPAT", "SIMFIN", "MARKETPARQUET", "STOOQ"]
        other_descriptor = None
        for name in candidates:
            if name == selected_source:
                continue
            p = self.providers.get(name)
            if p is None or getattr(p, "configured", True) is False:
                continue
            try:
                if not await p.validate_symbol(security):
                    continue
                bars = list(await p.get_history(security, start, end))
                if not bars:
                    continue
                self.policy.assert_single_source(bars)
                other_descriptor = self.repository.save_series(bars)
                break
            except Exception:
                continue
        if other_descriptor is None:
            return

        try:
            fa = self.repository.parquet.read_bars(
                security_id=security.security_id,
                source=selected_source,
                source_symbol=selected_source_symbol,
                start_date=start,
                end_date=end,
            )
            fb = self.repository.parquet.read_bars(
                security_id=security.security_id,
                source=other_descriptor.source,
                source_symbol=other_descriptor.source_symbol,
                start_date=start,
                end_date=end,
            )
            from core.prices.models import AdjustmentStatus, PriceQualityStatus, SourcePriceBar
            import pandas as pd

            def convert(frame):
                rows=[]
                for _,r in frame.iterrows():
                    rows.append(SourcePriceBar(
                        security_id=str(r.security_id),source=str(r.source),source_symbol=str(r.source_symbol),
                        trade_date=date.fromisoformat(str(r.trade_date)[:10]),open=float(r.open),high=float(r.high),low=float(r.low),
                        raw_close=float(r.raw_close),adjusted_close=float(r.adjusted_close),volume=float(r.volume),
                        retrieved_at=pd.Timestamp(r.retrieved_at).to_pydatetime(),
                        quality_status=PriceQualityStatus(str(r.quality_status)),adjustment_status=AdjustmentStatus(str(r.adjustment_status)),
                        vwap=float(r.vwap) if pd.notna(r.vwap) else None,raw_payload_hash=None if pd.isna(r.raw_payload_hash) else str(r.raw_payload_hash),
                    ))
                return rows

            result=compare_adjusted_close(convert(fa),convert(fb))
            self.repository.save_validation(
                security_id=security.security_id,start=start,end=end,
                source_a=selected_source,source_b=other_descriptor.source,**result
            )
        except Exception:
            # Validation failure never mutates the selected source.
            return
