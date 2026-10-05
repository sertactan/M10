from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from data.providers.finnhub_universe import FinnhubUniverseProvider
from data.providers.massive_universe import MassiveUniverseProvider
from data.providers.sec_edgar_universe import SECEdgarUniverseProvider
from data.repositories.security_repository import SecurityRepository


@dataclass(frozen=True)
class UniverseSyncResult:
    as_of: date
    source_mode: str
    active_loaded: int
    delisted_loaded: int
    sec_enriched: int
    finnhub_validated: int
    snapshot_count: int
    ticker_events_loaded: int


class USUniverseService:
    def __init__(
        self,
        repository: SecurityRepository,
        *,
        sec: SECEdgarUniverseProvider,
        massive: MassiveUniverseProvider,
        finnhub: FinnhubUniverseProvider,
    ) -> None:
        self.repository = repository
        self.sec = sec
        self.massive = massive
        self.finnhub = finnhub

    async def sync(
        self,
        *,
        as_of: date,
        include_delisted: bool = True,
        ticker_event_limit: int = 0,
    ) -> UniverseSyncResult:
        today = datetime.now(timezone.utc).date()
        active_loaded = 0
        delisted_loaded = 0
        sec_enriched = 0
        finnhub_validated = 0
        ticker_events_loaded = 0

        if self.massive.configured:
            active_records = await self.massive.list_us_securities(as_of=as_of, active=True)
            active_loaded = self.repository.bulk_upsert(active_records, snapshot_date=as_of)
            source_mode = "MASSIVE_PIT"

            if include_delisted and as_of == today:
                delisted_records = await self.massive.list_us_securities(active=False)
                delisted_loaded = self.repository.bulk_upsert(delisted_records)

            # SEC and Finnhub are current-reference sources. Never enrich a historical
            # snapshot with current identifiers because that can create identity look-ahead.
            if as_of == today:
                sec_records = await self.sec.list_current_us_securities()
                for record in sec_records:
                    if self.repository.merge_sec_identity(record):
                        sec_enriched += 1
                if self.finnhub.configured:
                    finnhub_symbols = await self.finnhub.list_us_symbols()
                    known = {row["ticker"] for row in self.repository.current_us_common_stocks()}
                    finnhub_validated = sum(1 for item in finnhub_symbols if item.symbol in known)

                if ticker_event_limit > 0:
                    candidates = self.repository.current_us_common_stocks()[:ticker_event_limit]
                    for row in candidates:
                        identifier = row.get("composite_figi") or row["ticker"]
                        events = await self.massive.ticker_events(identifier)
                        self.repository.apply_ticker_events(row["security_id"], events)
                        ticker_events_loaded += len(events)
        else:
            if as_of != today:
                raise RuntimeError(
                    "Historical US universe sync requires MASSIVE_API_KEY because SEC/Finnhub "
                    "symbol lists are current-reference sources, not PIT universe archives."
                )
            sec_records = await self.sec.list_current_us_securities()
            active_loaded = self.repository.bulk_upsert(sec_records, snapshot_date=as_of)
            sec_enriched = active_loaded
            source_mode = "SEC_CURRENT_FALLBACK"
            if self.finnhub.configured:
                finnhub_symbols = await self.finnhub.list_us_symbols()
                known = {row["ticker"] for row in self.repository.current_us_common_stocks()}
                finnhub_validated = sum(1 for item in finnhub_symbols if item.symbol in known)

        snapshot_count = len(self.repository.universe_as_of(as_of))
        return UniverseSyncResult(
            as_of=as_of,
            source_mode=source_mode,
            active_loaded=active_loaded,
            delisted_loaded=delisted_loaded,
            sec_enriched=sec_enriched,
            finnhub_validated=finnhub_validated,
            snapshot_count=snapshot_count,
            ticker_events_loaded=ticker_events_loaded,
        )
