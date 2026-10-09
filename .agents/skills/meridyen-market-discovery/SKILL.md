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
