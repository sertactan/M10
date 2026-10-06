# Phase 12 — Production Build

## Status

**BUILD COMPLETE; final production release remains dependency-blocked.**

Master-prompt scope:

- Windows executable
- installer
- logging
- error handling
- settings
- update system

## Implemented

- PyInstaller Windows one-folder build specification
- Inno Setup installer definition
- Windows GitHub Actions build workflow
- installer SHA-256 output
- rotating production logs
- global exception hook with user-safe notification
- atomic persistent runtime settings
- update manifest parsing/fetch/version comparison
- writable LOCALAPPDATA runtime data root for frozen builds
- runtime path override for testing/deployment
- Phase 12 acceptance matrix

Production release remains dependency-aware: canonical V1.4 and downstream production evidence must be complete before a final release can be declared.
