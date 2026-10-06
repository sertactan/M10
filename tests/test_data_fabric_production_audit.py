from __future__ import annotations

import asyncio
from time import perf_counter

import pytest

from core.data_sync.racing import race_in_canonical_order
from data.cache.sec_json_mirror import SecJsonMirror
from data.database.sqlite_store import SQLiteStore
from data.providers.http_json import JsonHttpResponse
from data.repositories.provider_health_repository import ProviderHealthRepository


class _Http:
    def __init__(self, *, response=None, error: Exception | None = None):
        self.response = response
        self.error = error

    async def get_json_response(self, *args, **kwargs):
        if self.error is not None:
            raise self.error
        return self.response


@pytest.mark.asyncio
async def test_production_audit_network_failure_uses_sec_last_known_good(tmp_path):
    mirror = SecJsonMirror(tmp_path / "sec")
    url = "https://data.sec.gov/submissions/CIK0000000001.json"

    first = await mirror.fetch_json(
        _Http(
            response=JsonHttpResponse(
                payload={"cik": "0000000001"},
                status_code=200,
                etag='"audit-v1"',
                last_modified="Tue, 06 Oct 2026 00:00:00 GMT",
                not_modified=False,
            )
        ),
        url,
    )
    assert first.source == "NETWORK"

    fallback = await mirror.fetch_json(
        _Http(error=RuntimeError("simulated network outage")),
        url,
    )
    assert fallback.source == "LAST_KNOWN_GOOD"
    assert fallback.payload == {"cik": "0000000001"}


@pytest.mark.asyncio
async def test_production_audit_corrupt_sec_cache_fails_closed(tmp_path):
    mirror = SecJsonMirror(tmp_path / "sec")
    url = "https://data.sec.gov/submissions/CIK0000000002.json"
    payload_path, meta_path = mirror._paths(url)
    payload_path.write_text("{not-json", encoding="utf-8")
    meta_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(RuntimeError, match="simulated outage"):
        await mirror.fetch_json(
            _Http(error=RuntimeError("simulated outage")),
            url,
        )


def test_production_audit_rate_limit_opens_circuit_and_records_capacity(tmp_path):
    store = SQLiteStore(tmp_path / "audit.sqlite")
    store.initialize()
    try:
        health = ProviderHealthRepository(
            store,
            failure_threshold=3,
            cooldown_seconds=3600,
        )
        for _ in range(3):
            health.record_failure(
                "FINNHUB",
                latency_ms=900.0,
                rate_limited=True,
                message="HTTP 429 rate limit",
            )

        snapshot = health.snapshot("FINNHUB")
        assert snapshot.circuit_state == "OPEN"
        assert snapshot.consecutive_failures == 3
        assert snapshot.rate_limit_score == 0.0
        assert health.can_attempt("FINNHUB") is False
    finally:
        store.close()


@pytest.mark.asyncio
async def test_production_audit_provider_outage_uses_ready_fallback_without_priority_drift():
    timings = {}

    async def probe(name):
        started = perf_counter()
        if name == "PRIMARY":
            await asyncio.sleep(0.05)
            timings[name] = perf_counter() - started
            raise RuntimeError("simulated provider outage")
        await asyncio.sleep(0.005)
        timings[name] = perf_counter() - started
        return "fallback-ready"

    started = perf_counter()
    result = await race_in_canonical_order(
        ("PRIMARY", "SECONDARY"),
        probe,
        lambda item: item.error is None,
    )
    elapsed = perf_counter() - started

    assert result is not None
    assert result.provider == "SECONDARY"
    assert result.value == "fallback-ready"
    assert timings["SECONDARY"] < timings["PRIMARY"]
    assert elapsed < 0.12


def test_production_audit_local_health_snapshot_benchmark(tmp_path):
    store = SQLiteStore(tmp_path / "benchmark.sqlite")
    store.initialize()
    try:
        health = ProviderHealthRepository(store)
        for _ in range(25):
            health.record_success("SEC_EDGAR", latency_ms=100.0)

        started = perf_counter()
        for _ in range(100):
            snapshot = health.snapshot("SEC_EDGAR")
            assert snapshot.circuit_state == "CLOSED"
        elapsed = perf_counter() - started

        # Generous CI guardrail: catches accidental network calls or expensive
        # regressions in this local-only path without making timing flaky.
        assert elapsed < 2.0
    finally:
        store.close()


def test_production_audit_sqlite_integrity_guard(tmp_path):
    store = SQLiteStore(tmp_path / "integrity.sqlite")
    store.initialize()
    try:
        assert store.connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    finally:
        store.close()
