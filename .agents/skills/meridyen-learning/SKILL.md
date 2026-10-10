---
name: meridyen-learning
description: Reproducible M10 walk-forward backtests and Learning V3 challenger audits.
---
# A6 — Learning & Performance Auditor
Use actual M10 WF5/WF6/WF9 and Learning V3 code. Require full point-in-time
membership, delisted securities, split/dividend/terminal consideration,
source available_at, embargo dates and mature 252-session labels.
Do not treat simulated labels or code test passing as verified predictive
performance. Report precision@K, recall@K, drawdown and test costs only
when supported by complete cohorts. No automatic formula update or
champion/challenger promotion; publish review proposals only.

## Phase25Q/R/M/S acceptance gate

An existing verified Phase25Q stage contains 21 retrospective source
months, 128,088 membership rows and 2,110,622 vendor price rows.
Phase25R found 464 historical identity conflicts; Phase25M/S
explain some issuer corporate actions but not approved adjusted-price
or delisted terminal value. The canonical 133-candidate gate remains
zero accepted. Report these as research evidence only.
Do not run/claim WF9 or Learning V3 trained outcomes until independent
historical identity, corporate-action and `available_at` gates pass.

Phase25L reports four dated official events across B and FUN.
These improve issuer-action research yet leave all 464
source conflicts quarantined and 0 approved historical
SimFinId/CIK full-window matches; do not report WF9 or
Learning V3 improvement based on these event references.

Phase25P adds three SEC index acceptance stamps; actual public
dissemination and feature ingestion times are not independently
certified. Those 3 records remain unusable for historical
model selection, regardless of period-end or initial EDGAR
acceptance. Apply `core.research.sec_publication_gate` and
never assign `available_at=Accepted` by default.
