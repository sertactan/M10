from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from data.database.duckdb_store import DuckDBStore
from data.database.sqlite_store import SQLiteStore


@dataclass(frozen=True)
class DuckDBRefreshStats:
    forward_outcomes: int
    backtest_predictions: int
    analysis_runs: int
    backtest_results: int


class DuckDBAnalyticsMirror:
    """Mirror analytical evidence from SQLite into DuckDB.

    SQLite remains the operational source of truth. DuckDB receives a replace-only
    analytical mirror so optimization cannot mutate canonical operational data.
    """

    TABLES = (
        "forward_outcomes",
        "backtest_predictions",
        "analysis_runs",
        "backtest_results",
    )

    def __init__(self, duckdb: DuckDBStore) -> None:
        self.duckdb = duckdb

    @staticmethod
    def _read_sqlite_table(sqlite: SQLiteStore, table: str) -> pd.DataFrame:
        return pd.read_sql_query(f"SELECT * FROM {table}", sqlite.connection)

    def refresh_from_sqlite(self, sqlite: SQLiteStore) -> DuckDBRefreshStats:
        connection = self.duckdb.connect()
        counts: dict[str, int] = {}
        for table in self.TABLES:
            frame = self._read_sqlite_table(sqlite, table)
            temp_name = f"_mirror_{table}"
            connection.register(temp_name, frame)
            try:
                connection.execute(
                    f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM {temp_name}"
                )
            finally:
                connection.unregister(temp_name)
            counts[table] = len(frame)
        return DuckDBRefreshStats(
            forward_outcomes=counts["forward_outcomes"],
            backtest_predictions=counts["backtest_predictions"],
            analysis_runs=counts["analysis_runs"],
            backtest_results=counts["backtest_results"],
        )

    def paired_model_rows(self, *, model_a: str, model_b: str):
        connection = self.duckdb.connect()
        return connection.execute(
            """
            SELECT
                a.observation_id,
                a.score AS score_a,
                b.score AS score_b,
                a.precision_confirmed AS precision_a,
                b.precision_confirmed AS precision_b,
                o.fm252
            FROM backtest_predictions a
            JOIN backtest_predictions b
              ON b.observation_id=a.observation_id
            JOIN forward_outcomes o
              ON o.observation_id=a.observation_id
            WHERE a.model_version=?
              AND b.model_version=?
              AND a.status='READY'
              AND b.status='READY'
              AND o.outcome_status='READY'
            ORDER BY a.observation_id
            """,
            [model_a, model_b],
        ).fetchall()

    def route_performance_rows(self, *, model_version: str):
        connection = self.duckdb.connect()
        return connection.execute(
            """
            SELECT
                a.route,
                COUNT(*) AS n,
                AVG(a.score) AS average_score,
                AVG(b.return_12m) AS average_return_12m
            FROM analysis_runs a
            JOIN backtest_results b ON b.analysis_id=a.analysis_id
            WHERE a.model_version=?
              AND a.route IS NOT NULL
              AND a.status='READY'
              AND b.outcome_status='READY'
            GROUP BY a.route
            ORDER BY a.route
            """,
            [model_version],
        ).fetchall()
