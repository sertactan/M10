from __future__ import annotations

from collections import Counter

from data.database.sqlite_store import SQLiteStore


class ValidationRepository:
    """Read-only diagnostics over persisted cross-provider validation evidence."""

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def latest_price(self, security_id: str, *, limit: int = 20) -> list[dict]:
        rows = self.store.connection.execute(
            """
            SELECT *
            FROM price_validation_results
            WHERE security_id=?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (security_id, int(limit)),
        ).fetchall()
        return [dict(row) for row in rows]

    def latest_fundamentals(self, security_id: str, *, limit: int = 100) -> list[dict]:
        rows = self.store.connection.execute(
            """
            SELECT *
            FROM fundamental_validation_results
            WHERE security_id=?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (security_id, int(limit)),
        ).fetchall()
        return [dict(row) for row in rows]

    def summary(self, security_id: str) -> dict:
        price = self.latest_price(security_id)
        fundamentals = self.latest_fundamentals(security_id)
        price_counts = Counter(str(row["status"]) for row in price)
        fundamental_counts = Counter(str(row["status"]) for row in fundamentals)

        return {
            "price": {
                "counts": dict(sorted(price_counts.items())),
                "latest": price,
                "diagnostics": [
                    row for row in price if str(row["status"]) not in {"OK"}
                ],
            },
            "fundamentals": {
                "counts": dict(sorted(fundamental_counts.items())),
                "latest": fundamentals,
                "diagnostics": [
                    row for row in fundamentals
                    if str(row["status"]) not in {"MATCH"}
                ],
            },
        }
