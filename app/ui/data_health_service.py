from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from app.bootstrap import AppContainer
from data.database.sqlite_store import SQLiteStore
from data.repositories.background_sync_repository import BackgroundSyncRepository
from data.repositories.provider_health_repository import (
    QUALITY_SCORE,
    ProviderHealthRepository,
)


@dataclass(frozen=True)
class ProviderHealthView:
    provider: str
    health_score: float
    circuit_state: str
    availability_pct: float
    error_rate_pct: float
    latency_ms: float | None
    freshness_age_seconds: float | None
    rate_limit_status: str
    consecutive_failures: int
    last_success_at: datetime | None
    last_attempt_at: datetime | None
    last_message: str | None


@dataclass(frozen=True)
class CacheHealthView:
    status: str
    source: str | None
    source_symbol: str | None
    end_date: date | None
    selected_at: datetime | None
    age_days: int | None


@dataclass(frozen=True)
class BackgroundSyncHealthView:
    status: str
    queue_depth: int
    pending: int
    running: int
    retry: int
    failed: int
    succeeded: int
    last_task_type: str | None
    last_task_status: str | None
    last_updated_at: datetime | None
    last_error: str | None


@dataclass(frozen=True)
class DataHealthSnapshot:
    observed_at: datetime
    providers: tuple[ProviderHealthView, ...]
    cache: CacheHealthView
    background_sync: BackgroundSyncHealthView


class DataHealthService:
    PROVIDERS = tuple(QUALITY_SCORE)

    def __init__(
        self,
        root: Path | None = None,
        *,
        store: SQLiteStore | None = None,
    ) -> None:
        if root is None and store is None:
            raise ValueError("root or store is required")
        self.root = root
        self.store = store

    @staticmethod
    def _parse_dt(value: str | None) -> datetime | None:
        if not value:
            return None
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def snapshot(self) -> DataHealthSnapshot:
        if self.store is not None:
            return self._snapshot_from_store(self.store)
        assert self.root is not None
        app = AppContainer(self.root)
        app.initialize()
        try:
            return self._snapshot_from_store(app.sqlite)
        finally:
            app.close()

    def _snapshot_from_store(self, store: SQLiteStore) -> DataHealthSnapshot:
        now = datetime.now(timezone.utc)
        health = ProviderHealthRepository(store)
        providers: list[ProviderHealthView] = []

        known_rows = store.connection.execute(
            "SELECT provider FROM provider_health_state"
        ).fetchall()
        names = list(self.PROVIDERS)
        for row in known_rows:
            name = str(row["provider"])
            if name not in names:
                names.append(name)

        for name in names:
            snapshot = health.snapshot(name)
            state = store.connection.execute(
                """
                SELECT last_attempt_at,last_message
                FROM provider_health_state
                WHERE provider=?
                """,
                (name,),
            ).fetchone()
            latency = store.connection.execute(
                """
                SELECT AVG(latency_ms) AS avg_ms
                FROM (
                    SELECT latency_ms
                    FROM provider_health_events
                    WHERE provider=? AND success=1 AND latency_ms IS NOT NULL
                    ORDER BY event_id DESC
                    LIMIT 20
                )
                """,
                (name,),
            ).fetchone()
            rate = store.connection.execute(
                """
                SELECT
                    SUM(CASE WHEN rate_limited=1 THEN 1 ELSE 0 END) AS limited,
                    COUNT(*) AS total
                FROM (
                    SELECT rate_limited
                    FROM provider_health_events
                    WHERE provider=?
                    ORDER BY event_id DESC
                    LIMIT 50
                )
                """,
                (name,),
            ).fetchone()

            limited = int(rate["limited"] or 0) if rate is not None else 0
            total = int(rate["total"] or 0) if rate is not None else 0
            rate_status = "OK" if limited == 0 else f"THROTTLED {limited}/{total}"
            freshness_age = (
                max(0.0, (now - snapshot.last_success_at).total_seconds())
                if snapshot.last_success_at is not None
                else None
            )
            providers.append(
                ProviderHealthView(
                    provider=name,
                    health_score=snapshot.health_score,
                    circuit_state=snapshot.circuit_state,
                    availability_pct=snapshot.availability_score,
                    error_rate_pct=max(0.0, 100.0 - snapshot.availability_score),
                    latency_ms=(
                        float(latency["avg_ms"])
                        if latency is not None and latency["avg_ms"] is not None
                        else None
                    ),
                    freshness_age_seconds=freshness_age,
                    rate_limit_status=rate_status,
                    consecutive_failures=snapshot.consecutive_failures,
                    last_success_at=snapshot.last_success_at,
                    last_attempt_at=self._parse_dt(
                        state["last_attempt_at"] if state is not None else None
                    ),
                    last_message=(
                        str(state["last_message"])
                        if state is not None and state["last_message"]
                        else None
                    ),
                )
            )

        providers.sort(key=lambda item: (-item.health_score, item.provider))
        cache = self._cache_health(store, now)
        background = self._background_health(store)
        return DataHealthSnapshot(
            observed_at=now,
            providers=tuple(providers),
            cache=cache,
            background_sync=background,
        )

    def _cache_health(self, store: SQLiteStore, now: datetime) -> CacheHealthView:
        row = store.connection.execute(
            """
            SELECT source,source_symbol,end_date,selected_at
            FROM canonical_price_selection
            ORDER BY selected_at DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return CacheHealthView(
                status="EMPTY",
                source=None,
                source_symbol=None,
                end_date=None,
                selected_at=None,
                age_days=None,
            )

        end_date = date.fromisoformat(str(row["end_date"]))
        age_days = max(0, (now.date() - end_date).days)
        status = "FRESH" if age_days <= 3 else "LAST_KNOWN_GOOD"
        return CacheHealthView(
            status=status,
            source=str(row["source"]),
            source_symbol=str(row["source_symbol"]),
            end_date=end_date,
            selected_at=self._parse_dt(row["selected_at"]),
            age_days=age_days,
        )

    def _background_health(self, store: SQLiteStore) -> BackgroundSyncHealthView:
        counts = BackgroundSyncRepository(store).counts()
        pending = counts.get("PENDING", 0)
        running = counts.get("RUNNING", 0)
        retry = counts.get("RETRY", 0)
        failed = counts.get("FAILED", 0)
        succeeded = counts.get("SUCCEEDED", 0)
        queue_depth = pending + running + retry

        latest = store.connection.execute(
            """
            SELECT task_type,status,updated_at,last_error
            FROM background_sync_tasks
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ).fetchone()

        if running:
            status = "RUNNING"
        elif retry:
            status = "RETRYING"
        elif pending:
            status = "QUEUED"
        elif latest is not None and str(latest["status"]) == "FAILED":
            status = "DEGRADED"
        else:
            status = "IDLE"

        return BackgroundSyncHealthView(
            status=status,
            queue_depth=queue_depth,
            pending=pending,
            running=running,
            retry=retry,
            failed=failed,
            succeeded=succeeded,
            last_task_type=str(latest["task_type"]) if latest is not None else None,
            last_task_status=str(latest["status"]) if latest is not None else None,
            last_updated_at=self._parse_dt(
                latest["updated_at"] if latest is not None else None
            ),
            last_error=(
                str(latest["last_error"])
                if latest is not None and latest["last_error"]
                else None
            ),
        )
