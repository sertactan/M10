# V13 Task 11 — source-bound S1/S2/S3 progress

11 October 2026 (JST). The frozen S1–S3 implementation and the prior V12
five-issuer gate matrix remain unchanged. This step adds a read-only source
join for the **existing** normalized discovery/control research legs. It
checks the report's SHA-256 pinned SEC submissions against the original local
submissions bytes, issuer CIK, original accession, form, SEC `accepted_at`,
research availability, fact hashes, normalized range and as-of timing. It
does not invent missing factor values or replace accepted-at with public
dissemination evidence.

## Real receipt

The existing private V12 report SHA-256 is
`1ff05025cf0ce7e7a76b397a5b3782203a8a21b1b7aa6c010291c7de744e2fc9`.
The original INOD `CIK0000903651.json` submissions SHA-256 is
`070461656ae36691ad952bd53e529dd48fbb74b8f7191637d3c6bb79e27910f3`.
Four partial INOD legs (`D01`, `D02`, `D03`, `F54`) were bound to **nine**
underlying SEC evidence rows covering four original filing accessions. Every
row has an original SEC acceptance time no later than its existing research
availability and as-of time. The exact accession/time/period/fact-hash receipt
is private at `E:/M10/.master_tasks_v13_private/core/inod_sec_binding.json`,
sealed by adjacent `.sha256` file. No original SEC file or report was edited.

| Task 11 condition | Result |
|---|---|
| Frozen S1/S2/S3 versions and formulas | Preserved from V12; no model-code changes. |
| INOD partial SEC source identity and acceptance chronology | **4 legs / 9 evidence rows bound** to pinned original submissions. |
| Complete 48 discovery factors | **Open**: INOD has 5 research factors in the V12 report. |
| Complete 12 failure controls | **Open**: INOD has 2 research controls. |
| Historical winner/control H and valid cohorts | **Open**. |
| Complete router/Gate6 and N61/FPR operands | **Open**. |
| Historical public dissemination and provider availability | **Open**: SEC acceptance is verified, publication and provider timing are not. |
| Independent complete-score reference | **Open** because mandatory inputs remain absent. |

**Task 11 remains PARTIAL; S1/S2/S3 complete scores added: 0.** The existing
real partial legs retain `RESEARCH_ONLY_ACCEPTED_AT_UNVERIFIED` classification;
this source join documents original acceptance times without modifying that
classification or asserting a canonical PIT score. Other issuers lack a pinned
original submissions receipt in this source set, so the join is limited to
INOD. No complete real issuer/model combination can be accepted from these
available inputs.

Reproduce with `python scripts/scoring_v13_core_sec_binding.py --report
<v2_audit2/report.json> --submissions <CIK0000903651.json> --ticker INOD
--out <private/inod_sec_binding.json>`. Four unit tests pass via
`python -m unittest discover -s tests -p test_scoring_v13_core_sec_binding.py
-q`: original timing join, source-hash tamper, premature availability and CIK
mismatch.
