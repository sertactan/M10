# Phase25X — eight-security research evidence matrix, no canonical admission

Date: 2026-10-10. Scope: Phase25W's real Windows research-only pilot, without rerunning Phase25Q/R/S/V/W or downloading vendor data. The audit reads existing private JSON and operational SQLite in `mode=ro` with `query_only=ON`. It writes a create-only JSON under private `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25x`. No price rows, private identity rows or SQLite content are committed.

## Selection and real Windows result

The Phase25W pilot has 25 securities. Eight with one present-day local CIK lead, 438 observed source price rows, 21 retrospective month-end ticker observations, and the greatest local SEC fact coverage among the uncomplicated P2 pilot candidates were selected. The local facts are period-end scoped and can have later filing dates; their count is research depth, not PIT proof. Phase25W's 464/464 identity collision rows remain quarantined. The eight selected ticker strings do not directly overlap those collision rows, which still does not certify their daily identity.

| Ticker | SimFinId | Present-day CIK lead | Period-scoped local SEC facts / accession count | Matching official 10-K fact rows | Historical CIK/share class | Complete actions | Independent adjusted price | Delisting/terminal payoff | SEC publication + feature `available_at` | Contemporary membership | Overall |
| --- | ---: | --- | ---: | ---: | --- | --- | --- | --- | --- | --- | --- |
| BRLT | 3172579 | 0001866757 | 333 / 10 | 42 | PARTIAL | BLOCKED | BLOCKED | BLOCKED | PARTIAL | BLOCKED | BLOCKED |
| BBCP | 11817699 | 0001703956 | 323 / 12 | 40 | PARTIAL | BLOCKED | BLOCKED | BLOCKED | PARTIAL | BLOCKED | BLOCKED |
| BKE | 196385 | 0000885245 | 318 / 11 | 46 | PARTIAL | BLOCKED | BLOCKED | BLOCKED | PARTIAL | BLOCKED | BLOCKED |
| AIV | 67201 | 0000922864 | 242 / 10 | 46 | PARTIAL | BLOCKED | BLOCKED | BLOCKED | PARTIAL | BLOCKED | BLOCKED |
| CNA | 446249 | 0000021175 | 212 / 11 | 38 | PARTIAL | BLOCKED | BLOCKED | BLOCKED | PARTIAL | BLOCKED | BLOCKED |
| AMSF | 6767743 | 0001018979 | 208 / 11 | 37 | PARTIAL | BLOCKED | BLOCKED | BLOCKED | PARTIAL | BLOCKED | BLOCKED |
| ACGL | 445596 | 0000947484 | 187 / 11 | 41 | PARTIAL | BLOCKED | BLOCKED | BLOCKED | PARTIAL | BLOCKED | BLOCKED |
| AFBI | 15337141 | 0001823406 | 165 / 12 | 24 | PARTIAL | BLOCKED | BLOCKED | BLOCKED | PARTIAL | BLOCKED | BLOCKED |

All eight have 438 source price rows and 21 retrospectively acquired monthly list observations. `PARTIAL` identity means only a single current local CIK lead plus an official annual filing anchor, not dated daily continuity or a complete traded share-class history. `PARTIAL` SEC means one official accepted-time anchor linked to local fact rows, not provider publication/ingestion `available_at` certification. All selected local period-scoped facts have `accepted_at = NULL`; their populated `available_at` values cannot be elevated to independent contemporaneous proof. A null `delisted_date` in local `security_master` is not a no-delisting certificate.

## Official SEC anchors

These official filing-detail pages identify the filer CIK, accession and SEC-displayed Accepted time. The time is recorded exactly as displayed by SEC; this audit does not infer time zone conversion, publication latency or feature ingestion time.

