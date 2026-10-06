from __future__ import annotations

from datetime import datetime, timedelta, timezone

from data.database.sqlite_store import SQLiteStore
from data.repositories.provider_health_repository import ProviderHealthRepository


def test_provider_health_cold_start_preserves_static_order(tmp_path):
    store = SQLiteStore(tmp_path / "ops.sqlite")
    store.initialize()
    try:
        health = ProviderHealthRepository(store)
        order = ("MASSIVE", "STOOQ", "YAHOO_COMPAT")
        assert health.rank(order) == order
        assert all(health.snapshot(name).health_score == 100.0 for name in order)
    finally:
        store.close()


def test_provider_health_opens_after_failure_threshold_and_recovers(tmp_path):
    store = SQLiteStore(tmp_path / "ops.sqlite")
    store.initialize()
    try:
        health = ProviderHealthRepository(
            store,
            failure_threshold=3,
            cooldown_seconds=60,
        )

        for _ in range(3):
            health.record_failure("STOOQ", latency_ms=900.0, message="temporary failure")

        snap = health.snapshot("STOOQ")
        assert snap.circuit_state == "OPEN"
        assert snap.consecutive_failures == 3
        assert health.can_attempt("STOOQ") is False

        old = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
        store.connection.execute(
            "UPDATE provider_health_state SET opened_at=? WHERE provider='STOOQ'",
            (old,),
        )
        store.connection.commit()

        assert health.snapshot("STOOQ").circuit_state == "HALF_OPEN"
        assert health.can_attempt("STOOQ") is True

        health.record_success("STOOQ", latency_ms=120.0)
        recovered = health.snapshot("STOOQ")
        assert recovered.circuit_state == "CLOSED"
        assert recovered.consecutive_failures == 0
        assert recovered.last_success_at is not None
    finally:
        store.close()


def test_provider_health_score_penalizes_failing_provider_and_reranks(tmp_path):
    store = SQLiteStore(tmp_path / "ops.sqlite")
    store.initialize()
    try:
        health = ProviderHealthRepository(store, failure_threshold=5)
        providers = ("STOOQ", "SIMFIN")
        assert health.rank(providers) == providers

        health.record_failure(
            "STOOQ",
            latency_ms=2500.0,
            rate_limited=True,
            message="429 rate limit",
        )
        health.record_success("SIMFIN", latency_ms=150.0)

        stooq = health.snapshot("STOOQ")
        simfin = health.snapshot("SIMFIN")
        assert stooq.availability_score < simfin.availability_score
        assert stooq.rate_limit_score < simfin.rate_limit_score
        assert stooq.health_score < simfin.health_score
        assert health.rank(providers)[0] == "SIMFIN"
    finally:
        store.close()
