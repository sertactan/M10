Phase 25T-U — M10 desktop PIT / Learning evidence interface

Integrated existing native PySide6 desktop: PIT / LEARNING header button, a strictly read-only local historical evidence dialog, and historical_pit_evidence_service with unit and Qt tests. No scoring or model changes.

The service reads only local private Phase25Q versioned staging, Phase25R independently matched QA, and optional Phase25S SEC issuer action / real-price-pair report, never operational.db. Stage manifest uses a full SHA256 staging_version, folder uses first 16 hex digits. A mismatch, missing file, excessive-size file or unexpected canonical flag is NOT VERIFIED.

Historical window Jan 1 2024 through Sep 30 2025; source-only observed 21 retroactively acquired monthly listing files, 128088 source month/ticker/exchange rows and 2110622 SimFin valid daily source price rows. Verified Phase25R source price count is 1557903 of 3557 strong candidates. Retrospective membership is NOT contemporaneous daily PIT proof. 464 month/ticker/exchange conflicting issuer/IPO rows impact 7 strong tickers. Phase25S real-price-pair count is displayed ONLY if a local report of the identical staging version exists; official issuer actions are not adjusted-price certification.

Operator: in native M10 Windows desktop click PIT / LEARNING and REFRESH (NO MODEL TRAINING). This is evidence presentation, not a trading signal, real WF9 run, Learning V3 training, model deployment or automatic import. Missing canonical CIK/security class continuity, delisting terminal return, dividend/split/due-bill/spinoff vendor adjustment, SEC dissemination public available_at and mature labels still block canonical learning.

Complete Phase25S local real-price testing later using the existing private staging manifest at %LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25q\staged_datasets\research_pit_28323984fb4f48b1\manifest.json. Run python -m scripts.phase25s_sitc_official_action_price_diagnostics --manifest <manifest> in a separate up-to-date M10 worktree. DO NOT switch or modify live Hermes development branch or load source data into GitHub.

Regressions: tests/test_phase25tu_desktop_pit_evidence_status.py validates stage hash, fail-closed unknowns, stale report rejection, and native PySide6 dialog. CI is required before merger.
