# S15.3 Research Terminal

Windows desktop research platform for **S15.3 V1.2** and **S15.3 V1.4 Dual-Magnitude Architecture**.

## Status

### Phase 0 — Architecture ✅
- PIT-safe contracts and look-ahead guard
- SQLite / DuckDB / Parquet boundaries
- provider interfaces
- external model configs
- reproducible analysis-run persistence
- production mock-data prohibition

### Phase 1 — US Universe ✅
- NASDAQ / NYSE / NYSE American universe
- Massive PIT ticker snapshots and delisted archive
- SEC EDGAR CIK/ticker/exchange enrichment
- Finnhub validation/fallback hook
- stable security IDs with FIGI-first identity
- ticker aliases and ticker-change events
- historical universe fails closed without a PIT-capable source

### Phase 2 — Historical Price Engine ✅
- common `PriceProvider` interface:
  - `get_history()`
  - `get_daily_bar()`
  - `get_market_snapshot()`
  - `get_splits()`
  - `get_dividends()`
  - `validate_symbol()`
- Massive raw + adjusted daily bars, splits and dividends
- Stooq individual CSV + bulk ZIP bootstrap
- SimFin bulk CSV/ZIP share prices with chunked reads
- Yahoo-compatible fallback/validation only
- MarketParquet optional survivorship-aware Parquet ingestion
- provider-isolated Parquet price lake + DuckDB catalog hook
- SQLite series registry, canonical-source selection and validation results
- no silent cross-provider stitching

Every historical price row retains at least:

```text
source
source_symbol
raw_close
adjusted_close
retrieved_at
quality_status
```


### Phase 3 — Fundamental / SEC Engine ✅ code-complete
- SEC EDGAR Submissions + Company Facts/XBRL
- 10-K / 10-Q / 8-K / 20-F (plus amendments and 40-F/6-K support)
- filing date + accepted timestamp + accession number + source document
- amendment/restatement version preservation
- PIT canonical snapshots
- SEC regulatory precedence over all secondary providers
- Finnhub normalized financials, estimates and company metrics
- SimFin bulk historical fundamentals
- FMP statement/ratio fallback
- official SEC / Investor Relations KPI-guidance ingestion
- TTM and FCF snapshot calculations
- secondary validation without SEC overwrite

Every fundamental fact retains:

```text
metric_name
value
period_end
filing_date
accepted_at
available_at
source
source_document
accession_number
retrieved_at
quality_status
validation_status
```

## Historical price provider priority

1. **Massive** — primary professional historical/current market data
2. **Stooq** — free historical OHLCV bootstrap, individual CSV and bulk ZIP
3. **SimFin** — secondary bulk daily share-price dataset
4. **Yahoo-compatible** — fallback and validation only; never authoritative for backtests
5. **MarketParquet** — optional bulk Parquet source, useful for survivorship-bias-aware research

The engine selects **one source for an entire requested backtest window**. It may compare another provider for validation, but never fills missing dates by silently mixing sources.

## Provider roles outside prices

1. **SEC EDGAR** — authoritative CIK/identity; Phase 3 filings and fundamentals
2. **Massive** — US listing universe, historical PIT universe, delisted symbols, ticker events
3. **Finnhub** — validation/fallback; later estimates/analyst/news
4. **FMP** — optional future fallback only

## Local configuration

Copy `.env.example` to `.env` and fill only what you use:

```text
SEC_USER_AGENT=Your Name your-email@example.com
MASSIVE_API_KEY=
FINNHUB_API_KEY=
FMP_API_KEY=
STOOQ_BULK_ZIP_PATH=
SIMFIN_PRICE_BULK_PATH=
MARKETPARQUET_ROOT=
SIMFIN_FUNDAMENTALS_PATH=
```

`.env` is gitignored. Never commit real API keys.

## Quick checks

```powershell
python -m pytest
python main.py --doctor
```

## Sync US universe

```powershell
python main.py --sync-universe
python main.py --sync-universe --as-of 2025-05-05 --no-delisted
```

Historical universe sync requires Massive because SEC/Finnhub symbol lists are current-reference sources.

## Sync one ticker's historical prices

```powershell
python main.py --sync-price AAPL --price-start 2010-01-01 --price-end 2026-10-05
```

Force one provider:

```powershell
python main.py --sync-price AAPL --price-start 2010-01-01 --price-end 2026-10-05 --price-provider MASSIVE
```

`YAHOO_COMPAT` can be downloaded for validation but the canonical backtest policy will not accept it as the sole authoritative source.

## Bootstrap a Stooq bulk ZIP

```powershell
python main.py --ingest-stooq-bulk "D:\data\stooq_us_daily.zip"
```

The importer stores series incrementally rather than loading the entire archive into memory.

## SimFin / MarketParquet

Set a local bulk path:

```text
SIMFIN_PRICE_BULK_PATH=D:\data\simfin-share-prices.zip
MARKETPARQUET_ROOT=D:\data\marketparquet\
```

Then `AUTO` price sync can use those sources according to provider policy if higher-priority sources are unavailable or unsuitable.

## Fundamental sync

```powershell
python main.py --sync-fundamentals AAPL
python main.py --sync-fundamentals AAPL --fund-provider SEC_EDGAR
python main.py --show-fundamentals AAPL --fund-as-of 2025-05-05
```

For official company guidance / non-standard KPIs, ingest structured records with an official HTTPS document:

```powershell
python main.py --ingest-ir-json ".\\guidance.json" --ir-ticker AAPL
```

SEC-sourced structured KPI records must reference a sec.gov document and accession number.

## Next

Phase 4 — S15.3 V1.2 canonical scoring engine.
