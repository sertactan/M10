# WF6 — Expanding Walk-Forward Engine

Status: STARTED.

Leakage policy: `WF6_LEAKAGE_POLICY_V1_2026-10-07`.

WF6 validates the frozen S15.3 V1.4.1 model. It does **not** tune weights,
thresholds or formulas.

Default folds:

```text
2013-2017 reference -> 2018 OOS
2013-2018 reference -> 2019 OOS
2013-2019 reference -> 2020 OOS
2013-2020 reference -> 2021 OOS
2013-2021 reference -> 2022 OOS
2013-2022 reference -> 2023 OOS
2013-2023 reference -> 2024 OOS
```

Only WF5 PIT replay observations enter the test panel. READY outcomes are
evaluation rows; censored/partial observations remain censored and are not
converted to failures.

Same-security overlap is explicitly counted per fold. Historical similarity
hardening excludes the target security from its own historical control cohort.
