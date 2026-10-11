# V12 Tasks 11–12: frozen core acceptance audit

11 October 2026 (JST). This audit reads the existing five-issuer real-source
`v2_audit2/report.json` receipt offline. Input SHA-256 and the report's
phase27/phase28 source SHA-256 mappings are preserved in the private output
`E:/M10/.master_tasks_v12_private/core/audit.json`. No database, canonical
factor, formula, market price, or accepted Research score was changed.
The saved audit bytes have SHA-256
`b7e95045ae84717bcfa5437096838243c2ae6034dce89872447860a3c647cfac`,
recorded in `audit.json.sha256`. The original audit bytes were preserved when
the sidecar was added.

## Frozen contract and implementation references

| Model | Original contract / version binding | Required acceptance chain |
|---|---|---|
| S1 | `S1_S2_S14_CANONICAL_SOURCE.md`, pinned SHA-256 `53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794`; `core/scoring/s1_s14.py` | 48 discovery factors, 12 controls, DNA60, complete router, historical winner/control similarity H, N61 risk, source timing, independent reference. |
| S2 | Same frozen source and implementation | 48 + 12 factors, DNA60, Gate6, H, false-positive risk, timing and independent reference. |
| S3 | Same frozen source and implementation | 48 + 12 factors, DNA60, router, H, timing and independent reference. |
| S15.3 V1.2 | `MERIDYEN_S15.3_CANONICAL_FINAL_v1.0`; `docs/S153_V12_FEATURE_CONTRACT.md`; `core/models/s153_v12.py` | S15.2; M10 at least 5/7; T10 at least 5/7; selected essential-route coverage at least 70%; route gate; confidence/source fit; PIT feature provenance. |
| S15.3 V1.4 | `specs/s153_v14/manifest.json` binds five SHA-256 specification artifacts; `S15.3_V1.4_RECOVERED_2026-10-05` | V1.2 upstream; 13 V1.4 scenario, destination and confidence inputs; dual magnitude; model fit; dated sources. |
| S15.3 V1.4.1 | `S15.3_V1.4.1_CANONICAL_COMPLETION_2026-10-07`; `specs/s153_v141/canonical_completion_specification.md` | V1.2 READY first, own route-confidence/assumption/scenario evidence, dated input provenance. |

The source SHA is checked against the report's stored contract SHA. The original
S1–S14 source file itself is not in this checkout, so this is **receipt
verification**, not a fresh byte comparison against that original file. All
five V1.4 specification artifacts are independently hashed against the local
manifest, and model version names are checked. Report rows do not contain a full set of
source references, so that gate remains false for every model.

## Actual five-issuer gate result

| Issuer | Real discovery factors / 48 | Controls / 12 | Historical H | S15.2 | M10 / T10 | V1.2 route and confidence | V1.4 scenario inputs | V1.4.1 |
|---|---:|---:|---|---|---|---|---|---|
| INOD | 5 | 2 | absent | absent | absent / absent | route 40%; confidence absent | absent | V1.2 not READY |
| TMDX | 5 | 2 | absent | absent | absent / absent | incomplete | absent | V1.2 not READY |
| CRMD | 2 | 2 | absent | absent | absent / absent | incomplete | absent | V1.2 not READY |
| PENG | 0 | 1 | absent | absent | absent / absent | incomplete | absent | V1.2 not READY |
| ETON | 3 | 2 | absent | absent | absent / absent | incomplete | absent | V1.2 not READY |

The source report contains partial fiscal growth, margin, cash and router
normalizations for some issuers. These are real research legs, not the 48/12
complete factor contracts. In particular, the report's `core48_partial`,
`dna60_partial`, `router_partial`, and `gate6_partial` values use the frozen
missing-data renormalization and must not be promoted to complete S1–S3 scores.
The historical winner/control cohort is absent; forward outcomes cannot be
inserted as current features. No issuer has a complete route-specific
SupportedMC scenario, historical H, M10, or T10 in this receipt. The audit
does not generate model scores when these inputs are absent.

The available SEC-derived normalized research legs were independently checked
for `available_at <= as_of`, 0–100 range, source reference and evidence hash:
INOD 4/4, TMDX 4/4, CRMD 2/2, PENG 1/1, ETON 3/3. Their recorded quality
status is `RESEARCH_ONLY_ACCEPTED_AT_UNVERIFIED`; the dates are therefore
useful for research provenance but do not prove SEC publication-time PIT
acceptance. The private audit retains each leg's individual checks.

**Task 11: PARTIAL, 0 newly accepted S1/S2/S3. Task 12: PARTIAL, 0 newly
accepted V1.2/V1.4/V1.4.1. Neither task is DONE.** All six versioned model
receipts per issuer were checked; all 30 remain below acceptance. No eligible
complete real issuer/model combination was found in this source set. The next
data engineering requirement is source-bound, dated normalized factor rows
for the missing discovery/control families, historical winner/control cohorts,
route-specific destinations and confidence/fit; the report aggregate cannot
establish them.

Run: `python scripts/scoring_v12_core_audit.py --report <private report.json>
--out <private audit.json> --verify` to recompute and compare the exact saved
bytes and sidecar without writing either file. Use `--seal-existing` once to
seal an already identical output without rewriting the audit JSON. Omitting
both flags writes and seals a new output. The private output lists every gate
and missing engine requirement for each issuer/model. Six standard-library unit tests
pass (`python -m unittest discover -s tests -p test_scoring_v12_core_audit.py
-v`): fail-closed partial receipts, source-hash mismatch, version mismatch,
an independent S1–S3 arithmetic reference, a future availability rejection,
and read-only exact-byte/sidecar verification. The five-issuer real-report
invocation also passed. Tests of audit logic do not establish model acceptance.
