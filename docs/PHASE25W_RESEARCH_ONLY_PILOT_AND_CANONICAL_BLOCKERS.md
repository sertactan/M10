# Phase25W — Source-backed research pilot; canonical PIT remains fail-closed

Date 2026-10-10. Scope: next incremental implementation after Phase25Q/R/K/S and draft PR #162. No repeated download, no stage rebuild, no edits to operational.db, S15/S16, Learning V2 or Hermes.

## Verified contract and outputs

- Read existing private Phase25Q manifest and Phase25R source reconciliation and **require the same immutable staging_version** and matching source row counts. Open original staging SQLite with mode=ro, query_only and quick_check.
- Preserve **all 464 source identity collision rows** in the new private JSON report, each marked QUARANTINED_PENDING_DATED_IDENTITY_EVIDENCE. Their 30 ticker strings, including seven strong candidates B, CWBC, FUN, STRR, TEL, TTE, VIVO, must not be automatically accepted.
- From Phase25K candidate_gate, sort **non-directly-colliding source candidates with observable prices** deterministically by local daily-row coverage and monthly ticker overlap; select at most 25 (configurable 1..100) as a research-audit queue. Selected does not mean historical daily identity is PIT-certified, nor that survivors represent the whole US market.
- Include primary-public-record event references for B, CWBC, FUN, STRR, TEL, TTE, VIVO, and SITC. Official events document conditional historical facts but **do not** certify automatic adjusted-price vendor factors, rights payouts or point-in-time price series. SITC reverse split and CURB spin-off research is crosschecked by existing optional Phase25S report, requiring identical stage version.
- Read actual operational.db only in mode=ro: count 2024–2025 canonical membership rows, overlapping BACKTEST_ADJUSTED selections and corporate_actions rows; missing DB returns null instead of pretending 0.
- Persist a new private JSON file with all 464 conflicts and the research pilot observations. The CLI prints summary-only figures. Never upload private issuer rows, data files, SQLite or manifest to public GitHub.

## PIT hard constraints

- 21 Alpha Vantage month-end files fetched retrospectively in 2026 **are not** contemporaneously known 2024–2025 daily membership.
- SimFin Adj. Close may be hindsight-adjusted. Split or spin-off official announcements do not by themselves certify close-to-close total returns, CURB distribution rights, dividends or delisting payouts.
- A ticker string alone is never historical CIK/CUSIP/share-class identity. Any unknown issuer/date is quarantined, even outside the 30 direct collision symbols.
- SEC accepted time is not automatically public dissemination time nor feature ingestion available_at time.
- This phase **cannot** legitimately move even one source record to canonical. Only an independently evidenced later per-security/date admission importer can do so.

Primary cross-checks: [Nasdaq CWBC old/new symbol and 0.79 exchange](https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2024-160), [Barnes cash merger SEC report](https://www.sec.gov/Archives/edgar/data/9984/000114036125001965/ef20042046_8k.htm), [SITC 2 CURB per 1 SITC SEC exhibit](https://www.sec.gov/Archives/edgar/data/894315/000119312524231147/d104351dex991.htm). Complete seven cases are in Phase25V documentation and Phase25W public-source catalogue.

## Local Windows runbook

Use a separate, up-to-date worktree. Never change the user's original main checkout:

~~~powershell
git -C E:\M10 fetch origin
$code = "$env:TEMP\M10-phase25w"
if (-not (Test-Path $code)) {
  git -C E:\M10 worktree add --detach $code origin/feat/phase25w-research-cohort-pit-failclosed-20261010
}
Set-Location $code
$root = "$env:LOCALAPPDATA\S153ResearchTerminal\runtime"
& "E:\M10\.venv\Scripts\python.exe" -m scripts.phase25w_research_pit_pilot --manifest "$root\phase25q\staged_datasets\research_pit_28323984fb4f48b1\manifest.json" --phase25r "$root\phase25r\staging_readonly_reconciliation.json" --sitc "$root\phase25s\sitc_official_reverse_split_spinoff_price_diagnostics.json" --operational-db "$root\data\runtime\operational.db" --pilot-size 25 --out "$root\phase25w\pilot_cohort_research_only_v1.json"
~~~

The private output path is **create-only**: a repeat run must use a distinct filename. Regression tests use synthetic SQLite only:
~~~powershell
& "E:\M10\.venv\Scripts\python.exe" -m unittest tests.test_phase25w_research_pit_pilot -v
~~~

## Source-certification and release gates

- **464/464 source identity conflict rows remain quarantined.** No automatic resolution in this PR.
- **Canonical accepted securities independently proven: 0** by the referenced research-only source contract. Even if operational tables contain rows, they are never automatically certified here.
- **Real Windows pilot observed 2026-10-10:** 25 of 133 priced, non-directly-colliding source candidates entered the research-only queue; 464/464 conflict rows across 30 ticker strings stayed quarantined. Operational read-only counts: 2024–2025 historical membership 0, BACKTEST_ADJUSTED selections 0, corporate actions 0. Canonical accepted securities and security-dates proven: 0. Phase25S supplied two official-event research price pairs. The private JSON report stays outside GitHub (SHA-256 `002f5f035ac082de16703060fb68cbe00ead422a70fd537109b4b25ae459e2ef`). Windows-specific synthetic tests: 6 passed after fixture connections were explicitly closed. CI passing proves engineering only, not PIT or 10X returns.
- WF9, historical WF5/WF6 and Learning V3 are **BLOCKED** pending complete independence-verified historical issuer continuity, daily exchange session calendar, delist-inclusive universe, full corporate-action vendor-adjusted price and terminal payoff, and SEC public publication/feature available_at audit.
- All changes in this PR are limited to a new script, synthetic tests and this documentation. Existing PR #162, original vendor data and frozen models untouched.
