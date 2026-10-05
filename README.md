# S15.3 Research Terminal — Phase 0

Windows desktop research platform for S15.3 V1.2 and V1.4.

## Phase 0 status

Implemented:
- clean layered package structure
- PIT-safe timestamp/data contracts
- SQLite operational schema
- DuckDB adapter boundary (lazy dependency)
- provider interfaces
- PIT repository queries
- model configuration loader and fail-closed model base
- reproducible analysis-run persistence
- unit tests for PIT leakage and storage

Not implemented yet by design:
- US universe ingestion (Phase 1)
- historical price ingestion/corporate actions (Phase 2)
- SEC fundamentals ingestion (Phase 3)
- S15.3 V1.2 canonical model (Phase 4)
- S15.3 V1.4 canonical model (Phase 5)
- backtester/scanner/UI/forecast

No mock scores or demo stock results are produced.

## Quick check

```powershell
python -m pytest
python main.py --doctor
```

`duckdb` and `PySide6` are declared as runtime dependencies but Phase 0 tests do not require them to be installed.
