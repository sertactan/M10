# WF8-D — Corruption/Tamper + Rollback-Safe Activation

Status: COMPLETE pending CI/merge.

Policy: `WF8D_ACTIVATION_POLICY_V1_2026-10-07`.

## Activation rule

A production candidate is verified **before** any active pointer changes.

Required chain:

```text
WF8 hardening = PRODUCTION_EVIDENCE_READY
WF8-C manifest = VERIFIED
model_version = S15.3_V1.4.1
```

Only then is the candidate promoted to `ACTIVE`. The previous active activation
becomes `STANDBY` and remains the Last-Known-Good rollback target.

## Runtime verification

Production resolution re-verifies the active manifest. If it fails:

1. Active activation is treated as corrupt/tampered.
2. Standby activations are checked newest-first.
3. The first still-verified standby becomes ACTIVE.
4. The failed activation becomes QUARANTINED.
5. An AUTO_ROLLBACK event is persisted.

If no verified standby exists, production fails closed with no active
calibration rather than continuing on corrupt evidence.

## CLI

Activate:

```powershell
python scripts/wf8_activation.py activate --manifest-id <MANIFEST_ID>
```

Runtime resolve / verification:

```powershell
python scripts/wf8_activation.py resolve
```

The schema enforces at most one ACTIVE activation per model version.
