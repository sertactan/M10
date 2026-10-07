# WF8-E — Windows / Runtime Final Release Gate

Status: IMPLEMENTED — completion requires Python CI + Windows Production Build
on the exact merged commit.

Gate version: `WF8E_RELEASE_GATE_V1_2026-10-07`.

## Packaged runtime requirements

The packaged application doctor now requires:

- hardened WF7 calibration provider module
- WF8-A hardening module
- WF8-C reproducibility module
- WF8-D activation/rollback module
- SQLite runtime tables for WF5/WF6/WF7/WF8

A clean installation does **not** require a fabricated active calibration.
Absence of real validated market-prevalence evidence remains fail-closed at the
calibration/activation layer.

## Windows build sequence

The production workflow must successfully execute, in order:

1. build bundled security seeds
2. PyInstaller application build
3. packaged V1.4.1 specification/schema checks
4. clean-install offline `--doctor`
5. corrupt-database recovery smoke
6. upgrade migration smoke
7. Inno Setup installer build
8. installer SHA-256
9. WF8-E final release gate
10. artifact upload

The final gate produces:

```text
WF8E_RELEASE_EVIDENCE.json
```

The evidence binds:

- exact GitHub commit
- source release-readiness contract
- WF8 source schema contract
- explicit PyInstaller WF8 hiddenimports
- Windows smoke/recovery/migration workflow contract
- packaged WF8 schema
- installer existence
- installer SHA-256 verification
- deterministic evidence SHA-256

Any failed required check returns `RELEASE_BLOCKED` and the Windows workflow
fails before artifact publication.