| Ticker | SEC accession | SEC-displayed Accepted time | Official filing detail |
| --- | --- | --- | --- |
| BRLT | 0001866757-25-000038 | 2025-03-13 17:12:35 | [SEC](https://www.sec.gov/Archives/edgar/data/1866757/000186675725000038/0001866757-25-000038-index.htm) |
| BBCP | 0001437749-25-000800 | 2025-01-10 08:30:35 | [SEC](https://www.sec.gov/Archives/edgar/data/1703956/000143774925000800/0001437749-25-000800-index.htm) |
| BKE | 0000885245-24-000051 | 2024-04-03 15:59:57 | [SEC](https://www.sec.gov/Archives/edgar/data/885245/000088524524000051/0000885245-24-000051-index.htm) |
| AIV | 0000950170-25-025775 | 2025-02-24 17:05:21 | [SEC](https://www.sec.gov/Archives/edgar/data/922864/000095017025025775/0000950170-25-025775-index.htm) |
| CNA | 0000021175-25-000008 | 2025-02-11 10:26:27 | [SEC](https://www.sec.gov/Archives/edgar/data/21175/000002117525000008/0000021175-25-000008-index.htm) |
| AMSF | 0000950170-25-030059 | 2025-02-28 16:28:37 | [SEC](https://www.sec.gov/Archives/edgar/data/1018979/000095017025030059/0000950170-25-030059-index.htm) |
| ACGL | 0000947484-25-000017 | 2025-02-27 16:14:56 | [SEC](https://www.sec.gov/Archives/edgar/data/947484/000094748425000017/0000947484-25-000017-index.htm) |
| AFBI | 0000950170-25-043249 | 2025-03-21 16:30:34 | [SEC](https://www.sec.gov/Archives/edgar/data/1823406/000095017025043249/0000950170-25-043249-index.htm) |

Annual reports provide issuer/share-class leads and may describe particular distributions. They cannot establish an exhaustive 2024-01-01 to 2025-09-30 corporate-action ledger or validate third-party adjustment factors. No independent adjusted-price provider artifact or complete delisting return feed was present in the existing approved Phase25Q/R/S/V/W sources or the read-only operational DB. The operational DB has zero corporate-action rows and zero 2024-2025 canonical membership rows as observed in Phase25W. This phase intentionally makes no surrogate adjustment from hindsight SimFin `Adj. Close`.

## Decision and missing provider

**Canonical admitted securities: 0; canonical security-dates: 0; WF9: BLOCKED.** No selected row passes every required gate. The missing evidence is a dated historical security master with traded share-class and exchange continuity; complete split, dividend, spin-off, merger and rights ledger; an independent adjusted daily-price feed with factor methodology and delisting terminal payoff; contemporaneously captured 2024-2025 universe membership; and a publication/ingestion audit for each SEC feature. A provider or separately archived source for these items must be identified and licensed/validated before a new per-security/date admission review. Retrospectively obtained 2026 list and prices are not 2024-2025 PIT observations.

## Reproduce safely on Windows

Run from this Phase25X worktree with the existing `E:\M10\.venv\Scripts\python.exe`. The output filename must be new because the CLI refuses overwrite and confines reports to private `%LOCALAPPDATA%`.

```powershell
$root = "$env:LOCALAPPDATA\S153ResearchTerminal\runtime"
& "E:\M10\.venv\Scripts\python.exe" -m scripts.phase25x_evidence_matrix --phase25w "$root\phase25w\pilot_cohort_research_only_v1.json" --phase24 "$root\phase24\simfin_sec_cik_candidates.json" --operational-db "$root\data\runtime\operational.db" --out "$root\phase25x\evidence_matrix_research_only_v2.json"
& "E:\M10\.venv\Scripts\python.exe" -m unittest tests.test_phase25x_evidence_matrix -v
```

Real private reports: `evidence_matrix_research_only_v1.json` and final `evidence_matrix_research_only_v2.json` in the private Phase25X directory. Both contain the same evidence payload (SHA-256 `44f2b269fb7c86555eaa834b95e70866d08ff2a1b85c2a88bc309db7a67ff581`). The final v2 run also enforces private output confinement and per-row quarantine checks. Tests are synthetic and contain no user data. No S15/S16 formula, production model, Hermes code, operational database or upstream source was changed. No PR is merged automatically.

