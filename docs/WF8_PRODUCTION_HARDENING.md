# WF8 — Production Hardening

Status: IMPLEMENTED — WF8-A through WF8-E are present; activation of a new historical evidence chain remains dependent on WF9.

Policy: `WF8_PRODUCTION_HARDENING_V1_2026-10-07`.

WF8 is the release-hardening layer for the new walk-forward chain:

```text
WF5 PIT replay
  -> WF6 expanding OOS walk-forward
    -> WF7 OOS validation/calibration
      -> WF8 production evidence gate
```

## WF8-A — Production Readiness Gate

The first WF8 deliverable is fail-closed. It does not alter S15.3 formulas,
thresholds, model weights or probabilities.

Required gates:

1. WF5 replay is COMPLETE.
2. WF6 walk-forward is COMPLETE.
3. WF6 points to the exact WF5 source run.
4. WF6 leakage policy is the frozen V1 policy.
5. All WF6 folds are materialized and COMPLETE.
6. At least one READY OOS outcome exists.
7. WF7 validation is COMPLETE.
8. WF7 points to the exact WF6 run.
9. WF7 validation summary exists.
10. Threshold matrix is exactly 65/75/80/85 + Top20/Top50.
11. Calibration bucket matrix is complete.
12. Probability release remains fail-closed: S15.3 score is not silently treated
    as probability, and at least one empirical bucket has N>=30.

A missing or failed required gate produces:

```text
PRODUCTION_BLOCKED
```

Only a fully valid evidence chain produces:

```text
PRODUCTION_EVIDENCE_READY
```

## Implemented WF8 milestones

- WF8-B: validated WF7 empirical evidence is bound to production forecast/calibration adapters.
- WF8-C: reproducibility manifest and hashes protect the WF5/WF6/WF7/WF8 chain.
- WF8-D: tamper detection and rollback-safe Last-Known-Good activation are implemented.
- WF8-E: Windows/runtime release gate verifies packaged schema, clean install, corrupt-DB recovery, upgrade migration, installer hash, and release evidence.

These implementation gates do not manufacture a historical production run. A newly generated chain is eligible for production activation only after WF9 supplies real PIT universe and canonical adjusted-price evidence.
