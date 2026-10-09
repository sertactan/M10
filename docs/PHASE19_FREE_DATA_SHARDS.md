# Phase 19 — Free research-data shards from iPhone / GitHub Actions

Status: IMPLEMENTED ON REVIEW BRANCH; not a certified dataset, full market backtest or training run.
Target research window: 2024-01-01 through 2025-09-30.

## Scope and guardrails

- The manual GitHub Actions workflow \`.github/workflows/phase19-free-sec-shards.yml\` runs offline regression tests and an **optional** bounded official SEC Companyfacts download.
- No new paid API, subscription, tunnel, agent deployment or broker integration.
- **No** changes to canonical S15.3/S16/S16-EA formulae, model scores, WF9, production M10 SQLite/DuckDB/Parquet, or Learning V3.
- Never call current SEC company tickers a historical PIT membership snapshot. The current exchange list excludes many delisted/renamed issuers and is a **research issuer lookup only**.
- The collector counts facts by the original SEC \`filed\` date inside the requested window. It preserves SEC raw JSON and does not backdate restated 2026 data to 2024. Neither the raw JSON nor a checksum proves SEC's precise original \`accepted_at\`.
- GitHub Actions has temporary storage. The uploaded SEC-public-data shard is an **artifact retained for seven days**, not a permanent database or a signed PIT archive. A workflow run can restore the most recent unexpired artifact with an identical shard index/size and verify its SHA-256 before skipping previously downloaded issuer files. After artifact expiry, external data must be redownloaded. Do not claim indefinite resumability.
- The repo is PUBLIC. Artifacts containing official SEC public issuer data may be visible to people with access to the Actions run. Never upload tokens, private market-data feeds, account data, private SQLite DBs, data vendor archives with restrictive terms, or \`SEC_USER_AGENT\` itself.
- Official SEC traffic is bounded at one request per second or slower *within this workflow*. Multiple parallel workflows/users on the same IP are outside this local budget. On SEC HTTP 403/429, stop and review; do not rotate IPs or evade rate limits.

## Initial execution from an iPhone

1. Have the pull request merged only after review/CI. The workflow must be on the repository default branch to appear reliably under GitHub **Actions**.
2. In GitHub M10 repository **Settings -> Secrets and variables -> Actions**, create the **repository secret \`SEC_USER_AGENT\`**, e.g. \`MeridyenResearch real-contact@owned-domain.tld\`. Use a real contact email, do not put its value in chat, a commit or a PR. This is **not a paid API key**.
3. Open **Actions -> Meridyen Phase19 Free SEC Shards -> Run workflow**. Use defaults \`execute=false\`, \`shard_index=0\`, \`shard_size=10\` for the initial **offline preview**. No network, no raw files.
4. After verifying the preview and the secret, use \`execute=true\` to fetch **up to 10 current SEC-listed issuers** in shard 0. The workflow produces \`status.json\`, \`sec_catalog.json\`, \`source_manifest.json\`, and per-issuer source JSON files in a *temporary* GitHub Actions artifact. A partial run displays failure, uploads its resumable files, and can be retried with exactly the same inputs.
5. Increase \`shard_index\` to \`1,2,...\` for separate issuer batches. \`shard_size\` must remain constant across a sweep; a different shard size changes the partition map. Track \`catalog_sha256\` across shards; mismatched hashes mean the current-ticker catalog shifted, and cohorts must be reconciled before coverage reporting.
6. Download the artifacts within seven days and transfer/ingest them **only through a separately verified M10 staging importer** on the Windows host. **This patch does not claim to integrate artifact JSON into the live operational DB.** For larger datasets use the original Windows bulk bootstrap, not 1000s of GitHub runner jobs.

Run source collector directly on Windows with a *private* writable folder:

\`\`\`powershell
$env:SEC_USER_AGENT = 'MeridyenResearch real-contact@owned-domain.tld'
python scripts/phase19_free_sec_shard.py --start 2024-01-01 --end 2025-09-30 --shard-index 0 --shard-size 10 --out-dir E:\Meridyen_SEC\phase19\shard0 --execute
\`\`\`

Omit \`--execute\` to preview offline.

## Existing maximum-history strategy: separate, guarded Windows steps

The hosted SEC collector is only the *first ingest slice*. It is not sufficient to discover the historic US market or produce canonical price outcomes.

| Source | Existing M10 integration | Role and constraints |
|---|---|---|
| Official SEC EDGAR | \`scripts/bootstrap_wf1_free_data.py\`, SEC Companyfacts importer | Free authoritative source fundamentals; available_at, amendments, source identity still require temporal audit. Bulk Companyfacts ZIP is preferable for whole-market intake, where permitted; download locally, not into git. |
| Free historical US listings | \`scripts/sync_free_pit_universe.py\` with \`ALPHAVANTAGE_API_KEY\` | Month-end PIT membership, including delisted securities. Free key required, daily limits; no paid upgrade. If unavailable, fail closed. |
| Stooq | \`data/providers/stooq_price.py\` / \`scripts/bootstrap_wf1_free_data.py\` | Useful free daily price research and RAW_ONLY discovery. NOT canonical split/dividend-adjusted backtest source. Vendor terms must permit personal use/transfer. |
| SimFin adjusted price | \`data/providers/simfin_price.py\` | Optional locally acquired bulk if the free license provides the needed date/adjustment history. Check actual columns, entitlement and redistribution. |
| Massive | Existing provider adapters | Never call for this free-only project unless an existing no-cost entitlement is independently confirmed and explicitly chosen later. |
| Yahoo | Existing fallback | Noncanonical validation, never promote to authoritative PIT. |

To check *actual* local M10 on Windows without changing its data, run Phase 18 intake and Phase 14 audit using matching paths:

\`\`\`powershell
powershell -ExecutionPolicy Bypass -File scripts/phase18_windows_intake.ps1 -ShowReport
python scripts/phase14_dataset_audit.py --start 2024-01-01 --end 2025-09-30 --report-only
\`\`\`

Choose the installed writable runtime when it differs from the checkout. Review the report's explicit missing PIT dates, price selection source quality and physical Parquet coverage before any canonical WF9 run.

## Readiness truth table

- **GitHub preview SUCCESS**: offline regression passed and a status report was generated.
- **SEC shard SUCCESS**: bounded SEC source JSON was downloaded/reused, with SHA-256; still **noncanonical research**.
- **Price/SEC/PIT readiness**: requires independent local audit of exact historic membership (including delistings), original filing availability, corporate-action adjusted OHLCV, source licenses, and actual M10 runtime tables.
- **Full learning/backtest**: requires genuine completed WF5/WF6 historical runs, matured labels and out-of-sample evaluation. Challenger model cannot auto-promote itself; frozen canonical math must remain unmodified.

### Remaining build work

1. Verify CI and manual offline preview on default branch.
2. Confirm the required SEC contact secret is present using repository UI without exposing the value.
3. Fetch a bounded issuer shard and inspect content counts; do not claim 2024–25 historic exchange coverage.
4. Implement an explicitly reviewed, local-only source importer with provenance and PIT feature gates, then run Windows native Phase18/Phase14 reports.
5. Only when local data is ready: resume WF9/OOS/Learning V2 & V3 experiments.
