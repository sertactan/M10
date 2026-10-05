from __future__ import annotations

from datetime import date, datetime, timezone
from threading import Lock

from core.optimization.cache import BoundedLRUCache
from core.optimization.parallel_scanner import ParallelMarketScanner
from core.prices.models import AdjustmentStatus, PriceQualityStatus, SourcePriceBar
from data.storage.parquet_price_store import ParquetPriceStore
from core.scanner.contracts import ScanCandidate


AS_OF = datetime(2026, 10, 6, tzinfo=timezone.utc)


class Candidates:
    def __init__(self, rows):
        self.rows = rows

    def current(self):
        return list(self.rows)

    def historical(self, as_of):
        assert as_of == AS_OF
        return list(self.rows)


class WorkerScorer:
    def __init__(self, closed):
        self.closed = closed

    def score(self, candidate, as_of):
        base = float(int(candidate.security_id.split("_")[-1]))
        v12 = type("V12", (), {
            "score": base,
            "status": "READY",
            "primary_route": "F10",
            "verdict": "DISCOVERY",
            "confidence": 80.0,
        })()
        v14 = type("V14", (), {
            "score": base + 1.0,
            "status": "READY",
            "primary_route": "EARLY_ASYMMETRIC",
            "primary_magnitude": "3X-5X",
            "confidence": 82.0,
        })()
        return v12, v14

    def close(self):
        with self.closed["lock"]:
            self.closed["count"] += 1


def test_parallel_scanner_preserves_deterministic_order_and_closes_workers():
    rows = [
        ScanCandidate(
            security_id=f"SEC_{i}",
            ticker=f"T{i}",
            exchange=("NASDAQ", "NYSE", "AMEX")[i % 3],
        )
        for i in range(30)
    ]
    closed = {"count": 0, "lock": Lock()}
    scanner = ParallelMarketScanner(
        Candidates(rows),
        scorer_factory=lambda: WorkerScorer(closed),
        workers=4,
        batch_size=10,
    )
    progress = []
    result, summary = scanner.scan_current(
        as_of=AS_OF,
        on_progress=lambda p: progress.append(p),
    )

    assert [row.security_id for row in result] == [row.security_id for row in rows]
    assert [row.v12_score for row in result] == [float(i) for i in range(30)]
    assert summary.total == 30
    assert progress[-1].completed == 30
    assert 1 <= closed["count"] <= 4


def test_parallel_scanner_rejects_invalid_worker_count():
    try:
        ParallelMarketScanner(
            Candidates([]),
            scorer_factory=lambda: None,
            workers=0,
        )
    except ValueError as exc:
        assert "workers" in str(exc)
    else:
        raise AssertionError("workers=0 must fail")



def test_bounded_lru_cache_tracks_hits_misses_and_evictions():
    cache = BoundedLRUCache(capacity=2)
    assert cache.get("missing") is None
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1
    cache.put("c", 3)
    assert cache.get("b") is None
    stats = cache.stats
    assert stats.hits == 1
    assert stats.misses == 2
    assert stats.evictions == 1
    assert stats.size == 2


def test_parquet_price_cache_is_provenance_aware_and_copy_safe(tmp_path):
    store = ParquetPriceStore(tmp_path / "pq", cache_capacity=2)
    now = datetime(2026, 10, 6, tzinfo=timezone.utc)
    first = [
        SourcePriceBar(
            security_id="SEC_A",
            source="TEST",
            source_symbol="AAA",
            trade_date=date(2026, 10, 6),
            open=10.0,
            high=11.0,
            low=9.0,
            raw_close=10.0,
            adjusted_close=10.0,
            volume=100.0,
            retrieved_at=now,
            quality_status=PriceQualityStatus.PRIMARY,
            adjustment_status=AdjustmentStatus.DUAL_RAW_ADJUSTED,
        )
    ]
    store.write_bars(first)

    a = store.read_bars(
        security_id="SEC_A",
        source="TEST",
        source_symbol="AAA",
        start_date=date(2026, 10, 6),
        end_date=date(2026, 10, 6),
    )
    b = store.read_bars(
        security_id="SEC_A",
        source="TEST",
        source_symbol="AAA",
        start_date=date(2026, 10, 6),
        end_date=date(2026, 10, 6),
    )
    assert store.cache_stats.hits == 1
    b.loc[b.index[0], "adjusted_close"] = 999.0
    c = store.read_bars(
        security_id="SEC_A",
        source="TEST",
        source_symbol="AAA",
        start_date=date(2026, 10, 6),
        end_date=date(2026, 10, 6),
    )
    assert float(c.iloc[0]["adjusted_close"]) == 10.0

    replacement = [
        SourcePriceBar(
            security_id="SEC_A",
            source="TEST",
            source_symbol="AAA",
            trade_date=date(2026, 10, 6),
            open=12.0,
            high=13.0,
            low=11.0,
            raw_close=12.0,
            adjusted_close=12.0,
            volume=120.0,
            retrieved_at=now,
            quality_status=PriceQualityStatus.PRIMARY,
            adjustment_status=AdjustmentStatus.DUAL_RAW_ADJUSTED,
        )
    ]
    store.write_bars(replacement)
    refreshed = store.read_bars(
        security_id="SEC_A",
        source="TEST",
        source_symbol="AAA",
        start_date=date(2026, 10, 6),
        end_date=date(2026, 10, 6),
    )
    assert float(refreshed.iloc[0]["adjusted_close"]) == 12.0
