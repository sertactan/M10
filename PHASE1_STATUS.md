# Phase 1 — US Universe Status

## Implemented
- Massive active US stock universe ingestion for NASDAQ / NYSE / NYSE American
- Massive delisted ticker archive ingestion
- Massive PIT universe snapshots using the provider `date` parameter
- Massive ticker-change event ingestion (optional/incremental)
- SEC EDGAR current CIK / ticker / exchange enrichment
- Finnhub current US symbol validation/fallback hook
- stable security IDs preferring Share Class FIGI, then Composite FIGI, then CIK+name
- ticker alias history
- SQLite compatibility migrations for Phase 0 databases
- historical-universe fail-closed behavior when Massive is unavailable
- no API keys committed; environment variables only

## Provider roles
1. SEC EDGAR — authoritative identity/CIK and later filings/fundamentals
2. Massive — primary listing, historical universe, delisted, ticker events
3. Finnhub — validation/fallback
4. FMP — reserved optional fallback

## Deferred to Phase 2+
- historical OHLCV ingestion
- splits/dividends/corporate-action adjustment engine
- SEC statement/fact ingestion
