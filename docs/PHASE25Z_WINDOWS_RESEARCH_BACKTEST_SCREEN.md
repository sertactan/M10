# Phase25Z Windows Research Backtest screen

Date 2026-10-10. The existing PySide6 Research Terminal gains a `RESEARCH BACKTEST` tab. It reads only the fixed private Phase25Z V2 JSON at `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25z\research_backtest_v2_desktop.json`; it does not open a database, call a provider, recalculate canonical models or start WF9/Learning. The tab validates the research-only schema, 25-symbol cohort, 20 monthly observations, required risk ledger, 0 canonical counts, blocked WF9 and untrained Learning V3 before rendering.

The view shows the 25 pilot tickers and date window, adjusted/close monthly source-index lines, all 25 exact signed index contributions and leave-one-out indices, the top 15 single-name monthly source moves, input/source/report SHA-256, lookahead/survivorship/corporate-action/`available_at` warnings and separate Research/Canonical status labels. Selecting it hides the ordinary stock model header and historical backtest context so they cannot be visually mistaken for this experimental cohort. Switching back restores them. A refresh button rereads the existing private JSON; a missing or invalid report is shown as unavailable, never as canonical.

## Real native Windows check

The tab was opened on the native Windows Qt platform with the actual private Phase25Z V2 report. Observed: window visible, two chart series rendered, 25 contribution rows, 15 outlier rows, ordinary model context hidden. Upper and scrolled-lower screenshots were saved privately:

- `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25z\research_backtest_windows_screen_v2_top.png`
- `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25z\research_backtest_windows_screen_v2_bottom.png`

The images were visually inspected: title and status read `EXPERIMENTAL ONLY`/`CANONICAL MODE BLOCKED`; chart has two distinct monthly lines; top rows show CETX and AGMH; source hashes and all risk warnings appear after scrolling. Screenshots contain private local paths and stay out of GitHub.

Four new synthetic Qt tests pass locally. Existing pytest-based desktop suites could not run in the Windows project venv because that venv does not contain pytest; GitHub CI installs pytest and runs the complete repository suite. No production installer has been modified in this PR. The private data and 27-item master program are not declared complete by this UI milestone.
