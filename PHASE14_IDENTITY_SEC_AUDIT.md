# Phase14 — Historical Ticker/CIK Identity & SEC Acceptance-Time Audit

Status: **engineering audit added**; NO Windows database scanned by GitHub.
Does NOT alter frozen S15/S16 formulas, current SEC ingest, PIT rows or
any canonical feature score. This is a diagnostic, not automated repair.

## Why this audit is necessary

- In `SecurityRepository.upsert_historical_snapshot_record`, fallback
  matching by `(ticker,exchange)` can accidentally attach historical
  listings to a later issuer that reused the symbol; if both CIKs are
  present and disagree, a human-backed issuer history is required.
- `app/bulk_data_bootstrap.py` imports SEC `companyfacts.zip` with
  `filing_map={}`; therefore the imported fact may know a filing DATE
  but not the original SEC submissions `acceptanceDateTime`. Falling
  back to the next UTC day is conservative relative to the filing date
  but **does not certify an original acceptance timestamp**.
- Matching a security by CIK alone is insufficient for share-class
  identity. Multiple securities may legitimately share one CIK.

## Audit scope

1. US ticker + exchange keys assigned multiple known distinct CIKs;
   candidate ticker reuse needs reconciliation against historical SEC
   filings and exchange event evidence.
2. A single `(snapshot_date,ticker,exchange)` assigned multiple security
   IDs (first 31 groups checked and 30 displayed). Counts are lower
   bounds if the sample is truncated.
3. Explicit time-bounded ticker aliases belonging to distinct security
   IDs with overlapping validity windows. Open-ended/undated aliases
   are NOT evidence of a definite collision; flagged as not certified.
4. Latest N SEC_EDGAR financial fact rows for missing or malformed
   acceptance times, invalid/missing available times, available-before-
   accepted lookahead, available-before-filed-date, impossible periods,
   absence of accession, and optional SEC submissions linkage.
5. Where `filing_records_source` contains a matching accession for the
   same security, checks availability against original stored filing
   acceptance time and detects mismatching fact/filing acceptance.

The fact sample uses descending rowid and is **recent-insertion-biased**,
NOT random or exhaustive. Even clean samples do NOT certify historical
filing PIT or WF9. The tool never changes existing rows.

## Windows run (SAFE while SEC import is still underway)

Open a separate Windows PowerShell. You do not need to interrupt SEC.

    cd E:\M10
    git pull
    $db="$env:LOCALAPPDATA\S153ResearchTerminal\runtime\data\runtime\operational.db"
    .\.venv\Scripts\python.exe -m scripts.phase14_identity_sec_audit --db "$db" --sec-sample 500 --out "E:\Meridyen_Backups\identity_sec_audit.json"

A sample of 500 SEC rows is suggested during active 1.3GB Companyfacts
import. Later, with the importer stopped, use `--sec-sample 10000`
for a larger but still nonexhaustive sample. Both are read-only; the
JSON report path is intentionally **outside** the live operational DB.
With a busy SQLite lock, the audit exits with an error rather than
waiting or retrying aggressively. Re-run after the importer completes.

## Interpret results

- `SAMPLED_NO_FLAGS_NOT_PIT_CERTIFIED`: no problems visible in bounded
  checks; not an affirmative PIT or model readiness certificate.
- `EVIDENCE_GAPS_REQUIRE_RECONCILIATION`: missing SEC acceptance,
  ambiguous ticker reuse or other missing original evidence.
- `IDENTITY_OR_TEMPORAL_CONFLICTS_REQUIRE_REVIEW`: snapshot identity
  collision or proven stored-time ordering anomaly in the sample.
- `BLOCKED`: live DB missing or required tables missing. No repair.

## Next engineering steps after the diagnostic

- Resolve ambiguous ticker/CIK mappings using historical listing
  start/end records, share-class FIGI, SEC filings and dated aliases;
  freeze approved crosswalk in an audited source-controlled schema.
- Import and link authoritative SEC submissions `acceptanceDateTime`
  by accession (with bounded provider requests and SEC fair-access);
  preserve source timestamps, corrected/restated filing chronology.
- Rerun audit on immutable DB backup after import and then run WF9
  original PIT controls before any canonical feature promotion.

Do NOT use this script to delete facts, set guessed acceptance times,
or automatically mark a model/backtest `COMPLETE_AND_ACTIVATED`.
