from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Iterable

from data.database.sqlite_store import SQLiteStore


V141_UPSTREAM_REQUIRED_KEYS = (
    "DATA_COVERAGE",
    "SOURCE_QUALITY",
    "MODEL_FIT",
    "PIT_INTEGRITY",
    "PIR_VAL",
    "PLAUSIBLE_CEILING_MC",
)

SUPPORTED_MC_KEYS = (
    "SUPPORTED_MC_12_FI",
    "SUPPORTED_MC_12_D",
    "SUPPORTED_MC_12_B",
    "SUPPORTED_MC_12_R",
)


@dataclass(frozen=True)
class WalkForwardDateReadiness:
    as_of_date: date
    universe_members: int
    price_covered: int
    fundamental_covered: int
    feature_covered: int
    v141_upstream_ready: int
    exact_pit_universe: bool
    blockers: tuple[str, ...]

    @property
    def price_coverage_pct(self) -> float:
        return 0.0 if self.universe_members <= 0 else 100.0 * self.price_covered / self.universe_members

    @property
    def fundamental_coverage_pct(self) -> float:
        return 0.0 if self.universe_members <= 0 else 100.0 * self.fundamental_covered / self.universe_members

    @property
    def feature_coverage_pct(self) -> float:
        return 0.0 if self.universe_members <= 0 else 100.0 * self.feature_covered / self.universe_members

    @property
    def v141_upstream_ready_pct(self) -> float:
        return 0.0 if self.universe_members <= 0 else 100.0 * self.v141_upstream_ready / self.universe_members


