# Phase25Z Research Backtest V2 — experimental sensitivity, not canonical performance

Date: 2026-10-10. This incremental V2 reads existing private Phase25W, Phase25X, Phase25Y-A and Phase25Q staging. It does not rerun their source-building workflows, download data, open operational.db, run WF9 or train Learning V3. The 25-symbol cohort is selected with full-window hindsight, so no numeric result is an OOS or investable return. Canonical accepted securities/dates remain **0/0**.

## Actual Windows result

| Diagnostic | Value | Meaning |
| --- | ---: | --- |
| Source adjusted-close monthly index | 1.1904467091 | Phase25Y-A baseline reproduced exactly. |
| Source close monthly index | 1.0899443828 | Source-price comparison, not an independently certified return. |
| Cross-sectional 5th/95th percentile winsorized alternative | 1.0208601321 | Monthly source returns capped before equal weighting; sensitivity estimator only. |
| Cross-sectional monthly median alternative | 1.0599952794 | Median of 25 source returns each month; sensitivity estimator only. |
| Excluding CETX, then reweighting 24 | 1.5072921497 | Largest absolute leave-one-out change; full minus omitted = −0.3168454407. |
| Excluding AGMH, then reweighting 24 | 1.1061411655 | Full minus omitted = +0.0843055436. |
| Largest exact signed index contribution | CETX −0.2207591916 | Sum of all 25 signed contributions ties exactly to 0.1904467091 index change. |
| AGMH exact signed index contribution | +0.0954962780 | Its Aug–Sep 2025 adjusted source return was +3.2448979592. |
| Largest absolute contribution share | 29.07595498% | CETX share of gross *absolute* signed contributions; not a portfolio weight. |
| Top five absolute contribution share | 58.86786782% | Concentration of computed index movement. |
| Source-date union / missing dates | 438 / zero for all 25 | This compares symbols only with each other, not with an official exchange calendar. |
| Month-end endpoint lags | zero for all 25 | Every pilot symbol shares the same source endpoint dates. |

The greatest monthly mean adjusted-minus-close return gap is +0.0132086192 for Dec 2024–Jan 2025. All 20 interval differences, 25 exact index contributions, 25 leave-one-out paths, top individual monthly moves, observed date coverage and seven machine-readable risk gates are in the private JSON. A dated historical sector map is absent from the bounded research sources, so sector concentration is `null`, not estimated from today's classification.

## Method and controls

V2 uses the Phase25Y-A fixed ex-post 25-name cohort and validates its 20-interval adjusted/close index against the previously saved private report. For each month, it calculates the simple source-price return of each name. Exact adjusted-index contribution is the preceding index level multiplied by the name's equal-weight monthly return component, then summed across intervals. Leave-one-out removes one name and reweights the remaining 24 each month. The winsorized alternative linearly interpolates cross-sectional 5th/95th percentile caps each month; the robust alternative compounds cross-sectional medians. These alternatives do not model executable portfolios, total return or model performance.

Missing daily dates are compared with the 25-name union of observed source dates. This cannot certify exchange sessions, suspended trading, holidays, delisted coverage or source adjustment correctness. No historical sector classification, commission, spread, slippage or terminal payoff is supplied. Machine risk states are `LOOKAHEAD_EX_POST_COHORT`, `SURVIVORSHIP_AND_DELISTING`, `RETROSPECTIVE_MEMBERSHIP`, `CORPORATE_ACTION_PRICE_FACTORS`, `SEC_AVAILABLE_AT` (all BLOCKED), `EXCHANGE_SESSIONS` (PARTIAL), and `HISTORICAL_SECTOR` (UNAVAILABLE).

**Research Mode: ENABLED_EXPERIMENTAL_ONLY. Canonical Mode: BLOCKED. WF9: BLOCKED. Learning V3: NOT_TRAINED.** None of the V2 output can promote a security-date, train a model or validate a strategy.

## Windows reproduction and artifact

Run from this V2 worktree with a fresh private output filename:

```powershell
$root = "$env:LOCALAPPDATA\S153ResearchTerminal\runtime"
& "E:\M10\.venv\Scripts\python.exe" -m scripts.phase25z_research_backtest_v2 --phase25w "$root\phase25w\pilot_cohort_research_only_v1.json" --phase25x "$root\phase25x\evidence_matrix_research_only_v2.json" --phase25y-a "$root\phase25y\research_only_backtest_v1.json" --manifest "$root\phase25q\staged_datasets\research_pit_28323984fb4f48b1\manifest.json" --out "$root\phase25z\research_backtest_v2_next.json"
& "E:\M10\.venv\Scripts\python.exe" -W error::ResourceWarning -m unittest tests.test_phase25z_research_backtest_v2 -v
```

Final actual Windows report for the desktop chart: `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25z\research_backtest_v2_desktop.json`, SHA-256 `cab8f4f9e6523b73594a44e0bb8beb373740e0a7cf2179329e484ea2a1486322`. It remains private; the source SHA-256 and input-report hashes are recorded inside it. Sources and operational database were not changed.
