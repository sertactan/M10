# Scoring V8 — independent other-model evidence and PIT readiness gate

Date: 2026-10-11 JST. Base: `7af654a` / PR #181, the five-stock V7 Research
checkpoint. This report uses the **existing, sealed private V7 report** and
existing contracts; it does not refetch SEC filings, crawl V1–V7 history,
calculate synthetic issuer scores, change canonical specifications, or modify
the production DB/EXE. Its purpose is to make acceptance blockers deterministic
and independently visible to the V8 integration team.

## Real replay input and verification depth

- Input: `E:/M10/.scoring_v7_private/scoring_completion/piotroski_s9/report.json`.
- Source SHA-256: `425753df2a65d249bfb8c2ff633c87fcb3f63d92d2a0dca5ee57f4992b81e364`.
- Output: **private**, `E:/M10/.scoring_v8_private/model_gates_v8.json`.
- Actual mode: `V7_SHA256_SEAL_AND_CONTRACT_ONLY_NO_RAW_SOURCE_REPLAY`.
  The local `.sha256` matches the report bytes. The fifteen previously accepted
  Research scores are checked against **their full-precision V7 values**,
  including the genuine `INOD S11=0.0`; all model/count/zero-PIT controls pass.
  This V8 pass does **not** independently replay all original SEC bodies and
  raw-data receipts. V7's own source replay has separate prior acceptance; use
  both `--phase27` and `--phase28` if underlying revalidation is required.

## Current five-stock evidence gate

The counts below are candidate financial or research factors. They are not
canonical PIT factor acceptances; a renormalized partial weighted average is
not a fully evidenced frozen-model score.

| Ticker | Complete discovery research factor candidates /48 | Control input candidates /12 | S14 accepted legs /6 | S16 raw feature candidates /22 | S16 normalized PIT /22 |
|---|---:|---:|---:|---:|---:|
| INOD | 3 | 2 | 3 | 6 | **0** |
| TMDX | 3 | 2 | 2 | 6 | **0** |
| CRMD | 1 | 2 | 3 | 6 | **0** |
| PENG | 0 | 1 | 2 | 6 | **0** |
| ETON | 2 | 2 | 2 | 6 | **0** |

**S1–S3 / Core48 / Control12 / H:** All five issuers lack 48 individually
complete discovery factors, all 12 verified failure controls and independent
dated winner/control cohorts for historical `H`. D01/D02 are explicitly
partial where present, Control GP has missing forward/structural legs, and
router/Gate6/N61/FPR partially renormalized diagnostics cannot satisfy their
full frozen chains. **Full S1, S2, S3 = 0 each.** The current feature map is
Research-only, with no new canonical normalizations established by V8.

**S4/S5 and quality:** All five S4 and S5 still lack a complete accepted
Beneish ratio and interaction package. INOD's B_Q evidence is **5/7** risk
legs, with DEPI (pure depreciation) and LVGI (comparable interest-bearing
debt) missing; S6 is **5/7**, with inventory and independently resolved
RSST components outstanding. S13 has **0/7** signed AUD/RPT/REC/DIL/REV/ACQ/GOV
rubric decisions; source passage matches alone are not signed risk findings.
INOD S14 is **N/A (3/6)**, retaining genuine S11 `0.0`, not N/A. CRMD is
3/6; TMDX, PENG and ETON are 2/6. No unseen B_Q/S6/S13 component is set to
zero or neutral. The conditional prior-year zero-debt denominator remains a
`SPEC_EDGE_CASE`, not a new LVGI rule.

**S15.3:** The frozen V1.2 engine reports four unmet gates for each company:
`S15.2`, `M10>=5/7`, `T10>=5/7`, and at least 70% essential coverage for the
selected route. V1.4 reports 22 missing requirements for INOD/TMDX/CRMD/ETON,
24 for PENG (including its V1.4 feature, magnitude, route and evidence
requirements). V1.4.1 reports `V1.2 READY` missing for all five. Each version
has **zero complete Research scores**. V1.2's prerequisite is not inferred
from a sparse or partially computed numeric intermediate.

**Task 13 — SEC/historical PIT:** INOD has two distinct SEC acceptance-time
candidates in this report, but **zero** verified `public_dissemination_at` and
**zero** verified `historical_provider_available_at` for those sources. SEC
acceptance and present-day archive retrieval do not prove past data-feed
availability. Other stocks are similarly evaluated from their original
individual report evidence; this pass does not reconstruct historical
accessibility. Task 13 remains **PARTIAL**.

**Task 14 — S16-C:** All 22 expected frozen feature IDs occur exactly once
for each stock. Six have research raw-input candidates (volume ignition,
momentum acceleration, compression, extension risk, liquidity risk and liquidity
elasticity); **0/22** are independently PIT normalized and accepted.
Consequently **S16-C = N/A**, five selected stocks are not a complete
same-date normalization universe, and historical canonical coverage is
**0 securities / 0 dates**. WF9 remains **BLOCKED** and Learning V3
**NOT_TRAINED**.

**Task 15 — S16-E:** Numerical normalization, out-of-sample calibration and
activation still require explicit user approval. **S16-E = N/A**,
`PENDING_APPROVAL`. No independent score is derived from S16-EA alert logic.

**Task 16 — S16-EA:** The cached minute/candidate event evidence remains
Research-only. The first-publication event timestamp, real same-clock replay
population, verified session calendar and independent timestamped bar
provenance are missing. **Verified early alerts = 0**; task **PARTIAL**.

## Machine checks and integration contract

Added four isolated files:

1. `app/scoring_v8_model_gates.py` — byte-independent baseline assertions,
   candidate-versus-canonical evidence gates, explicit null/zero preservation,
   S1–S16 and Tasks 13–16 audit JSON.
2. `scripts/scoring_v8_model_gates.py` — read-only CLI. An optional output
   path is opened in exclusive-create mode and cannot overwrite an old report.
3. `tests/test_scoring_v8_model_gates.py` — eight `unittest` regression cases
   covering 15 fixed accepted scores, true S11 zero, 22 feature PIT inflation,
   partial S1/S15.3 scores, S13, S14, SEC-publication boundary and SHA seal.
4. This document.

Execute from the V8 checkout:

```powershell
python -m unittest discover -s tests -p test_scoring_v8_model_gates.py -v
python scripts/scoring_v8_model_gates.py --report E:/M10/.scoring_v7_private/scoring_completion/piotroski_s9/report.json --out E:/M10/.scoring_v8_private/model_gates_v8_new.json
```

The CLI's input is intentionally restricted to the original **V7 sealed
15-score checkpoint**. To evaluate a future V8 score expansion, create an
explicit next acceptance contract after independent evidence replay; do not
silently rewrite the baseline or treat these coverage tables as completed
scores. The default CLI verifies the V7 report SHA-256 and contract; optional
paired `--phase27 PATH --phase28 PATH` invokes the existing deeper V7 source
validator if original staging databases and private receipts are available.

**Validation:** Eight local Python 3.13 standard-library unittest cases pass,
`compileall` passes, `git diff --check` passes. The real, separately sealed V7
input passes the offline audit. No new complete model score or canonical
PIT claim was justified by these unchanged inputs.
