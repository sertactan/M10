# Phase 19 — Offline audit after the 21-month historical-listing download

**Target:** 2024-01-01 through 2025-09-30. The user observed the final `2025-09-30` CSV being saved on 2026-10-09. **Do not interpret 21 saved research CSVs as 21 canonical PIT snapshots.**

This phase uses `scripts/phase19_pit_source_audit.py`, which:
- makes **zero API calls**, downloads nothing and does not open the SEC ZIP;
- verifies every requested month-end CSV against its paired local source manifest, SHA-256, original byte length, filtered share count, and exchange totals;
- reports distinct `(ticker, exchange)` **listing keys**, not distinct legal issuers or securities (ticker reuse, changes in company names, mergers and exchange changes remain unresolved);
- reports appearing/disappearing keys for manual review; does not infer that a missing ticker was delisted or that its price went to zero;
- optionally reads the installed `security_master` via **SQLite mode=ro/query_only** and counts tentative current ticker/exchange matches with CIK, absent CIK, ambiguous keys and no match. This does **not certify historical SEC CIK identity**;
- produces `phase19_listing_source_audit.json` in the private local PIT staging folder. Never upload raw CSV/manifest, local SQLite DB or API key to public GitHub.
- leaves `operational.db`, SEC Companyfacts (**12,313,284 records from user's actual local observation**), all prices, and S15.3/S16/WF9/Learning V3 unchanged.

Run in Windows PowerShell after updating `E:\M10`:

```powershell
cd E:\M10
git pull --ff-only
$db = "$env:LOCALAPPDATA\S153ResearchTerminal\runtime\data\runtime\operational.db"
.\.venv\Scripts\python.exe -m scripts.phase19_pit_source_audit --db "$db"
```

Expected successful **source-file** audit: `status = SOURCE_ARCHIVE_VERIFIED_NOT_PIT_CERTIFIED`, `verified_months = 21`, `findings = []`. No expectation is set for actual distinct listing-key count; compute from real CSV files.

Inspect `distinct_ticker_exchange_listing_keys`, `distinct_ticker_strings`, `listing_key_with_name_variations`, `ticker_appearing_on_multiple_exchanges` and `current_security_master_candidate_match`. **Never call these keys exact historical securities**.

Next phases require an explicit historical security-identity mapping (CIK/FIGI, classes, relistings, ticker reuse), delisting evidence, SEC original available-at data and a truly adjusted price feed. **Do not run** `sync_free_pit_universe.py` on the production DB with these unverified keys, and do not release a backtest or trained model as canonical.
