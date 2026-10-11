# V13 Task 15 — S16-E Estimated outside-sample readiness

**Status:** `PENDING_APPROVAL` / `DATA_MISSING`. S16-E remains **OFF**. No
Estimated score, calibration metric, performance claim or production activation
was produced.

## Real dated input checked

The Phase25W private research pilot contains **25** distinct SimFin security
IDs. Each candidate has **438** source price rows covering 2024-01-02 through
2025-09-30. This is useful dated *Research* coverage but not a complete S16-E
as-of case cohort. The source's 21 historical listing snapshots were acquired
retrospectively in 2026, and its issuer identity, adjusted total return,
delisting, SEC/publication and provider-availability gates are unverified.
The pilot contains no ten-factor S16-E historical provider capture envelopes,
contemporaneous bid/ask spread, first-public catalyst clock, verified float,
five-session source calendar or mature case-level outcomes. It cannot be
scored as if those observations existed in 2024–2025.

The read-only audit saved
`E:/M10/.master_tasks_v13_private/estimated/s16e_oos_readiness.json` and an
SHA-256 sidecar. Report digest:
`7b3b39935fda7214f98a45d0b4be167d0ec55b3d905d371bc55ad4094e2a0a5a`.
`--verify` reproduced the report exactly from the original pilot bytes. The
source SHA and exact missing-gate list are in the private output. **Eligible
outside-sample cases: 0; metrics: null.**

## Engineering acceptance gate

`app/scoring_v13_estimated_oos.py` defines an explicitly proposed, untouched
research split: TRAIN 2024, VALIDATION January–April 2025, HOLDOUT May–September
2025. This is an evaluation plan, not model approval or a fitted threshold.
The case gate checks decision, outcome-end and label-available clocks; labels
must mature before evaluation and may not cross from train into validation or
from validation into holdout. It requires a verified five-session horizon,
historical security identity, corporate actions, delisting payoff,
contemporaneous membership and all **10** original draft S16-E inputs with
historical provider capture no later than the decision clock. Missing inputs
fail closed. The real pilot has no eligible case-level records to feed this
gate; synthetic unit cases only check its leak prevention.

**Still required:** a genuinely captured historical ten-factor source panel,
preselected exchange session calendar and benchmark, mature outcome ledger
including delisted names and corporate actions, preregistered alert/outcome
thresholds, purged walk-forward folds, untouched final holdout and source
licenses. Only then could OOS precision/false alerts/drawdown/costs be reported.
Formula weights, normalization and activation also need separate user approval
for an exact S16-E version. Without that decision S16-E stays N/A/OFF even if
future data become complete. S16-C remains separately canonical-gated.

Validation: four scoped tests passed; the direct CLI's private `--verify`
passed. No frozen model, live database, source file, runtime registry or
installed application was changed.
