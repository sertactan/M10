# Phase25Y-A — read-only experimental backtest of the Phase25W pilot

Date: 2026-10-10. This is a reproducible **research-only price arithmetic experiment**, not canonical performance, WF9, an investment recommendation or an S15/S16 result. The code reads existing private Phase25W and Phase25X reports plus the existing Phase25Q research staging SQLite in `mode=ro`/`query_only=ON`. It never opens operational.db, downloads data, changes a model or writes back to a source. The private JSON output is create-only and confined to `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25y`.

## Experiment and real Windows result

The cohort is exactly the 25 Phase25W pilot securities selected **after** their complete 2024-01 through 2025-09 price coverage was visible. For each symbol, the program takes the last available source daily row in each of the 21 months, calculates the source `Adj. Close` and ordinary `Close` return to the next month, equally weights the 25 simple returns, and compounds 20 monthly intervals. The index starts at 1.0 at the January 2024 source endpoint; no turnover, slippage, dividend cashflow, tax, fee or execution is modeled. The 25 symbols all have 438 valid source rows and 21 retrospective monthly ticker observations. The program refuses missing endpoints, identity collision symbols, nonpositive prices or any change to the Phase25W/X zero-canonical gate.

| Quantity | Actual read-only experiment |
| --- | ---: |
| Fixed ex-post pilot symbols | 25 |
| Monthly source endpoints | 21 |
| Monthly intervals | 20 |
| Final source `Adj. Close` arithmetic index | 1.1904467091 |
| Final source `Close` arithmetic index | 1.0899443828 |
| Canonical admissions | 0 |
| WF9 runs | 0 |
| Phase25W identity collision rows left quarantined | 464/464 |

The adjusted index's 0.1904467091 change from 1.0 is **not a validated 19.04% investment return**. The difference from the ordinary close index is evidence that source adjustment assumptions matter; neither series has independently verified total-return adjustment or terminal payoff. A single source symbol, AGMH, has a 3.2449 simple adjusted-price ratio return in the August–September 2025 interval, illustrating extreme concentration in this research sample. No benchmark comparison, precision@K, Sharpe, drawdown, cost estimate or model promotion is reported.

## Bias and data availability ledger

| Issue | Observed limitation | Consequence |
| --- | --- | --- |
| Lookahead | Phase25W chose the 25 using full-window 438-bar coverage and 21 lists acquired retrospectively in 2026. | A 2024 investor could not construct this same selected cohort from proven contemporaneous inputs. |
| Survivorship | The fixed ex-post pilot omits missing histories, delisted payoffs and the 464 quarantined conflicting identity rows. | The direction and size of selection bias cannot be estimated from the 25-symbol subset. |
| `available_at` | Phase25X found only partial SEC Accepted anchors; local SEC facts have no `accepted_at` and no verified ingestion archive. | No SEC feature enters this arithmetic; attaching one later would require dated publication and feature availability proof. |
| Corporate actions | Full distributions, splits, spin-offs and rights are not reconciled to the source factors. | Source `Adj. Close` cannot be accepted as an independent total-return series. |
| Execution | Price endpoints represent a hypothetical monthly rebalance, without real fills, liquidity or costs. | The index is a numerical diagnostic, not a tradable strategy record. |
| Canonical gate | Phase25X admits 0 security-dates; historical daily CIK/share-class and contemporary PIT membership are missing. | WF9 remains BLOCKED. |

## Reproduction

Run in this Phase25Y-A worktree with the existing Windows environment and a new output filename:

```powershell
$root = "$env:LOCALAPPDATA\S153ResearchTerminal\runtime"
& "E:\M10\.venv\Scripts\python.exe" -m scripts.phase25y_research_only_backtest --phase25w "$root\phase25w\pilot_cohort_research_only_v1.json" --phase25x "$root\phase25x\evidence_matrix_research_only_v2.json" --manifest "$root\phase25q\staged_datasets\research_pit_28323984fb4f48b1\manifest.json" --out "$root\phase25y\research_only_backtest_v2.json"
& "E:\M10\.venv\Scripts\python.exe" -m unittest tests.test_phase25y_research_only_backtest -v
```

Actual private v1 output: `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25y\research_only_backtest_v1.json`, SHA-256 `d0964746b77a3328c34b76cf3dbd71edab8ce207495d2c505582cbc72d3521d2`. The JSON stores the exact input hashes, cohort ticker strings, all 20 interval diagnostics and six limitations. It is not committed to GitHub. The separate Phase25Y-B provider feasibility work does not feed this backtest; each workstream has its own branch and PR.
