---
name: meridyen-market-discovery
description: Python-first market screening with PIT and evidence quality checks.
---
# A2 — Market Discovery
Work with existing M10 market universe and provider code; do not scrape
InvestingPro or fabricate live OHLCV. Require ticker/security_id, source
timestamp, exchange, liquidity, splits and delisting flags. Prefer Python
scanner and verified cached data. For unavailable source data return
INCONCLUSIVE. Hand off an evidence manifest to A3 only after deterministic
validation. No live trading.

## Phase25R research collision quarantine

Before reporting historical membership as a market signal, inspect the
**existing** Phase25R private read-only report through the M10 source
evidence adapter (`core/hermes_team/phase25_source_evidence.py`).
Do not rerun the 2,110,622-row Phase25Q ingestion just to get metadata.
If the report is absent or lacks its source/canonical denial flags,
mark INCONCLUSIVE. In particular quarantine seven strong-cohort ticker
strings B, CWBC, FUN, STRR, TEL, TTE, VIVO because 464 issuer-name
collisions span 30 tickers in retrospective month-end source files.
Neither ticker-only historical membership nor 3,557 strong-cohort
membership constitutes certified point-in-time issuer identity.
