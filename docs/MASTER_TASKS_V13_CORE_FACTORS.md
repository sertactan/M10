# V13 Task 11 — new original F52/F53 raw factor components

12 October 2026 (JST). The frozen S1–S14 source SHA-256
`53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794`
was checked directly against the original plugin file. Sections 4.4 and 4.5
define revenue per diluted share, FCF per diluted share and their k-year
growth. This step computes the **one-year raw growth** for INOD from exact
FY2025/FY2024 comparative rows in the original FY2025 10-K accession
`0001104659-26-020655`. The pinned SEC Companyfacts SHA-256 is
`6ccc9dcc93b9c303cee51c166f345350fb16258408c884e2ed5d1231f2741b38`;
the pinned original submissions SHA-256 is
`070461656ae36691ad952bd53e529dd48fbb74b8f7191637d3c6bb79e27910f3`.
The original SEC acceptance time is `2026-02-26T22:22:13Z`. Both comparative
periods are part of that filing, so this receipt is current Research evidence
as of October 2026, not an as-of-2024 PIT claim.

| Exact source, USD unless stated | FY2024 | FY2025 |
|---|---:|---:|
| Revenue | 170,461,000 | 251,663,000 |
| Diluted weighted-average shares | 32,177,000 | 35,025,000 |
| Operating cash flow | 34,864,000 | 46,752,000 |
| Capital expenditure | 7,741,000 | 11,104,000 |
| FCF = CFO − capex | 27,123,000 | 35,648,000 |

The source selector requires one matching USD/share fact per tag, fiscal end,
annual start, original accession and 10-K form; an independent existing
selector must agree. Two 60-digit Decimal paths also agree within 1e-50:

- **F52 raw RPS growth (1Y):** `0.35631868287006280541810411830225966440311098097458443097295` = 35.631868%.
- **F53 raw FPS growth (1Y):** `0.20743803356707170809332576793539190158729933162230284997446` = 20.743803%.

These are genuinely new original-source **raw partial factor components**.
The frozen contract does not give a specific numeric 0–100 normalization for
F52 or F53. Their quality scores therefore remain **N/A**, and neither is
added to Control12. The earlier INOD partial-factor acceptance count is not
inflated; complete Core48/Control12, historical H, router and risk gates remain
open. **Task 11 stays PARTIAL; new complete S1/S2/S3 scores: 0.**

The source rows, fact hashes, Decimal reference values and model gates are in
the sealed private receipt
`E:/M10/.master_tasks_v13_private/core_factors/inod_f52_f53_raw.json`
(SHA-256 `ebe9164854707c4b3ccbb482d9aa437090b866b723b797ec39298f37c0fd5b2a`).
Reproduce using `python scripts/scoring_v13_core_factors_sec.py --companyfacts
<pinned companyfacts.json> --submissions <pinned CIK0000903651.json> --out
<private receipt.json>`. Three unit tests pass: exact raw formula, nonpositive
FCF denominator rejection, and pinned source tamper rejection.
