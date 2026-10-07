# WF8-C — Reproducibility / Hash Manifest

Status: COMPLETE pending CI/merge.

Manifest version: `WF8C_REPRO_MANIFEST_V1_2026-10-07`.

The manifest hashes the persisted evidence chain, not merely a config file.

Component hashes:

```text
WF5 hash = replay run + checkpoints + persisted score/outcome states
WF6 hash = walk-forward run + folds + OOS panel
WF7 hash = validation summary + threshold metrics + calibration buckets + route metrics
WF8 hash = hardening run + acceptance checks
```

The final chain hash also binds:

- manifest version
- explicit code identity / build commit
- hardening id
- WF5/WF6/WF7 run ids
- all four component SHA-256 values

## Create

```powershell
python scripts/wf8_reproducibility.py create ^
  --hardening-id <HARDENING_ID> ^
  --code-identity <GIT_COMMIT_OR_BUILD_ID>
```

## Verify

```powershell
python scripts/wf8_reproducibility.py verify --manifest-id <MANIFEST_ID>
```

Any change to persisted WF5/WF6/WF7/WF8 evidence after manifest creation changes
the corresponding component hash and causes verification to raise a
reproducibility error. The stored manifest status is then marked `TAMPERED`.

Timestamps used only as write metadata are intentionally excluded from the
evidence payload where they do not alter analytical meaning.
