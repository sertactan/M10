# Phase 25S — SEC-backed SITC split / CURB spinoff research controls

**Purpose:** Advance real event verification without confusing an officially documented corporate action with a certified vendor-adjusted price series or a complete daily historical SimFinId/CIK/class identity.

## Independently source-backed historical events

| Security | Official SEC filing | Action | Actual time / terms | What the evidence proves |
|---|---|---|---|---|
| SITC common / CIK 0000894315 | [2024 Form 8-K](https://www.sec.gov/Archives/edgar/data/894315/000095017024099069/sitc-20240816.htm) | Reverse split | Effective **Aug 16, 2024, 5 PM EDT**, **1 new share per 4 old**; adjusted trading **Aug 19**; new CUSIP **82981J 851** | Issuer, NYSE common share event terms at those dates |
| SITC common / CIK 0000894315 | [2024 Form 8-K](https://www.sec.gov/Archives/edgar/data/894315/000119312524231147/d104351d8k.htm) and [official exhibit](https://www.sec.gov/Archives/edgar/data/894315/000119312524231147/d104351dex991.htm) | CURB spinoff | **Oct 1, 2024** distribution of **2 CURB common per 1 SITC common** owned at **Sep 23 record date** | Documented noncash spinoff in addition to reverse split |

The first SEC report was signed **Aug 20** and itself documents the earlier Aug 16 / Aug 19 event; the research script does **not** invent that the filing's contents were available before signature. To certify public SEC \`available_at\` timing, the accession acceptance/dissemination timestamp must be retrieved and separately documented.

The Oct 1 spin-off is NOT a simple $3.25 cash distribution or an ordinary single-ticker stock price adjustment. Proper total returns would require actual CURB trading/when-issued conditions, eligible distribution rights, the time-dependent SITC and CURB price bases, contemporaneous liquidity and delist terminal proceeds where relevant. Therefore no total-return claim is computed.

## Windows real-source paired price check

Use the pre-existing private Phase25Q versioned stage (original 435MB SimFin input and 21 listing archives left untouched):

\`\`\`powershell
cd "$env:LOCALAPPDATA\S153ResearchTerminal\runtime\phase25q\code_checkout"
$manifest="$env:LOCALAPPDATA\S153ResearchTerminal\runtime\phase25q\staged_datasets\research_pit_28323984fb4f48b1\manifest.json"
& "E:\M10\.venv\Scripts\python.exe" -m scripts.phase25s_sitc_official_action_price_diagnostics --manifest $manifest
\`\`\`

**Run from a worktree that has Phase25S code**, not a stale checked-out Phase25Q branch. Source SQLite is opened \`mode=ro\` with \`PRAGMA query_only\`; \`quick_check\` runs before any paired research price calculations.

The selected vendor source bar dates are **Aug 16 / Aug 19** and **Sep 30 / Oct 1 2024**. Even if both bars exist and a factor looks similar to the announced reverse split, two retrospectively adjusted bars cannot certify: historical issuer identity, ex-date market mechanism, all splits/dividends/spinoffs, adjusted price continuity, CURB dividend-equivalent value, delisted returns, or SEC public information availability.

Private report:
\`%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25s\sitc_official_reverse_split_spinoff_price_diagnostics.json\`

The current local Windows session may be disconnected. The model must not report a real local Phase25S run until Windows command and report contents are observed.

**No changes** to production \`operational.db\`, P1 source prices, SEC raw evidence, M10 desktop, Hermes PR #150, S15.3, S16 or Learning V3 models. All existing canonical/backtest acceptance remains blocked until independently verified.
