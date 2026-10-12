# V14 Task 11 — original S1/S2/S3 acceptance gate

12 October 2026 (JST). This continuation preserves the first private V14 gate
receipt (`gate_receipt.json`, SHA-256
`1d310b9946bc906a1320f6bd4fae4ca84e5150dde94b0832788c3e8cdc8aac1b`).
The more complete `gate_receipt_v2.json` joins it to the previously sealed
V13 original SEC evidence. Its SHA-256 is
`00843e643c21f8cc6c912e736a5721a0f8a1ff3bb9c41911da989b94419d98fb`.
Both remain under `E:/M10/.master_tasks_v14_private/core`; no raw SEC source is
committed.

The original S1–S14 source at the installed Meridyen plugin was byte checked
against SHA-256
`53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794`.
It enumerates exactly 48 discovery and 12 control factors, with separate
Core48, Control12, DNA60, route/Gate6, historical H, and N61/FPR stages.
The five-stock V12 research report SHA-256 is
`1ff05025cf0ce7e7a76b397a5b3782203a8a21b1b7aa6c010291c7de744e2fc9`.
The V13 F52/F53 raw receipt SHA-256 is
`ebe9164854707c4b3ccbb482d9aa437090b866b723b797ec39298f37c0fd5b2a`.
The V13 INOD SEC binding receipt SHA-256 is
`cfd31efecf0e59d1e52a85baecc8006f2614c9dd485d063a77bdb5f0488f7e76`.
Both V13 receipts are independently checked against their `.sha256` sidecars
before a V14 receipt can be built.

| Stock | Discovery inputs / 48 | Control inputs / 12 | Historical H | Complete S1/S2/S3 |
|---|---:|---:|---|---|
| INOD | 5 | 2 | missing | N/A / N/A / N/A |
| TMDX | 5 | 2 | missing | N/A / N/A / N/A |
| CRMD | 2 | 2 | missing | N/A / N/A / N/A |
| PENG | 0 | 1 | missing | N/A / N/A / N/A |
| ETON | 3 | 2 | missing | N/A / N/A / N/A |

The 9 INOD SEC fact rows from 4 original accessions are bound to four
partial D01/D02/D03/F54 legs. These are source backed current Research legs;
the V13 receipt explicitly says public dissemination/PIT acceptance is not
verified. The FY2025 10-K supports exact one-year F52 revenue-per-share and
F53 FCF-per-share **raw growth**. The frozen source gives their formulas and a
general peer/benchmark scoring approach, but no factor-specific numerical
0–100 mapping or qualified peer cohort was present in this evidence set. Their
quality scores remain N/A, so Control12 does not gain two accepted inputs.

The Phase24G offline backup was opened read only (`mode=ro`, `query_only=ON`).
Its `s153_historical_control_observations` table has **0 rows**, while
`canonical_model_features` has 46 rows and no canonical `D01`–`D48` or
`F49`–`F60` factor key. This is a statement about those tables in that backup,
not all possible Meridyen storage. Historical H cannot be built from a
present-day stock snapshot. Without complete qualified Core48/Control12 and
historical winner/control snapshots, the partial DNA, router and Gate6 math
cannot become a complete model score. N61/FPR inputs also remain missing.

**Acceptance decision:** Task 11 remains PARTIAL. The separate full S1, S2,
and S3 gates remain OPEN; new complete Research scores: **0**. No frozen model
formula or live operational database was modified. Three isolated unit tests
pass, including a mismatched SEC binding rejection. The V2 private receipt
was independently rebuilt byte for byte with `--verify`.
