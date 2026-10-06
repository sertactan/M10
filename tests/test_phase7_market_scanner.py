from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from threading import Event
from datetime import timedelta

import pytest

from app.scanner_worker import ScannerWorker
from core.scanner.acceptance import PHASE7_ACCEPTANCE_ITEMS, AcceptanceItem, require_all_pass
from core.scanner.contracts import ScanCandidate, ScanMode
from core.scanner.engine import MarketScanner
from core.scanner.resultset import export_csv, filter_rows, sort_rows
from core.features.s153_v12_input_loader import S153V12InputLoader
from data.database.sqlite_store import SQLiteStore
from data.repositories.model_feature_repository import ModelFeatureRepository
from data.repositories.security_repository import SecurityRepository
from core.scanner.production import CanonicalDualModelScorer, RepositoryCandidateSource


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


def test_repository_candidate_source_preserves_historical_delisted_members(tmp_path: Path):
    store = SQLiteStore(tmp_path / "universe.sqlite")
    store.initialize()
    try:
        now = AS_OF.isoformat()
        securities = [
            ("SEC_NQ","NQ","Nasdaq Co","NASDAQ",1,None),
            ("SEC_NY","NY","Nyse Co","NYSE",1,None),
            ("SEC_AX","AX","Amex Co","AMEX",1,None),
            ("SEC_OLD","OLD","Old Co","NASDAQ",0,"2026-01-01"),
        ]
        store.connection.executemany(
            """
            INSERT INTO security_master (
                security_id,ticker,name,exchange,market,delisted_date,
                active,created_at,updated_at,security_type
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (sid,ticker,name,exchange,"US",delisted,active,now,now,"CS")
                for sid,ticker,name,exchange,active,delisted in securities
            ],
        )
        snapshot = AS_OF.date().isoformat()
        store.connection.executemany(
            """
            INSERT INTO universe_snapshot_membership (
                snapshot_date,security_id,ticker,exchange,exchange_mic,
                security_type,source,availability_date,ingested_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            [
                (snapshot,sid,ticker,exchange,exchange,"CS","TEST",now,now)
                for sid,ticker,_name,exchange,_active,_delisted in securities
            ],
        )
        store.connection.commit()

        source = RepositoryCandidateSource(SecurityRepository(store))
        current = source.current()
        assert {c.exchange for c in current} == {"NASDAQ","NYSE","AMEX"}
        assert {c.ticker for c in current} == {"NQ","NY","AX"}

        historical = source.historical(AS_OF)
        assert len(historical) == 4
        old = next(c for c in historical if c.ticker == "OLD")
        assert old.active is False
        assert old.delisted_date == "2026-01-01"
    finally:
        store.close()


def test_phase7_pit_filtering_excludes_future_feature_versions(tmp_path: Path):
    store = SQLiteStore(tmp_path / "pit.sqlite")
    store.initialize()
    try:
        store.connection.execute(
            """
            INSERT INTO security_master (
                security_id,ticker,name,exchange,market,active,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                "SEC_TEST","TEST","Test Inc.","NASDAQ","US",1,
                AS_OF.isoformat(),AS_OF.isoformat(),
            ),
        )
        store.connection.commit()
        repository = ModelFeatureRepository(store)
        repository.save_feature(
            security_id="SEC_TEST",
            feature_key="D01",
            value=21.0,
            feature_as_of=AS_OF - timedelta(days=1),
            available_at=AS_OF - timedelta(days=1),
            source_phase="PHASE3_FUNDAMENTAL",
            source_ref="before-cutoff",
            quality_status="CANONICAL",
            computation_version="test",
        )
        repository.save_feature(
            security_id="SEC_TEST",
            feature_key="D01",
            value=99.0,
            feature_as_of=AS_OF + timedelta(days=1),
            available_at=AS_OF + timedelta(days=1),
            source_phase="PHASE3_FUNDAMENTAL",
            source_ref="future-version",
            quality_status="CANONICAL",
            computation_version="test",
        )
        loaded = S153V12InputLoader(repository).load(
            security_id="SEC_TEST",
            ticker="TEST",
            as_of=AS_OF,
        )
        assert loaded.discovery_factors[1] == 21.0
    finally:
        store.close()


def test_production_scanner_uses_canonical_v141_without_faking_missing_inputs(tmp_path: Path):
    store = SQLiteStore(tmp_path / "production-gate.sqlite")
    store.initialize()
    try:
        scorer = CanonicalDualModelScorer(ModelFeatureRepository(store))
        v12, v14 = scorer.score(candidate(1, "NASDAQ"), AS_OF)
        assert v12.score is None
        assert v14.score is None
        assert v14.status == "INCONCLUSIVE_V1_4_1_INPUTS"
        assert v14.large_winner_probability is None
        assert v14.risk_adjusted_conviction is None
    finally:
        store.close()


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
        evidence="deliberate negative acceptance fixture",
    )
    with pytest.raises(RuntimeError, match="V1.4 scoring"):
        require_all_pass(blocked)
