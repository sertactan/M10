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

### Phase 1 — US Universe ✅ code-complete
- NASDAQ / NYSE / NYSE American universe
- Massive PIT ticker snapshots and delisted archive
- SEC EDGAR CIK/ticker/exchange enrichment
- Finnhub validation/fallback hook
- stable security IDs with FIGI-first identity
- ticker aliases and ticker-change events
- historical universe fails closed without a PIT-capable source

Live Massive/Finnhub ingestion starts when local API keys are configured. No key is committed to the repository.

## Provider roles

1. **SEC EDGAR** — authoritative CIK/identity; Phase 3 filings and fundamentals
2. **Massive** — US listing universe, historical point-in-time universe, delisted symbols, ticker events; Phase 2 price/corporate actions
3. **Finnhub** — validation/fallback; later estimates/analyst/news
4. **FMP** — optional future fallback only

## Local API configuration

Copy `.env.example` to `.env` and fill values locally:

```text
SEC_USER_AGENT=Your Name your-email@example.com
MASSIVE_API_KEY=
FINNHUB_API_KEY=
FMP_API_KEY=
```

`.env` is gitignored. Never commit real API keys.

## Quick checks

```powershell
python -m pytest
python main.py --doctor
```

## Sync today's US universe

```powershell
python main.py --sync-universe
```

With a Massive key this uses Massive PIT listings and optionally the delisted archive, then SEC enriches current identities and Finnhub validates current symbols.

## Historical PIT universe

```powershell
python main.py --sync-universe --as-of 2025-05-05 --no-delisted
```

Historical sync **requires Massive**. The program will not silently use today's SEC/Finnhub symbol list for an old date.

## Incremental ticker-change history

```powershell
python main.py --sync-universe --ticker-events 250
```

The argument is intentionally bounded/incremental because ticker-event history requires per-security API calls.

## Next

Phase 2 — Historical Price Engine: 10–20+ year OHLCV, adjusted/unadjusted prices, splits/dividends and corporate-action normalization.
