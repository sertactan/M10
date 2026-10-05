from __future__ import annotations

from pathlib import Path

from data.database.duckdb_store import DuckDBStore


class DuckDBPriceCatalog:
    """Register the provider-isolated Parquet lake for analytical scans."""

    def __init__(self, duckdb: DuckDBStore, parquet_root: str | Path) -> None:
        self.duckdb = duckdb
        self.parquet_root = Path(parquet_root)

    def refresh_view(self) -> bool:
        pattern = self.parquet_root / "prices" / "source=*" / "security_id=*" / "year=*" / "bars.parquet"
        if not list((self.parquet_root / "prices").glob("source=*/security_id=*/year=*/bars.parquet")):
            return False
        conn = self.duckdb.connect()
        glob_text = str(pattern).replace("'", "''")
        conn.execute(
            f"""
            CREATE OR REPLACE VIEW price_source_daily AS
            SELECT * FROM read_parquet('{glob_text}', hive_partitioning=true, union_by_name=true)
            """
        )
        return True
