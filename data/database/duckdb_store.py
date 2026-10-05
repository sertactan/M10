from __future__ import annotations

from pathlib import Path
from typing import Any


class DuckDBUnavailable(RuntimeError):
    pass


class DuckDBStore:
    """Analytical store boundary.

    Import is intentionally lazy so architecture/unit tests can run before the
    optional native dependency is installed. Production bootstrap must fail
    clearly if DuckDB is requested but unavailable.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._connection: Any = None

    def connect(self) -> Any:
        if self._connection is not None:
            return self._connection
        try:
            import duckdb  # type: ignore
        except ImportError as exc:
            raise DuckDBUnavailable(
                "DuckDB is not installed. Install project runtime dependencies."
            ) from exc
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = duckdb.connect(str(self.db_path))
        return self._connection

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
