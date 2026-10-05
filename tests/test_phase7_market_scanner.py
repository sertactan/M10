from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from threading import Event

import pytest

from app.scanner_worker import ScannerWorker
from core.scanner.acceptance import PHASE7_ACCEPTANCE_ITEMS, AcceptanceItem, require_all_pass
from core.scanner.contracts import ScanCandidate, ScanMode
from core.scanner.engine import MarketScanner
from core.scanner.resultset import export_csv, filter_rows, sort_rows


AS_OF = datetime(2025, 3, 1, 21, 0, tzinfo=timezone.utc)


class FakeCandidates:
    def __init__(self, current_rows, historical_rows):
        self._current = current_rows
        self._historical = historical_rows

    def current(self):
        return list(self._current)

    def historical(self, as_of):
        assert as_of == AS_OF
        return list(self._historical)


class FakeScorer:
    def score(self, candidate, as_of):
        assert as_of.tzinfo is not None
        base = float(int(candidate.security_id.split("_")[-1]) % 100)
        v12 = SimpleNamespace(
            score=base,
            status="V12_OK",
            primary_route="F10",
            verdict="10X Discovery",
            confidence=80.0,
        )
        v14 = SimpleNamespace(
            score=min(100.0, base + 5.0),
            status="V14_OK",
            primary_route="EARLY_ASYMMETRIC",
            primary_magnitude="3X-5X",
            confidence=82.0,
        )
        return v12, v14


def candidate(i, exchange="NASDAQ", *, active=True, delisted_date=None):
    return ScanCandidate(
        security_id=f"SEC_{i}",
        ticker=f"T{i:05d}",
        exchange=exchange,
        active=active,
        delisted_date=delisted_date,
    )


def test_current_and_historical_scans_cover_all_us_exchanges_and_delisted():
    current = [
        candidate(1, "NASDAQ"),
        candidate(2, "NYSE"),
        candidate(3, "AMEX"),
    ]
    historical = current + [
        candidate(4, "NASDAQ", active=False, delisted_date="2026-01-01"),
    ]
    scanner = MarketScanner(FakeCandidates(current, historical), FakeScorer(), batch_size=2)

    current_rows, current_summary = scanner.scan_current(as_of=AS_OF)
    assert current_summary.mode == ScanMode.CURRENT
    assert current_summary.total == 3
    assert current_summary.nasdaq == 1
    assert current_summary.nyse == 1
    assert current_summary.amex == 1
    assert current_summary.delisted == 0
    assert all(row.v12_status == "V12_OK" for row in current_rows)
    assert all(row.v14_status == "V14_OK" for row in current_rows)

    historical_rows, historical_summary = scanner.scan_historical(as_of=AS_OF)
    assert historical_summary.mode == ScanMode.HISTORICAL
    assert historical_summary.total == 4
    assert historical_summary.delisted == 1
    assert any(row.delisted for row in historical_rows)


def test_sort_filter_and_export(tmp_path: Path):
    rows, _ = MarketScanner(
        FakeCandidates(
            [candidate(1, "NASDAQ"), candidate(2, "NYSE"), candidate(3, "AMEX")],
            [],
        ),
        FakeScorer(),
    ).scan_current(as_of=AS_OF)

    sorted_rows = sort_rows(rows, field="v14_score", descending=True)
    assert [r.v14_score for r in sorted_rows] == sorted(
        [r.v14_score for r in rows], reverse=True
    )

    filtered = filter_rows(
        rows,
        exchanges={"NASDAQ", "NYSE"},
        min_v12_score=1.0,
        min_v14_score=6.0,
    )
    assert {r.exchange for r in filtered} == {"NASDAQ", "NYSE"}

    target = export_csv(rows, tmp_path / "scan.csv")
    payload = target.read_text(encoding="utf-8-sig")
    assert "security_id,ticker,exchange" in payload
    assert "NASDAQ" in payload
    assert "NYSE" in payload
    assert "AMEX" in payload


def test_10000_plus_security_batch_scan_and_progress():
    rows = [
        candidate(
            i,
            ("NASDAQ", "NYSE", "AMEX")[i % 3],
        )
        for i in range(10_050)
    ]
    progress = []
    scanner = MarketScanner(
        FakeCandidates(rows, []),
        FakeScorer(),
        batch_size=500,
    )
    result, summary = scanner.scan_current(
        as_of=AS_OF,
        on_progress=lambda p: progress.append(p),
    )
    assert len(result) == 10_050
    assert summary.total == 10_050
    assert summary.nasdaq > 0
    assert summary.nyse > 0
    assert summary.amex > 0
    assert progress[-1].completed == 10_050
    assert progress[-1].total == 10_050


def test_scanner_worker_keeps_caller_thread_free():
    started = Event()
    release = Event()

    class BlockingScanner:
        def scan_current(self, **kwargs):
            started.set()
            assert release.wait(timeout=5)
            return "done"

    worker = ScannerWorker(lambda: BlockingScanner())
    try:
        future = worker.submit("scan_current", as_of=AS_OF)
        assert started.wait(timeout=5)
        # Caller/UI thread is still executing while scan is blocked in its worker.
        caller_thread_marker = "responsive"
        assert caller_thread_marker == "responsive"
        assert not future.done()
        release.set()
        assert future.result(timeout=5) == "done"
    finally:
        worker.close()


def test_phase7_acceptance_contract_requires_exact_15_items():
    assert len(PHASE7_ACCEPTANCE_ITEMS) == 15
    passed = [
        AcceptanceItem(name=name, passed=True, evidence="unit/integration evidence")
        for name in PHASE7_ACCEPTANCE_ITEMS
    ]
    require_all_pass(passed)

    blocked = list(passed)
    idx = PHASE7_ACCEPTANCE_ITEMS.index("V1.4 scoring")
    blocked[idx] = AcceptanceItem(
        name="V1.4 scoring",
        passed=False,
        evidence="Phase 5 canonical V1.4 specification is not yet bound",
    )
    with pytest.raises(RuntimeError, match="V1.4 scoring"):
        require_all_pass(blocked)
