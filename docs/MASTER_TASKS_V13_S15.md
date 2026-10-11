# V13 S15.3 V1.2 / V1.4 / V1.4.1 acceptance work

The original `MERIDYEN_S15.3_CANONICAL_FINAL_v1.0`, V1.4 five-artifact
manifest and V1.4.1 completion specification remain unchanged. The V12
five-issuer source report and SHA seal were replayed offline. The V13 private
receipt is `E:/M10/.master_tasks_v13_private/s15/source_route_audit_v1.json`,
SHA-256 `75dfeaa491aa2daa62a29cb9207c5fcf8df9f32e05ee70a3d1923a9346f4242d`.

## Real source engineering completed

The new audit independently reconstructs the selected route's essential
coverage from the original engine's actual component values and refuses a
changed coverage receipt. It identifies exactly which missing route legs need
source evidence to reach the frozen 70% threshold. It also multiplies the
dated 9 October 2026 research close by the dated SEC-reported share count
with 50-digit Decimal arithmetic. Each candidate is bound to the share row's
evidence hash, share period, recorded availability, price time and report
seal. INOD's previously reported research market cap cross-checks to within
one cent. These are **current Research market-cap candidates**, not historical
PIT market caps and not route SupportedMC destinations. The source share
status says `RESEARCH_ONLY_ACCEPTED_AT_UNVERIFIED`; no provider-first-
availability claim follows from it.

| Issuer | Selected route | Essential legs present | Missing | More legs needed for ≥70% | Dated current MC candidate, USD |
|---|---|---|---|---:|---:|
| INOD | R10 | U, V | C, G, M | 2 | 2,133,099,699.52 |
| TMDX | R10 | U, V | C, G, M | 2 | 2,700,153,636.39 |
| CRMD | R10 | U, V | C, G, M | 2 | 575,229,120.04 |
| PENG | F10 | V | A, C, M, U | 3 | 3,908,793,017.17 |
| ETON | R10 | U, V | C, G, M | 2 | 1,578,074,857.18 |

Values displayed above are rounded; the sealed packet holds full Decimal
products. The date is the source close, **not a live quote**. The individual
shares come from company filings with different 2026 share dates, so these
products are research estimates and not exchange-certified capitalizations.

## Acceptance gate by version

| Version | Original mandatory gate | Real five-issuer result | Status |
|---|---|---|---|
| V1.2 | S15.2; M10 ≥5/7; T10 ≥5/7; essential route coverage ≥70%; original route gate; confidence and source fit | All five lack S15.2, M10, T10, confidence and route gate. Coverage is 40% for four R10 issuers and 20% for PENG F10. | No READY score |
| V1.4 | V1.2 upstream, actual growth/magnitude, route-specific SupportedMC, dual magnitude, 13 original V1.4 normalized scenario/confidence inputs, model fit and dated sources | All five lack all 13 scenario inputs and upstream READY. Current market cap candidates cannot supply SupportedMC or a tenfold destination. | No score |
| V1.4.1 | V1.2 READY, own source-backed route-confidence, assumption burden and scenario construction | All five fail the V1.2 prerequisite. Frozen implementation stops before generating scenario values. | No score |

The receipt preserves each model engine's exact missing list. A 40% route
coverage or partial `DNA60` is not rounded up. No future SupportedMC,
historical cohort, model fit, neutral V1.4 scenario, or zero-valued missing
leg was fabricated. The V12 audit's SEC research legs remain useful dated
inputs, but their `accepted_at` timing is unverified and does not establish
historical PIT availability.

**Task 12 remains PARTIAL: 0/3 versions accepted; 0 new full S15.3 scores.**
The closest code-addressable work is to source C/G/M for a real R10 issuer
(at least two of three for route coverage, plus any route-gate requirements),
S15.2, seven magnitude and timing leg families, route-specific destination
values, and calibrated confidence/fit. The data are not present in the sealed
five-issuer report. V1.4 and V1.4.1 must then be tested independently after
V1.2 READY; simply deriving current market cap cannot make either version
ready.

Run `E:/M10/.venv/Scripts/python.exe scripts/scoring_v13_s15_audit.py --verify`
from the V13 worktree to check original report and output SHA seals, source
timing, route coverage and unchanged receipt bytes. The focused tests also
exercise a tampered report, tampered route coverage and a future share
availability date. No live database or installed application was written.
