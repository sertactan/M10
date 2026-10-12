# MERİDYEN — Personal Research AI-Assessed V1.0

## Independence

The V14 base is abd4f09ae941c0e7e1de728b6f5831c5b5c5e176.
Original S1–S16, 17 full Research scores, 14/40 Verified gates,
0/22 S16-C PIT features, S16-E OFF, the operational database and installed
Personal Edition 1.0.6 are out of scope. Personal scores never count as
Original Verified, canonical PIT, CPA approval, or a trading signal.

## Windows usage

Run the existing PySide6 ResearchTerminalWindow with E:/M10/.venv/Scripts/python.exe
and open the new PERSONAL AI RESEARCH tab. The tab supports ticker selection,
FY selection, loading a local SEC evidence JSON, calculations, separate
Original/Personal comparisons, seven S13 categories, source link
double-click, JSON/CSV export, and error feedback.

Offline CLI from the isolated worktree:

    E:\M10\.venv\Scripts\python.exe scripts\personal_research_run.py --ticker INOD --root E:/M10

Run with INOD, CRMD, ETON, PENG, or TMDX. Optional arguments:
--period-end YYYY-MM-DD, --packet path/to/packet.json, --sidecar path,
--output report-prefix. Data goes to an **isolated sidecar** under
E:/M10/.personal_research_ai_v1_private/runs.sqlite3 and JSON/CSV exports,
without modifying the production tables. Sidecar writes are append-only,
source receipts are checked, and SQLite connections explicitly close.

## Sources and statuses

Input rows identify issuer, CIK, period, 10-K/10-Q, accession,
accepted-at, captured-at, scale, currency, exact SEC URL and locator,
verbatim quoted passage, source byte SHA-256, provenance and actor type.
The local source loader requires real SEC bytes, checks their SHA, verifies
the excerpt occurs in the original bytes, and cross-checks the reported
number against that excerpt. Invalid rows are rejected. Historic provider
arrival is not inferred from present-day file access.

Classes: SOURCE_EXACT; SOURCE_DERIVED; AI_ACCOUNTING_INTERPRETATION;
SCENARIO_ASSUMPTION; UNRESOLVED; EXPERT_REVIEWED. Numeric results are
EXACT, SCENARIO or UNQUANTIFIABLE; nonnumeric status labels explain missing
inputs and review requirements. No uncalibrated percentage confidence is
generated.

S6 invokes the frozen app.recovered_dechow.calculate_dechow with its
original accounting and reviewer gates. The INOD RSST diagnostic is
independently replayed from sealed source data and remains a candidate,
not a complete S6 original score. Inventory, short/long investment
classification and three-way WC/NCO/FIN review are still unresolved.

B_Q exposes seven independent component ratios/normalized risks:
DSRI, GMI, AQI, DEPI, SGAI, LVGI, TATA. The full result invokes unchanged
app.recovered_beneish.calculate_beneish. Pure depreciation never uses
combined D&A, total debt cannot be silently replaced by a borrowing
subtotal, and 0/0 denominator cases remain unresolved. Serious flag
interaction requires explicit sourced review.

S13 weights AUD .25, RPT .15, REC .20, DIL .15, REV .10, ACQ .10 and
GOV .05 follow the recovered contract. Each risk must be assigned 0, 25,
50, 75 or 100 by a sourced Personal AI proposal. Independent serious
issues impose +5/+10/+15 points of risk for 3/4/5+ issues, capped at 100.
Incomplete or contradictory proposals remain REVIEW_REQUIRED. AI does not
sign Original S13. All 27 legacy V5 source-referenced observations are
preserved, though full original filing body offsets and authorized decisions
remain missing, so the current company risk score is null.

Optional PERSONAL_S14_SCENARIO directly calls the untouched
core.scoring.s1_s14.s14 calculation after **all six** source-aligned legs
are available. The true INOD S11=0 is preserved. The original geometric
logarithm floor and forensic/conflict penalties are unchanged. Incomplete
inputs yield null, never a synthetic quality score.

## Five issuer source receipts

The legacy inputs require an exact match against their private *.sha256
seals and are independently recomputed where possible:

| Ticker | Source-backed partial Personal evidence | Whole-model status |
|---|---|---|
| INOD | FY2025 RSST aggregate 0.059140128066; 5/7 B_Q research components; 27 unsigned S13 observations | S6/B_Q/S13/S14 unresolved |
| CRMD | V10 pure DEPI 0.761229684221 | B_Q partial |
| ETON | V10 pure DEPI 5.328106852497 | B_Q partial |
| PENG | V10 pure DEPI 1.069471644355; FY ends 2025-08-29 | B_Q partial |
| TMDX | FY2025 PPE and combined D&A, insufficient to identify pure depreciation | B_Q partial |

Partial component numbers above do not establish an entire seven-leg score.
Local source seals alone are insufficient to verify original public timing.

## LLM and provenance

The optional structured offline review importer is in
app/personal_research/llm_review.py and the strict seven-category validator
is app/personal_research/s13_assessed.py. An input review needs dated
filings with original bytes, anchored findings, seven explicit AI risk
assessments, counter-evidence and a source-backed serious flag independence
review. Conflicting interpretations trigger REVIEW_REQUIRED. The default
provider is OFFLINE_MANUAL_STRUCTURED. External LLM calls are disabled;
the engine never uploads private filing bodies or buys API tokens.

## Tests and change boundaries

Test with E:/M10/.venv/Scripts/python.exe -m unittest -q
tests.test_personal_research_core tests.test_personal_research_beneish
tests.test_personal_research_s13 tests.test_personal_research_ui.
Original recovered S6/Beneish/quality regressions and the five Windows
ticker UI smoke checks are also run. Synthetic test fixtures are never
reported as genuine issuer evidence.

Modules are in app/personal_research; UI lives in
app/ui/personal_research_page.py. Only app/ui/main_window.py is altered
to register the new research tab. Frozen formula files and the original
master task acceptance records are untouched. The missing SEC accounting
classifications and professional review must still be obtained before
full original or personal numeric results can be supported.
