# Phase20 — Historical identity candidate review (offline)

Input: verified 2024-01-01 through 2025-09-30 Alpha Vantage historical listing CSVs and manifests, plus the existing local M10 operational.db.

Read-only: zero API calls, zero paid providers, no SEC downloads, production SQLite writes, model changes, or training.

## Windows command

    cd E:\M10
    git pull --ff-only
    .\.venv\Scripts\python.exe -m scripts.phase20_identity_candidate_review

The result is a PRIVATE local report under:
%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase19\pit_identity_candidates.json

No raw data or database should be uploaded to a public GitHub repository.

## Actual observed Phase19 baseline (Oct 9 2026)

- 21 of 21 source months verified, no source SHA errors.
- 6839 unique (ticker, exchange) listing KEYS; 6831 distinct ticker strings.
- 4917 present-day local ticker/exchange matches with a CIK.
- 231 present-day matches without CIK.
- 1691 without an exact present-day local ticker/exchange match.
- 0 keys with multiple matching present-day security IDs.
- 485 repeated (month,ticker,exchange) key groups; 56 name variations; 8 ticker strings on multiple exchanges.

The 6839 listing keys are NOT certified unique historical legal issuers.

## Report categories

- CURRENT_TICKER_EXCHANGE_CIK_CANDIDATE: matches today's ticker/exchange plus CIK, not a historical identity proof.
- CURRENT_TICKER_EXCHANGE_NO_CIK: matching current listing but no CIK.
- AMBIGUOUS_CURRENT_DB_MATCH: multiple present-day security IDs.
- OTHER_EXCHANGE_TICKER_CANDIDATE: same ticker, another exchange.
- ALIAS_TICKER_CANDIDATE: possible ticker alias.
- NORMALIZED_NAME_CANDIDATE: exact punctuation-insensitive company-name lookup; not certified.
- MULTIPLE_WEAK_CANDIDATES_REVIEW_ONLY: multiple competing hints.
- NO_LOCAL_IDENTITY_CANDIDATE: requires independent historical research.

All hints must undergo historic CIK/FIGI/share-class + time-varying alias checks, SEC filing-date/acceptance checks, delisting/corporate-action evidence and split/dividend-adjusted price verification before being promoted into canonical PIT or historical machine learning. No auto-merges or rescoring are performed.

Command options: --db, --staging-dir, --out, --start, --end. The tool verifies saved source hashes before comparing to local SQLite (mode=ro/query_only). It does not rewrite the existing ~12.3M SEC facts.
