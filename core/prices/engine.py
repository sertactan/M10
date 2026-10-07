from __future__ import annotations

import asyncio
from datetime import date
from time import perf_counter

from core.contracts.entities import Security
from core.data_sync.racing import ProviderRaceResult, race_in_canonical_order
from core.prices.policy import (
    FALLBACK_ONLY_PROVIDER_PRIORITY,
    PriceSelectionPolicy,
    PriceSourceMixingError,
    auto_provider_priority,
)
from core.prices.validation import compare_adjusted_close
from data.repositories.price_repository import PriceRepository
from data.repositories.provider_health_repository import ProviderHealthRepository


VALIDATION_PROVIDER_PRIORITY = (
    "MASSIVE",
    "MARKETPARQUET",
    "SIMFIN",
    "YAHOO_COMPAT",
    "STOOQ",
)


class HistoricalPriceEngine:
    def __init__(
        self,
        repository: PriceRepository,
        providers: dict[str, object],
        health: ProviderHealthRepository | None = None,
        provider_concurrency_limits: dict[str, int] | None = None,
        default_provider_concurrency: int = 2,
    ) -> None:
        self.repository = repository
        self.providers = providers
        self.health = health
        self.policy = PriceSelectionPolicy()
        self.default_provider_concurrency = max(1, int(default_provider_concurrency))
        self.provider_concurrency_limits = {
            name.upper(): max(1, int(limit))
            for name, limit in (provider_concurrency_limits or {}).items()
        }
        self._provider_semaphores: dict[str, asyncio.Semaphore] = {}

    def _provider_order(self, provider: str) -> tuple[str, ...]:
        if provider.upper() != "AUTO":
            return (provider.upper(),)

        static = auto_provider_priority(self.providers)
        if self.health is None:
            return static

        # Health may reorder eligible primary/free providers, but it must never
        # promote fallback-only Yahoo ahead of authoritative candidates.
        fallback_names = set(FALLBACK_ONLY_PROVIDER_PRIORITY)
        eligible = tuple(name for name in static if name not in fallback_names)
        fallback = tuple(name for name in static if name in fallback_names)
        return self.health.rank(eligible) + self.health.rank(fallback)

    def _validation_provider_order(self, selected_source: str) -> tuple[str, ...]:
        candidates = tuple(
            name
            for name in VALIDATION_PROVIDER_PRIORITY
            if name != selected_source
            and self.providers.get(name) is not None
            and getattr(self.providers[name], "configured", True) is not False
        )
        if self.health is None:
            return candidates
        return self.health.rank(candidates)

    def _provider_semaphore(self, name: str) -> asyncio.Semaphore:
        key = name.upper()
        semaphore = self._provider_semaphores.get(key)
        if semaphore is None:
            limit = self.provider_concurrency_limits.get(
                key, self.default_provider_concurrency
            )
            semaphore = asyncio.Semaphore(limit)
            self._provider_semaphores[key] = semaphore
        return semaphore

    async def _probe_history_provider(
        self,
        name: str,
        security: Security,
        start: date,
        end: date,
    ) -> list:
        provider = self.providers[name]
        async with self._provider_semaphore(name):
            started = perf_counter()
            try:
                if not await provider.validate_symbol(security):
                    raise RuntimeError("symbol validation failed")
                bars = list(await provider.get_history(security, start, end))
                if not bars:
                    raise RuntimeError("provider returned no bars")
                if self.health is not None:
                    self.health.record_success(
                        name,
                        latency_ms=(perf_counter() - started) * 1000.0,
                    )
                return bars
            except Exception as exc:
                if self.health is not None:
                    message = str(exc)
                    self.health.record_failure(
                        name,
                        latency_ms=(perf_counter() - started) * 1000.0,
                        rate_limited=("429" in message or "rate limit" in message.lower()),
                        message=message[:500],
                    )
                raise

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
        order = tuple(
            name
            for name in self._provider_order(provider)
            if self.providers.get(name) is not None
            and getattr(self.providers[name], "configured", True) is not False
            and (self.health is None or self.health.can_attempt(name))
        )
        downloaded = []
        selection = None
        selected_descriptor = None

        def accept(result: ProviderRaceResult[list]) -> bool:
            nonlocal selection, selected_descriptor
            if result.error is not None or result.value is None:
                return False

            bars = list(result.value)
            self.policy.assert_single_source(bars)
            descriptor = self.repository.save_series(bars)
            downloaded.append(descriptor)
            try:
                selection = self.policy.select(
                    downloaded,
                    require_adjusted=require_adjusted,
                    authoritative=True,
                )
                selected_descriptor = next(
                    item
                    for item in downloaded
                    if item.source == selection.source
                    and item.source_symbol == selection.source_symbol
                )
                return True
            except PriceSourceMixingError:
                return False

        await race_in_canonical_order(
            order,
            lambda name: self._probe_history_provider(
                name, security, start, end
            ),
            accept,
        )

        if selection is None or selected_descriptor is None:
            raise PriceSourceMixingError(
                "No authoritative single-provider series satisfies this price request"
            )

        # Persist only the dates the selected provider actually supplied.
        # The previous implementation recorded the requested window, which could
        # falsely claim canonical coverage before an IPO or after a delisting.
        self.repository.select_series(
            security_id=security.security_id,
            start=selected_descriptor.start_date,
            end=selected_descriptor.end_date,
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
        # A configured Massive feed may validate a free/local primary, and vice
        # versa. Yahoo may confirm a series but can never become authoritative.
        candidates = self._validation_provider_order(selected_source)

        candidates = tuple(
            name
            for name in candidates
            if self.providers.get(name) is not None
            and getattr(self.providers[name], "configured", True) is not False
            and (self.health is None or self.health.can_attempt(name))
        )

        other_descriptor = None

        def accept_validation(result: ProviderRaceResult[list]) -> bool:
            nonlocal other_descriptor
            if result.error is not None or result.value is None:
                return False
            bars = list(result.value)
            self.policy.assert_single_source(bars)
            other_descriptor = self.repository.save_series(bars)
            return True

        await race_in_canonical_order(
            candidates,
            lambda name: self._probe_history_provider(
                name, security, start, end
            ),
            accept_validation,
        )
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
