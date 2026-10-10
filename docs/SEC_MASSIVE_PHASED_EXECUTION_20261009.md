# SEC + Massive — 10 Fazlık Gerçek Veri Programı (2026-10-09)

Tracking: https://github.com/sertactan/M10/issues/117

**Status:** F0 inventory code staged. Windows execution and SEC/Massive full data completion NOT VERIFIED. Zero new paid API calls or subscriptions, no secret disclosure, no live database mutations, no canonical formula changes.

## Completion must be evidenced, not guessed
- Target 2013-01-01..2024-12-31 = 144 exact historical month ends.
- SEC ZIP present ≠ imported facts complete ≠ original SEC accepted_at independently evidenced.
- Massive Python adapter installed ≠ historical entitlement ≠ adjusted OHLCV/delisted payouts available.
- PIT rows ≠ true historical listing membership. Source labels alone cannot certify PIT.
- Prior ~1.3 GB ongoing SEC and ~25/144 monthly PIT are old observations, not current measurements.
- Code CI is not evidence that the real Windows operational.db has been populated.

## F0: Protect current SEC job and read-only inventory — STARTED
Implemented: scripts/sec_massive_phase0_inventory.py + tests. Never calls SEC/Massive, reads DB, creates files, or reads local .env secrets. Read-only metadata of lock, ZIP, checkpoint, Windows runtime path, provider process-environment Boolean flags. A False means only absent from current process environment (not necessarily absent from private .env).

On the actual Windows machine:
1. Verify whether legacy SEC ZIP importer is still running with Task Manager. Do not stop it, start a second one, delete lock, switch its running checkout's Git branch, or overwrite the DB.
2. After the F0 draft PR is reviewed/merged and the current import has stopped, update a separate checkout. From E:\M10, use PowerShell:
   
       $root = Join-Path $env:LOCALAPPDATA 'S153ResearchTerminal\runtime'
       python -m scripts.sec_massive_phase0_inventory --runtime-root "$root"

3. For current builds with the actual feature, DATA CONTROL → REFRESH (READ ONLY) shows local SEC/PIT progress; older EXE will not get source updates automatically.
4. Save only the status/counter fields (not credentials or private vendor data). Current PIT count requires real runtime audit. This F0 script deliberately does not scan the live SQLite DB.
**F0 gate:** Windows operator process-state confirmation and independent readonly status evidence; when the importer has finished, create SQLite online backup before further work.

## F1: SEC Companyfacts importer completion
Confirm PID/exclusive lock status, finish existing run safely, no duplicate importer. Reconcile ZIP entry counters and fact/issuer counts, run quick_check on SQLite backup, document missing data. A ZIP on disk does not prove completion.
**Gate:** importer status and integrity evidence verified from Windows.

## F2: SEC original Submissions / filings.files archive
After F1, run existing phase14_sec_submissions_collect.py dry-run first. Use identifying SEC_USER_AGENT, conservative rate limit and stop at 403/429. Archive original immutable root and historical files outside public Git with CIK/accession hashes/manifest.
**Gate:** historical document coverage plus explicit missing-item inventory.

## F3: SEC original accepted_at & fundamental PIT
On backup, run phase14_sec_submissions_archive_reconcile.py and SEC acceptance journal. Validate filing times, accession, share-class identity, amendments, restatements, period_end, available_at. No backdating. Preserve TTM/FCF as-of semantics.
**Gate:** traceable and independently audited issuer coverage, conflicts blocked rather than guessed.

## F4: Massive entitlement and single-stock pilot
Determine MASSIVE_API_KEY presence without reading/disclosing its value, independently verify allowed historical dates, license, API quota. Use existing phase14_price_actions_pilot.py preview first; after operator backup and consent only, a small INOD historical-year live test. Do not automatically upgrade.
**Gate:** real one-ticker raw/adjusted prices and splits/dividends confirmed, or BLOCKED_ENTITLEMENT.

## F5: Historical US PIT universe
Use existing sync_free_pit_universe.py AUTO (eligible Alpha Vantage free listing-status or permitted Massive) to resume 144 exact month-end snapshots; include delisted, aliases/ticker reuse, historical market exchange and security_id/CIK mapping.
**Gate:** 144/144 independently reviewed exact PIT dates, no present-day-survivor substitution.

## F6: Prices, corporate actions, delisting
Use eligible Massive/MarketParquet/SimFin adjusted-price source in bootstrap_wf9_canonical_data.py, not RAW_ONLY Stooq or unofficial Yahoo as canonical. Keep entire series by source; check actual physical Parquet partitions, splits, dividends, and delisting proceeds/cashouts.
**Gate:** source-verified adjusted and terminal outcomes; do not interpret missing bars as zero return.

## F7: Cross-source quality, PIT and temporal gates
Run existing Phase13/14/18 read-only audits on the SAME real Windows DB/Parquet root. Review accepted_at leakage, ticker/CIK ambiguities, missing monthly universe members, price adjustment errors, coverage, amendments and future facts.
**Gate:** no unresolved canonical blocker, independent source provenance review.

## F8: WF9, WF5/WF6 and S16 evaluations
After signed-off F7, run phase13_windows_pipeline.ps1 in report mode; native -Execute requires operator authorization. WF9 must really report COMPLETE_AND_ACTIVATED, then mature 252-session WF5 outcomes and WF6 OOS tests. S16-E estimated distinct from S16-C canonical; missing evidence means INCONCLUSIVE.
**Gate:** dataset/run manifest, genuine historical execution and leakage/false-positive review.

## F9: Refresh, alerting, backups and restore
Configure modest provider-budget incremental jobs; no 24/7 guarantees from idling free services. Keep active SQLite/DuckDB local; use optional encrypted Drive backups only as licensed and verify restore. No trading automation or hidden expenses.
**Gate:** operational dry run + one actual restore evidence.

## Existing project sources
- PHASE14_STATUS.md, PHASE14_SEC_ACCEPTANCE_STAGE.md, PHASE14_PRICE_ACTIONS_PILOT.md
- PHASE18_STATUS.md, DATA_CONTROL_CENTER_STATUS.md
- docs/MERIDYEN_IPHONE_REMOTE_AND_PIT_GATES_20261009.md

This roadmap does not start remote downloads or assert local importer termination. The next actual data-mutating steps require the owner machine and vendor/date rights.