# V12 Tasks 13–16: historical availability and event evidence

## Contract boundary

Original sources reviewed: `docs/S16_V1_CANONICAL_SPEC.md` (frozen S16 V1.0),
`docs/S16_PHASE3_HISTORICAL_FEATURE_RECONSTRUCTION.md`,
`core/models/s16_ea_v13.py`, `app/scoring_event_evidence.py`,
`docs/PHASE28_S16_E_ESTIMATED_DESIGN_DRAFT.md`,
`app/scoring_estimated_draft.py`, and the V11 audit. The Phase 3 text calls
SEC acceptance a conservative filing-entry clock, while the later Phase 25P
publication gate requires independent dissemination and provider arrival.
For historical provider features, V12 applies the stricter gate. This does not
edit the frozen model or reinterpret prior Current Research scores as PIT.

| Task | V12 verified work | Still required for DONE | State |
|---|---|---|---|
| 13 SEC historical PIT | Byte-sealed INOD Submissions response replay; 2 genuine 10-K acceptance stamps; distinct first-public, provider-first-available, capture and revision gates; as-of version selector | Independent dated dissemination/capture logs, historical issuer mapping, actual versioned fact bodies and broader source coverage | PARTIAL |
| 14 S16-C | Original 22-feature, same-date normalization and PIT gates confirmed; no candidate promoted | Historical source arrival and 22/22 normalized features with source-valid cross-sectional universe and replay | BLOCKED (0/22) |
| 15 S16-E | Existing isolated draft and OOS replay harness inspected; approval packet below | Genuine frozen cohort, provider capture, matured labels, holdout calibration, user approval of formula/version and activation | PENDING_APPROVAL, data missing |
| 16 S16-EA | Existing event-clock validator and original V1.3 engine inspected; no valid alarm manufactured | First news publication, provider delay, exchange calendar, same-clock bars, complete premarket baseline and outcome audit | PARTIAL (0 verified alerts) |

## Actual SEC byte replay

The local read-only SEC Submissions probe for INOD CIK `0000903651` returned
HTTP 200. Its captured response is 162,393 bytes; independent SHA-256 replay
matched the existing receipt `070461656ae36691ad952bd53e529dd48fbb74b8f7191637d3c6bb79e27910f3`.
Two original 10-K administrative rows were extracted:

| FY | Accession | SEC accepted UTC | First public | Historical provider arrival |
|---|---|---|---|---|
| 2025 | `0001104659-26-020655` | 2026-02-26 22:22:13 | Unverified | Unverified |
| 2024 | `0001410578-25-000194` | 2025-02-24 19:09:04 | Unverified | Unverified |

The response was captured 2026-10-10 17:11:52.942670 UTC. This proves
current retrievability and administrative acceptance values, not that the
provider had either filing in 2025 or February 2026. Both rows fail PIT
admission for first-public time, historical provider arrival, contemporaneous
capture and historical ticker/CIK mapping. `accepted_pit_versions=0`.

Private output: `E:/M10/.master_tasks_v12_private/pit/inod_submissions_pit_audit.json`.
The existing report was replayed byte for byte with `--verify`; its SHA-256
sidecar is `inod_submissions_pit_audit.json.sha256`, digest
`16da392e31082b15962c433fa9441666c2ac66afa8824833b900b7aacf803ebb`.
Verification recomputes from the original sealed SEC response and receipt,
compares exact output bytes, and checks the sidecar. It did not replace the
existing report. A missing sidecar is created only after exact replay succeeds;
an existing mismatched sidecar fails closed.
The private SEC response bytes and receipt remain at their original local
paths. Only the audit code and this metadata description belong in Git.

`app/scoring_v12_pit_audit.py` rejects absent or naive clocks, backward clock
chains, unsealed source bytes, late arrival, ambiguous original/amendment
chains and present-day retrieval claimed as contemporaneous capture. A
revision is selected only after that version itself passes all as-of gates;
future amendments cannot overwrite the original historical view. Source
attestations still require independent authentication; unit tests with
synthetic timestamps prove code behavior, not real provider history.

## S16-E activation decision packet

**Decision:** keep S16-E OFF (current safe state), or approve a *specific,
versioned* Estimated formula for isolated evaluation after the missing data
and holdout checks are complete. Approval of an experiment alone would not
authorize installation or production activation. The existing
`S16-E-EXPERIMENT-DRAFT-0.2` weights and gates are a proposed design, not a
recovered frozen model. A separate approval would need to identify the exact
formula/version, source licenses, 10 required input definitions, normalization,
hard gates, risk penalties, cohort/horizon, OOS acceptance thresholds and
activation scope. Without approval, S16-E remains N/A/OFF; S16-C remains
separate. After an approval and source acquisition, run the preregistered
as-of replay and untouched holdout, report Precision@K, false positives,
drawdown and costs only on fully mature cohorts, then test staging separation
from S16-C. No activation or performance claim occurred in V12.

## Verification

`python -m unittest discover -s tests -p test_scoring_v12_pit_audit.py -v`:
7/7 pass. Real sealed INOD replay: 2 rows, 0 PIT eligible. The original
17 Current Research scores, S16-C 0/22, S16-E OFF and S16-EA 0 verified
alerts are unchanged.
