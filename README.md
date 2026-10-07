# S15.3 Research Terminal

Windows desktop research platform for **S15.3 V1.2**, **S15.3 V1.4.1**, **S16 V1.0 Canonical**, and **S16-EA V1.3 Canonical Hybrid FastPath**.

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
- free Alpha Vantage dated listing-status PIT snapshots (2010+ with free key)
- Massive PIT ticker snapshots and delisted archive as optional accelerator
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

### Phase 4 — S15.3 V1.2 Canonical Scoring Engine ✅ code-complete
- canonical Core48 / Control12 / DNA60
- S1 / S2 / S3 / S14 / Company Quality
- F10 / I10 / D10 / B10 / R10 / Q10
- route gates and bottleneck penalty
- DF5 / DF10 / MCH5 / MCH10
- M5 / M10 / MAGGAP / NMP
- T10 / T15 / HP
- Core15.3 / final S15.3
- Discovery / Strong Watch / Precision Confirmed
- PIT canonical feature input layer only
- no new market/fundamental provider
- run reproducibility with data/config hashes

### Phase 5 — S15.3 V1.4.1 Canonical ✅ implemented
- V1.4.1 production canonical formula and completion specification are bound.
- Dual-magnitude / route-aware production scoring is active.
- Missing canonical evidence remains N/A/fail-closed; V1.2 math is never substituted silently.
- Production Windows release gate packages and verifies the V1.4.1 specification.

### Phase 6 — Historical Backtest Engine ✅ implemented / production evidence pending
- canonical anchor-session / adjusted-close / next-252-session / FM252 outcome engine
- single-provider canonical price selection; no cross-provider stitching
- PARTIAL / CENSORED handling without silent failure imputation
- feature/outcome firewall and reproducible outcome hashes
- production execution is delegated to WF9 and remains fail-closed without real PIT/adjusted data

### Phase 7 — Market Scanner ✅ implemented
- current + historical US universe scanner
- NASDAQ / NYSE / AMEX coverage
- canonical PIT feature loading
- S15.3 V1.2 + V1.4.1 production scoring
- historical delisted securities preserved
- sort / filter / CSV export and background progress path

### WF6–WF8 — Walk-forward validation / production hardening ✅ implemented
- expanding OOS folds and leakage controls
- empirical magnitude calibration with sample-size gates
- reproducibility manifest, tamper detection, rollback-safe activation
- Windows/runtime WF8-E release evidence gate

### WF9 — Full historical execution ⚠️ real-data execution pending
- default window: 2013-01 through 2024-12 (144 monthly PIT snapshots)
- resumable PIT-universe + authoritative adjusted-price bootstrap
- succeeds only when the run returns `COMPLETE_AND_ACTIVATED`
- current-universe substitution, Yahoo authority, and Stooq RAW_ONLY promotion are forbidden

### S16 / S16-EA
- S16 V1.0 canonical model is present and exposed in the desktop UI.
- S16 uses persisted `S16::` PIT features and fails closed when the 22 required features are incomplete.
- S16-EA V1.3 frozen Hybrid FastPath engine is implemented in Python with canonical parity tests.
- The S16-EA desktop tab intentionally reports INCONCLUSIVE until true PIT intraday/news evidence is loaded; daily data is never fabricated into an early-alert score.

## Historical price provider priority

1. **Massive** — primary professional historical/current market data
2. **Stooq** — free historical OHLCV bootstrap, individual CSV and bulk ZIP
3. **SimFin** — secondary bulk daily share-price dataset
4. **Yahoo-compatible** — fallback and validation only; never authoritative for backtests
5. **MarketParquet** — optional bulk Parquet source, useful for survivorship-bias-aware research

The engine selects **one source for an entire requested backtest window**. It may compare another provider for validation, but never fills missing dates by silently mixing sources.

## Provider roles outside prices

1. **SEC EDGAR** — authoritative CIK/identity; Phase 3 filings and fundamentals
2. **Alpha Vantage LISTING_STATUS** — free-key historical PIT listing snapshots (2010+)
3. **Massive** — optional historical PIT/delisted/ticker-event accelerator
4. **Finnhub** — validation/fallback; later estimates/analyst/news
5. **FMP** — optional future fallback only

## Local configuration

Copy `.env.example` to `.env` and fill only what you use:

```text
SEC_USER_AGENT=Your Name your-email@example.com
ALPHAVANTAGE_API_KEY=
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

Historical universe sync is free-key capable through Alpha Vantage LISTING_STATUS for dates after 2010-01-01. Massive remains an optional accelerator; current SEC/Finnhub symbol lists are never substituted for historical PIT membership.

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

## Run canonical V1.2

```powershell
python main.py --run-v12 AAPL --model-as-of 2025-05-05
```

The model reads only PIT canonical model features materialized from Phases 1-3,
historical controls, or deterministic canonical derivations. Missing factors remain N/A.

## WF9 production run

```powershell
python scripts/bootstrap_wf9_canonical_data.py --start 2013-01-01 --end 2024-12-31 --sync-universe --provider AUTO
python scripts/run_wf9_full_execution.py --preflight-only --code-identity <CURRENT_BUILD_COMMIT>
python scripts/run_wf9_full_execution.py --code-identity <CURRENT_BUILD_COMMIT>
```

A release must not claim WF9 completion unless the final command returns `COMPLETE_AND_ACTIVATED`.
