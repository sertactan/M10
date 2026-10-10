# Recovered S1–S14 quality contracts

## Source recovery and scope

The M10 Git history contains the S14 **aggregator**, but the original lower-level
quality definitions were preserved in the owner's installed Meridyen plugin.
The local search covered 204 Git refs, 1,492 commits, 6,079 objects and 1,301 text
blob versions. It found one unchanged `core/scoring/s1_s14.py` blob
`f573a616d7389e0755fcd5857b2ef9318edc0944`, introduced at `5d84e36` and integrated
at `6c14e87`. Test values of 90 are synthetic, not recovered financial evidence.

Recovered source: plugin `meridyen-equity-research` 0.28.1,
`skills/meridyen-equity-research/references/models/S1_S2_S14_CANONICAL_SOURCE.md`,
**MERİDYEN S1–S14 CANONICAL ANALYSIS SPECIFICATION v1.0**.
SHA-256: `53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794`.
The plugin's `references/SOURCE_INTEGRITY.md` independently lists this hash as
packaged in v0.2.0. No source Git commit is available for this external bundle;
the plugin version and content hash are the provenance identifiers.

Interpolation binding: the companion canonical extension
`models/s153-v12/Meridyen_S15.3_Canonical_Final_Spec_v1.0.md`, lines 68–84,
explicitly specifies linear interpolation between tabular score knots and
endpoint clipping. Its header identifies it as an extension preserving S1–S14.
SHA-256: `75d192891c0d67dccad5c5e004b07769998718effe189fe6af668ae435d3109c`.
The existing frozen `core.scoring.math.piecewise_score` implements this rule
(first source commit `3a8ba01`). No core formula is edited.

## Six-leg source matrix

| Leg | Source lines | Recovered math / inputs | Minimum evidence and remaining limitation |
|---|---|---|---|
| B_Q | 1015–1176; 1851–1866 | `clip(100*(1-CR/13))`; CR sums DSRI/GMI/AQI/DEPI/SGAI/LVGI/TATA risk weights 2/1.5/2/1/1/1.5/3 plus interaction | Two matched FYs of receivables, sales, COGS, current assets, PPE, total assets, depreciation, SGA, debt, NI and CFO; interaction flags evidenced. No raw accrual shortcut. |
| S6 | 1180–1277 | Dechow logistic L coefficients -7.893/.790/2.518/1.191/1.979/.171/-.932/1.029 for intercept, RSST, delta REC, delta INV, SOFT, delta CashSales, delta ROA, ISSUE; logistic/0.0037; reverse peer percentile or published bins | Three-period cash sales/ROA history, issuance, RSST decomposition and eligible peer or unambiguous bin. Exact WC/NCO/FIN mapping, shared interval endpoints and extreme fallback cutoff are not fully fixed by source. |
| S7 | 1281–1321 | `(NI-CFO)/((Assets_t+Assets_previous)/2)`; reverse peer percentile, or fallback knots 0→100, .05→75, .10→50, .15→25, .20→0 | NI/CFO same annual window and positive assets at FY end and day before FY start. Implemented full independent fallback. Negative accrual does not waive S13 review. |
| S11 | 1550–1623 | Jones industry-year regression followed by receivable-adjusted NDA; DA=scaled accrual−NDA; reverse peer percentile of abs(DA), fallback `100*max(0,1-abs(DA)/.20)` | Actual regression coefficients and target financial inputs; about20 peers preferred. Fallback does not eliminate the need to calculate DA. |
| S12 | 1627–1703 | CCR=CFO/NI; FCF=CFO−Capex; FCFCR=FCF/NI; OCFM=CFO/revenue; FCFM=FCF/revenue; weights .35/.30/.20/.15 | Four matched annual monetary inputs. Full acceptance requires positive NI and revenue plus all four quality legs. Nonpositive NI produces only explicitly partial diagnostic. |
| S13 | 1707–1833 | Risks AUD/RPT/REC/DIL/REV/ACQ/GOV; weights .25/.15/.20/.15/.10/.10/.05; independent serious flag counts 3/4/5 add5/10/15; S13=100−clip(risk) | Reviewed filing evidence for every qualitative block. Rubric0/25/50/75/100 is recovered; qualitative judgments and flag independence cannot be fabricated from absent data. |

S12 exact fallback knots:

- CCR: 0→0, .5→40, .8→70, 1→90, 1.2→100.
- FCFCR: 0→0, .4→35, .7→65, 1→90, 1.2→100.
- OCFM: 0→0, .05→40, .10→60, .20→85, .30→100.
- FCFM: 0→0, .05→45, .10→65, .15→80, .25→100.

Global source rules: missing is N/A, never an assumed zero; weighted averages
exclude missing legs. The implementation exposes nonpositive-NI S12 as partial
with `score=null` even though a two-margin diagnostic can be computed. This
prevents partial model output being counted as a full formula score. No peer
cohort is invented; outputs identify the explicit absolute fallback. The source
suggests a confidence blend but does not calibrate source-quality/model-fit
values; no arbitrary confidence number is generated.

## Implementation boundary

`app/recovered_quality.py` is pure: no database writes, HTTP, production model
changes or provider setup. `compute_quality(facts, at)` returns the six leg
records. S7/S12 retain exact input values, financial periods, SEC references,
accessions, accepted/available timestamps and source evidence hashes, plus
model-source hashes and line references. An evidence SHA covers the calculation.
Currency, future timestamps, bad hashes, conflicting same-time facts, mixed
issuer batches and mismatched fiscal windows fail closed. Latest incomplete
annual periods are not silently replaced by older complete periods. Capex is a
cash expenditure magnitude, consistent with the existing Phase28 convention.

All numerical outputs remain `RESEARCH_ONLY_NOT_CANONICAL_PIT`, with
`canonical_accepted=false`. An archive `available_at` cannot establish actual
first public dissemination. Complete S7/S12 formula execution is independent
of S14, S1–S3 discovery, 10X feasibility and canonical historical acceptance.
B_Q/S6/S11/S13 remain missing until their own evidence is supplied; S14 still
requires all six normalized legs in the unchanged frozen aggregator.

Recovered source definitions resolve the prior blanket SPEC_MISSING claim.
They do **not** prove every qualitative choice/edge case or supply missing raw
data. Task9 source recovery has real progress, while complete deterministic
six-leg application and Task10 S14 acceptance must stay open where unsupported.

## Independent reference examples and testing

All unit-test numbers are **synthetic fixtures**, never real stock evidence.
For NI10, CFO12, capex2, revenue100 and beginning/ending assets100: Sloan=-.02
and S7=100. S12 has Q_CCR100, Q_FCFCR90, Q_OCFM65 and Q_FCFM65, giving84.75.
Positive Sloan .075 gives62.5 under the recovered interpolation contract.
Actual issuer outputs must be reported separately by the private research run.
