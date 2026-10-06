# Phase 12 — Production Build

## Status

**FINAL VALIDATION IN PROGRESS.**

Master-prompt scope:

- Windows executable
- installer
- logging
- error handling
- settings
- update system

## Implemented

- PyInstaller Windows one-folder build specification
- canonical V1.4 spec bundle included in packaged data
- required Phase 6–11 runtime modules included in the Windows bundle
- Inno Setup installer definition
- Windows GitHub Actions production-build workflow
- packaged `--doctor` smoke test
- installer SHA-256 output
- rotating production logs
- global exception hook with user-safe notification
- atomic persistent runtime settings
- update manifest parsing/fetch/version comparison
- writable LOCALAPPDATA runtime data root for frozen builds
- runtime path override for testing/deployment
- release-readiness gate covering canonical V1.4, Phase 6–11 modules, strict PIT and no-mock production mode
- exact Phase 12 acceptance matrix

Final completion requires green Python CI and green Windows executable/installer build.
