# Meridyen Learning Engine V2 — Architecture & Usage

**Status: Local-first journal code complete, remote sync configuration pending.**
This repository is currently PUBLIC. Never commit real learning databases, positions, holdings, API credentials, private model checkpoints or licensed market data.

## Data layout

- Active SQLite: `data/runtime/meridyen_learning.sqlite3` on M10's writable volume. Separate from canonical market operational.db.
- Analytics: existing `data/runtime/analytics.duckdb` and `data/runtime/parquet/`, accessed locally by M10; do not operate these DBs through Google Drive sync.
- Evidence: dated `backtest.json`, source SHA-256, as-of and outcome maturity; censored predictions are **not** wrong predictions.
- GitHub: code, tests, public documentation and **sanitized** non-personal manifests only.
- Google Drive: encrypted, consistent SQLite snapshots; historical Parquet/archive copies as permitted by source license. Cloud files are backups, never concurrently-open writable databases.

## Created Google Drive folders

- Root: `https://drive.google.com/drive/folders/1htnyDRIwiHJkAsPtkrhba3G00kT3KqdR`
- Learning Engine: `https://drive.google.com/drive/folders/192fUAWUIUmYb4OPamMW3ly3Us3Ls7Jx8`
- Backups: `https://drive.google.com/drive/folders/1Bgz9m2m9qiTKgToBg-LZG9VUsGIDzYrz`
- Encrypted backup subfolder: `https://drive.google.com/drive/folders/1ye42qIcRkiIyQgh69j8pSL4c6GTvsg1Q`
- Phase13 manifests: `https://drive.google.com/drive/folders/1ZrvayFMEX1Ms4xptXZJyRmulCeJ0wfwB`

## Commands (local Python 3.11+)

```powershell
python scripts/learning_v2.py init
python scripts/learning_v2.py improve
python scripts/learning_v2.py learn --backtest C:\\M10\\research\\backtest.json --as-of 2026-10-08
python scripts/learning_v2.py feedback --category DATA --note "source gap" --evidence-ref "SHA256-or-source-URL"
python scripts/learning_v2.py backup --out-dir data/runtime/learning_backups
```

`learn` is evidence journaling, **not ChatGPT self-fine-tuning**. No model may auto-promote to production. Independent PIT audit and owner authorization are required for model changes.

## Google Drive remote (optional; no secrets in repo)

Rclone must be installed and authenticated locally by the user. Configure a **crypt remote** that points to the desired Google Drive location. Its name and folder prefix must be set so its `Database_Backups/Encrypted/` destination matches the intended Drive folder; otherwise files may land elsewhere. Verify before use.

```powershell
# Offline inspection (no upload):
python scripts/sync_learning_backup.py --manifest data/runtime/learning_backups/meridyen-learning-v2-<timestamp>.manifest.json --remote-crypt meridyen_crypt:
# After verifying the remote is genuinely rclone crypt and targets the intended Drive account:
python scripts/sync_learning_backup.py --manifest data/runtime/learning_backups/meridyen-learning-v2-<timestamp>.manifest.json --remote-crypt meridyen_crypt: --execute --confirm-crypt-remote
```

The uploader checks local SHA-256 and file existence before transfer, uses immutable destination, and never uploads the SQLite file actively opened by M10. The remote name is only **user-attested**; the current script cannot verify it is encrypted. Test remote integrity and restore from cloud separately before calling the backup production-ready.

## V3 after V2 is verified

- Optional ML challengers with held-out regimes, leakage-safe label maturity and veto gates.
- Repeatable evaluation vs S15/S16 baseline; do not rewrite frozen model definitions.
- Agent may propose bounded PRs and tests when asked `geliştir`, not edit without evidence or create unapproved trades.
- Scheduled checks require an actually deployed scheduler/M10 background service; a ChatGPT plugin skill alone is not an always-on worker.

## SEC research pilot integration — 2026-10-08

**Data status: SEC-filing research snapshot only, NOT canonical PIT backtest and NOT trained ML.**

The owner has a dated research pilot of INOD, CRMD and TMDX (3 tickers × 8 research
modules = 24 checked routes). It is distributed as a private ZIP containing
`run_manifest.json`, `results/*.json`, and source-tagged inputs. The
manifest includes SHA-256 hashes for every result file. A summary receipt is
saved in the owner's Google Drive Learning_Engine/V2 folder:

https://docs.google.com/document/d/1wUb5SMJJ22-z_CgcplHtmWDsenq_lNh71EaJLt8oLKI/edit

### Local Windows import to the persistent Learning V2 database

Download the **private pilot ZIP** from the ChatGPT conversation and use the
exact path on the Windows machine with the M10 checkout:

```powershell
python scripts/learning_v2.py --db data/runtime/meridyen_learning.sqlite3 research-import --bundle "C:\\Users\\YOU\\Downloads\\Meridyen_SEC_Research_Pilot_2026-10-08.zip"
python scripts/learning_v2.py --db data/runtime/meridyen_learning.sqlite3 research-audit
python scripts/learning_v2.py --db data/runtime/meridyen_learning.sqlite3 backup
```

For a packaged M10 build, identify its actual writable `S153_RUNTIME_ROOT`
and pass the **same** private Learning V2 DB in all three commands; checkout
relative paths need not be the production install's location.

The importer rejects tampered hashes, unsupported modes/statuses, path
traversal, missing source metadata, duplicate/conflicting records, unexpected
canonical/PIT/backtest claims, and incomplete bundles. SHA256 de-duplicates
reimports. Everything is isolated in new `learning_v2_research_*` tables.

**Research ≠ outcomes:** importing these 24 observations DOES NOT populate
`learning_v2_outcomes`, imply model hit rate, score or retrain S15/S16, or
establish a market-data feed. 2026 Q2 SEC records are observational evidence;
training requires historically matured, date-audited price outcomes, controls,
realistic execution cost and independent test periods.

**Cloud:** the source-linked summary receipt is already in Google Drive;
the private SQLite database is **NOT** mirrored to Google Drive by this
import and encrypted rclone backup still needs local user configuration.
Never commit private research DBs, positions, client information, or paid
vendor data to public GitHub. No API secrets are required for local ZIP import.
