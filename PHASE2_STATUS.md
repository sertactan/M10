# Phase 2 — Historical Price Engine Status

## Implemented
- common PriceProvider interface:
  - get_history()
  - get_daily_bar()
  - get_market_snapshot()
  - get_splits()
  - get_dividends()
  - validate_symbol()
- Massive dual raw/adjusted daily bars, splits, dividends, snapshot, symbol validation
- Stooq individual CSV and bulk ZIP ingestion
- SimFin bulk CSV/ZIP daily share-price ingestion
- Yahoo-compatible fallback/validation adapter
- MarketParquet local Parquet adapter with delisted-symbol support
- provider-isolated Parquet price storage
- SQLite series registry / canonical selection / validation metadata
- cross-provider stitching prohibition
- split normalization helper that rejects cross-provider corporate actions
- adjusted-series requirement for backtest selection

## Provider priority
1. Massive — primary professional provider
2. Stooq — free bootstrap/raw history
3. SimFin — secondary bulk daily prices
4. Yahoo-compatible — fallback/validation only; never authoritative
5. MarketParquet — optional survivorship-aware Parquet archive

## Important invariant
Historical prices from different providers are never silently mixed into one series.
Each row retains source, source_symbol, raw_close, adjusted_close, retrieved_at and quality_status.

## Deferred
- full-market download orchestration / rate-aware batching
- Windows UI progress/reporting
- provider-specific live acceptance runs after local keys/bulk archives are configured