class WalkForwardReadinessAuditor:
    """Evidence-only readiness audit for whole-market walk-forward work.

    This class does not manufacture historical membership, prices, fundamentals
    or model features. It reports what is actually present in canonical storage.
    """

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def available_snapshot_dates(self) -> list[date]:
        rows = self.store.connection.execute(
            """
            SELECT DISTINCT snapshot_date
            FROM universe_snapshot_membership
            ORDER BY snapshot_date
            """
        ).fetchall()
        return [date.fromisoformat(str(row["snapshot_date"])) for row in rows]

    def audit(self, as_of_date: date) -> WalkForwardDateReadiness:
        as_of = datetime.combine(as_of_date, time.max, tzinfo=timezone.utc).isoformat()
        d = as_of_date.isoformat()

        members = self.store.connection.execute(
            """
            SELECT COUNT(DISTINCT security_id) AS n
            FROM universe_snapshot_membership
            WHERE snapshot_date=?
              AND exchange IN ('NASDAQ','NYSE','AMEX')
            """,
            (d,),
        ).fetchone()
        universe_members = int(members["n"] or 0)

        sources = self.store.connection.execute(
            """
            SELECT DISTINCT source
            FROM universe_snapshot_membership
            WHERE snapshot_date=?
              AND exchange IN ('NASDAQ','NYSE','AMEX')
            """,
            (d,),
        ).fetchall()
        source_names = {str(row["source"]).upper() for row in sources}
        # Exact PIT means the snapshot came from an evidence-bearing historical
        # source, not a current-universe substitution. STOCK_DATA_PIT is valid
        # only for dates its provider itself allows; the provider enforces that
        # floor before rows reach this table.
        exact_pit = bool(source_names) and all(
            name in {"STOCK_DATA_PIT", "ALPHAVANTAGE_PIT", "MASSIVE", "IMPORTED_PIT_CANONICAL"}
            for name in source_names
        )

        price = self.store.connection.execute(
            """
            SELECT COUNT(DISTINCT u.security_id) AS n
            FROM universe_snapshot_membership u
            JOIN canonical_price_selection p ON p.security_id=u.security_id
            WHERE u.snapshot_date=?
              AND u.exchange IN ('NASDAQ','NYSE','AMEX')
              AND p.start_date<=?
              AND p.end_date>=?
              AND p.purpose IN ('BACKTEST','BACKTEST_ADJUSTED')
            """,
            (d, d, d),
        ).fetchone()
        price_covered = int(price["n"] or 0)

        fundamentals = self.store.connection.execute(
            """
            SELECT COUNT(DISTINCT u.security_id) AS n
            FROM universe_snapshot_membership u
            WHERE u.snapshot_date=?
              AND u.exchange IN ('NASDAQ','NYSE','AMEX')
              AND EXISTS (
                  SELECT 1
                  FROM fundamental_facts_source f
                  WHERE f.security_id=u.security_id
                    AND f.available_at<=?
              )
            """,
            (d, as_of),
        ).fetchone()
        fundamental_covered = int(fundamentals["n"] or 0)

        features = self.store.connection.execute(
            """
            SELECT COUNT(DISTINCT u.security_id) AS n
            FROM universe_snapshot_membership u
            WHERE u.snapshot_date=?
              AND u.exchange IN ('NASDAQ','NYSE','AMEX')
              AND EXISTS (
                  SELECT 1
                  FROM canonical_model_features f
                  WHERE f.security_id=u.security_id
                    AND f.feature_as_of<=?
                    AND f.available_at<=?
              )
            """,
            (d, as_of, as_of),
        ).fetchone()
        feature_covered = int(features["n"] or 0)

        all_required = (*V141_UPSTREAM_REQUIRED_KEYS,)
        placeholders = ",".join("?" for _ in all_required)
        v141 = self.store.connection.execute(
            f"""
            WITH latest AS (
                SELECT f.security_id,f.feature_key,f.value,
                       ROW_NUMBER() OVER (
                           PARTITION BY f.security_id,f.feature_key
                           ORDER BY f.feature_as_of DESC,f.available_at DESC,f.created_at DESC
                       ) AS rn
                FROM canonical_model_features f
                JOIN universe_snapshot_membership u ON u.security_id=f.security_id
                WHERE u.snapshot_date=?
                  AND u.exchange IN ('NASDAQ','NYSE','AMEX')
                  AND f.feature_key IN ({placeholders})
                  AND f.feature_as_of<=?
                  AND f.available_at<=?
            ),
            base_ready AS (
                SELECT security_id
                FROM latest
                WHERE rn=1 AND value IS NOT NULL
                GROUP BY security_id
                HAVING COUNT(DISTINCT feature_key)=?
            ),
            destination_ready AS (
                SELECT DISTINCT f.security_id
                FROM canonical_model_features f
                JOIN universe_snapshot_membership u ON u.security_id=f.security_id
                WHERE u.snapshot_date=?
                  AND u.exchange IN ('NASDAQ','NYSE','AMEX')
                  AND f.feature_key IN (?,?,?,?)
                  AND f.value IS NOT NULL
                  AND f.feature_as_of<=?
                  AND f.available_at<=?
            )
            SELECT COUNT(DISTINCT b.security_id) AS n
            FROM base_ready b
            JOIN destination_ready d ON d.security_id=b.security_id
            """,
            (
                d,
                *all_required,
                as_of,
                as_of,
                len(all_required),
                d,
                *SUPPORTED_MC_KEYS,
                as_of,
                as_of,
            ),
        ).fetchone()
        v141_ready = int(v141["n"] or 0)

        blockers: list[str] = []
        if universe_members == 0:
            blockers.append("NO_PIT_UNIVERSE_SNAPSHOT")
        if universe_members and not exact_pit:
            blockers.append("UNIVERSE_NOT_EXACT_PIT")
        if universe_members and price_covered < universe_members:
            blockers.append("PARTIAL_PRICE_COVERAGE")
        if universe_members and fundamental_covered < universe_members:
            blockers.append("PARTIAL_FUNDAMENTAL_COVERAGE")
        if universe_members and feature_covered < universe_members:
            blockers.append("PARTIAL_FEATURE_COVERAGE")
        if universe_members and v141_ready < universe_members:
            blockers.append("PARTIAL_V141_UPSTREAM_COVERAGE")

        return WalkForwardDateReadiness(
            as_of_date=as_of_date,
            universe_members=universe_members,
            price_covered=price_covered,
            fundamental_covered=fundamental_covered,
            feature_covered=feature_covered,
            v141_upstream_ready=v141_ready,
            exact_pit_universe=exact_pit,
            blockers=tuple(blockers),
        )

    def audit_many(self, dates: Iterable[date]) -> list[WalkForwardDateReadiness]:
        return [self.audit(d) for d in dates]
