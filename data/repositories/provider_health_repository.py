from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from data.database.sqlite_store import SQLiteStore


QUALITY_SCORE = {
    "SEC_EDGAR": 100.0,
    "MASSIVE": 100.0,
    "MARKETPARQUET": 95.0,
    "STOOQ": 85.0,
    "SIMFIN": 85.0,
    "FINNHUB": 80.0,
    "FMP": 80.0,
    "YAHOO_COMPAT": 65.0,
}


@dataclass(frozen=True)
class ProviderHealthSnapshot:
    provider: str
    circuit_state: str
    availability_score: float
    freshness_score: float
    data_quality_score: float
    latency_score: float
    rate_limit_score: float
    health_score: float
    consecutive_failures: int
    last_success_at: datetime | None
    opened_at: datetime | None


class ProviderHealthRepository:
    """Persistent provider-health and circuit-breaker state.

    The score is deliberately operational, not financial-model evidence:
      30% availability + 25% freshness + 20% data quality
      + 15% latency + 10% rate-limit capacity.

    Unseen providers retain neutral health (100) so the canonical static
    provider priority remains the cold-start tie breaker.
    """

    def __init__(
        self,
        store: SQLiteStore,
        *,
        failure_threshold: int = 5,
        cooldown_seconds: int = 60,
    ) -> None:
        self.store = store
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _parse_dt(value: str | None) -> datetime | None:
        if not value:
            return None
        return datetime.fromisoformat(value)

    @staticmethod
    def _latency_score(latency_ms: float | None) -> float:
        if latency_ms is None:
            return 100.0
        if latency_ms <= 250:
            return 100.0
        if latency_ms <= 500:
            return 90.0
        if latency_ms <= 1000:
            return 75.0
        if latency_ms <= 2000:
            return 55.0
        if latency_ms <= 5000:
            return 30.0
        return 10.0

    @staticmethod
    def _freshness_score(last_success_at: datetime | None, now: datetime) -> float:
        if last_success_at is None:
            return 100.0
        age = max(0.0, (now - last_success_at).total_seconds())
        if age <= 15 * 60:
            return 100.0
        if age <= 60 * 60:
            return 95.0
        if age <= 6 * 60 * 60:
            return 85.0
        if age <= 24 * 60 * 60:
            return 70.0
        if age <= 7 * 24 * 60 * 60:
            return 50.0
        return 25.0

    def _availability_score(self, provider: str) -> float:
        rows = self.store.connection.execute(
            """
            SELECT success
            FROM provider_health_events
            WHERE provider=?
            ORDER BY event_id DESC
            LIMIT 100
            """,
            (provider,),
        ).fetchall()
        if not rows:
            return 100.0
        return 100.0 * sum(int(row["success"]) for row in rows) / len(rows)

    def _recent_rate_limit_score(self, provider: str) -> float:
        rows = self.store.connection.execute(
            """
            SELECT rate_limited
            FROM provider_health_events
            WHERE provider=?
            ORDER BY event_id DESC
            LIMIT 50
            """,
            (provider,),
        ).fetchall()
        if not rows:
            return 100.0
        limited = sum(int(row["rate_limited"]) for row in rows)
        return max(0.0, 100.0 * (1.0 - limited / len(rows)))

    def _recent_latency_ms(self, provider: str) -> float | None:
        rows = self.store.connection.execute(
            """
            SELECT latency_ms
            FROM provider_health_events
            WHERE provider=? AND success=1 AND latency_ms IS NOT NULL
            ORDER BY event_id DESC
            LIMIT 20
            """,
            (provider,),
        ).fetchall()
        values = [float(row["latency_ms"]) for row in rows]
        return sum(values) / len(values) if values else None

    def _ensure_state(self, provider: str) -> None:
        now = self._now().isoformat()
        self.store.connection.execute(
            """
            INSERT INTO provider_health_state (
                provider,circuit_state,consecutive_failures,cooldown_seconds,
                availability_score,freshness_score,data_quality_score,
                latency_score,rate_limit_score,health_score,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(provider) DO NOTHING
            """,
            (
                provider,
                "CLOSED",
                0,
                self.cooldown_seconds,
                100.0,
                100.0,
                QUALITY_SCORE.get(provider, 80.0),
                100.0,
                100.0,
                100.0,
                now,
            ),
        )
        self.store.connection.commit()

    def snapshot(self, provider: str) -> ProviderHealthSnapshot:
        self._ensure_state(provider)
        now = self._now()
        row = self.store.connection.execute(
            "SELECT * FROM provider_health_state WHERE provider=?",
            (provider,),
        ).fetchone()
        assert row is not None

        state = str(row["circuit_state"])
        opened_at = self._parse_dt(row["opened_at"])
        cooldown = int(row["cooldown_seconds"])
        if state == "OPEN" and opened_at is not None and now >= opened_at + timedelta(seconds=cooldown):
            state = "HALF_OPEN"
            self.store.connection.execute(
                """
                UPDATE provider_health_state
                SET circuit_state='HALF_OPEN', updated_at=?
                WHERE provider=?
                """,
                (now.isoformat(), provider),
            )
            self.store.connection.commit()
            row = self.store.connection.execute(
                "SELECT * FROM provider_health_state WHERE provider=?",
                (provider,),
            ).fetchone()
            assert row is not None

        return ProviderHealthSnapshot(
            provider=provider,
            circuit_state=state,
            availability_score=float(row["availability_score"]),
            freshness_score=float(row["freshness_score"]),
            data_quality_score=float(row["data_quality_score"]),
            latency_score=float(row["latency_score"]),
            rate_limit_score=float(row["rate_limit_score"]),
            health_score=float(row["health_score"]),
            consecutive_failures=int(row["consecutive_failures"]),
            last_success_at=self._parse_dt(row["last_success_at"]),
            opened_at=self._parse_dt(row["opened_at"]),
        )

    def can_attempt(self, provider: str) -> bool:
        return self.snapshot(provider).circuit_state != "OPEN"

    def rank(self, providers: Iterable[str]) -> tuple[str, ...]:
        indexed = list(enumerate(providers))
        ranked = sorted(
            indexed,
            key=lambda item: (-self.snapshot(item[1]).health_score, item[0]),
        )
        return tuple(name for _, name in ranked)

    def record_success(self, provider: str, *, latency_ms: float | None = None) -> None:
        self._record(provider, success=True, latency_ms=latency_ms, rate_limited=False, message=None)

    def record_failure(
        self,
        provider: str,
        *,
        latency_ms: float | None = None,
        rate_limited: bool = False,
        message: str | None = None,
    ) -> None:
        self._record(
            provider,
            success=False,
            latency_ms=latency_ms,
            rate_limited=rate_limited,
            message=message,
        )

    def _record(
        self,
        provider: str,
        *,
        success: bool,
        latency_ms: float | None,
        rate_limited: bool,
        message: str | None,
    ) -> None:
        self._ensure_state(provider)
        now = self._now()
        previous = self.store.connection.execute(
            "SELECT * FROM provider_health_state WHERE provider=?",
            (provider,),
        ).fetchone()
        assert previous is not None

        failures = 0 if success else int(previous["consecutive_failures"]) + 1
        state = "CLOSED" if success else str(previous["circuit_state"])
        opened_at = None if success else previous["opened_at"]

        if not success and failures >= self.failure_threshold:
            state = "OPEN"
            opened_at = now.isoformat()
        elif not success and state == "HALF_OPEN":
            state = "OPEN"
            opened_at = now.isoformat()

        self.store.connection.execute(
            """
            INSERT INTO provider_health_events (
                provider,observed_at,success,latency_ms,rate_limited,message
            ) VALUES (?,?,?,?,?,?)
            """,
            (
                provider,
                now.isoformat(),
                1 if success else 0,
                latency_ms,
                1 if rate_limited else 0,
                message,
            ),
        )

        last_success_at = now if success else self._parse_dt(previous["last_success_at"])
        availability = self._availability_score(provider)
        freshness = self._freshness_score(last_success_at, now)
        quality = QUALITY_SCORE.get(provider, float(previous["data_quality_score"]))
        latency = self._latency_score(self._recent_latency_ms(provider))
        rate_limit = self._recent_rate_limit_score(provider)
        health = (
            0.30 * availability
            + 0.25 * freshness
            + 0.20 * quality
            + 0.15 * latency
            + 0.10 * rate_limit
        )

        self.store.connection.execute(
            """
            UPDATE provider_health_state
            SET circuit_state=?,consecutive_failures=?,opened_at=?,
                last_attempt_at=?,last_success_at=?,availability_score=?,
                freshness_score=?,data_quality_score=?,latency_score=?,
                rate_limit_score=?,health_score=?,last_message=?,updated_at=?
            WHERE provider=?
            """,
            (
                state,
                failures,
                opened_at,
                now.isoformat(),
                last_success_at.isoformat() if last_success_at else None,
                availability,
                freshness,
                quality,
                latency,
                rate_limit,
                health,
                message,
                now.isoformat(),
                provider,
            ),
        )
        self.store.connection.commit()
