from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock

from core.optimization.parallel_scanner import ParallelMarketScanner
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
