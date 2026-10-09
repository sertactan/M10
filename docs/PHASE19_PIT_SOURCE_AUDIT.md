# Phase 19 — Offline audit after the 21-month historical-listing download

**Target:** 2024-01-01 through 2025-09-30. The user observed the final `2025-09-30` CSV being saved on 2026-10-09. **Do not interpret 21 saved research CSVs as 21 canonical PIT snapshots.**

**Fix 2026-10-09:** Previous audit showed `INVALID_SOURCE_YYYY-MM-DD_ValueError` for all 21 months. The first version suppressed the actual failure reason and rejected any repeated ticker/exchange pair, although repeated source rows are an identity ambiguity rather than a corrupted source archive. The patched audit preserves such rows for counting and reports duplicate-key warnings; it still blocks tampered manifests, SHA mismatches, unexpected source counts and missing files. Real Windows re-audit must confirm the actual reason; this fix is not itself proof that the 21 files passed.

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

Expected successful **source-file** audit: either `SOURCE_ARCHIVE_VERIFIED_NOT_PIT_CERTIFIED` or `SOURCE_ARCHIVE_VERIFIED_WITH_IDENTITY_WARNINGS_NOT_PIT_CERTIFIED` (if the source contains duplicates), with `verified_months = 21`, `findings = []`. A `BLOCKED_SOURCE_ARCHIVE_INCOMPLETE_OR_INVALID` result now reports allowlisted reason codes such as `SOURCE_HASH_OR_METADATA_MISMATCH` or `SOURCE_ROW_COUNT_MISMATCH`, rather than hiding everything as a generic `ValueError`. Do not assume counts or claim complete identity until the real report is reviewed.

Inspect `distinct_ticker_exchange_listing_keys`, `distinct_ticker_strings`, `duplicate_listing_key_groups_across_months`, `sample_duplicate_listing_keys`, `listing_key_with_name_variations`, `ticker_appearing_on_multiple_exchanges` and `current_security_master_candidate_match`. Source rows are not de-duplicated or discarded; unique *keys* are calculated separately from raw row counts. **Never call these keys exact historical securities**.

Next phases require an explicit historical security-identity mapping (CIK/FIGI, classes, relistings, ticker reuse), delisting evidence, SEC original available-at data and a truly adjusted price feed. **Do not run** `sync_free_pit_universe.py` on the production DB with these unverified keys, and do not release a backtest or trained model as canonical.
