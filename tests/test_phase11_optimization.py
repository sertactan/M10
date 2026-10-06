from __future__ import annotations

from datetime import date, datetime, timezone
from threading import Lock

from core.optimization.acceptance import (
    PHASE11_ACCEPTANCE_ITEMS,
    OptimizationAcceptanceItem,
    require_phase11_complete,
)
from core.optimization.cache import BoundedLRUCache
from core.optimization.parallel_scanner import ParallelMarketScanner
from core.optimization.duckdb_analytics import DuckDBAnalyticsMirror
from data.database.duckdb_store import DuckDBStore
from data.database.sqlite_store import SQLiteStore
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
    assert not list((tmp_path / "pq").rglob("*.tmp.parquet"))



def test_duckdb_mirror_preserves_ready_model_evidence(tmp_path):
    sqlite = SQLiteStore(tmp_path / "ops.sqlite")
    sqlite.initialize()
    duckdb = DuckDBStore(tmp_path / "analytics.duckdb")
    try:
        now = datetime(2026, 10, 6, tzinfo=timezone.utc).isoformat()
        sqlite.connection.execute(
            """
            INSERT INTO security_master (
                security_id,ticker,name,exchange,market,active,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            ("SEC_A","AAA","AAA Inc.","NASDAQ","US",1,now,now),
        )
        sqlite.connection.execute(
            """
            INSERT INTO forward_outcomes (
                observation_id,security_id,as_of_date_requested,anchor_session,
                anchor_lag_calendar_days,entry_adjusted_close,horizon_sessions_available,
                fm252,max_multiple_observed,outcome_class,time_to_2x_sessions,
                time_to_3x_sessions,time_to_5x_sessions,time_to_7x_sessions,
                time_to_10x_sessions,outcome_status,diagnostics_json,outcome_hash,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "SEC_A|2024-01-02","SEC_A","2024-01-02","2024-01-02",
                0,10.0,252,12.0,12.0,"TRUE_10X",
                None,None,None,None,None,"READY","{}","a"*64,now,
            ),
        )
        for version, score in (("S15.3_V1.2",80.0),("S15.3_V1.4",84.0)):
            sqlite.connection.execute(
                """
                INSERT INTO backtest_predictions (
                    observation_id,model_version,score,precision_confirmed,
                    status,score_hash,created_at
                ) VALUES (?,?,?,?,?,?,?)
                """,
                ("SEC_A|2024-01-02",version,score,1,"READY","b"*64,now),
            )
        sqlite.connection.execute(
            """
            INSERT INTO analysis_runs (
                analysis_id,ticker,security_id,analysis_date,mode,model_version,
                data_snapshot_hash,model_config_hash,score,route,destination,prediction,
                status,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "A1","AAA","SEC_A","2024-01-02","HISTORICAL","S15.3_V1.2",
                "c"*64,"d"*64,80.0,"F10",None,None,"READY",now,
            ),
        )
        sqlite.connection.execute(
            """
            INSERT INTO backtest_results (
                analysis_id,entry_price,return_1m,return_3m,return_6m,return_12m,
                max_gain_12m,max_drawdown_12m,result_class,outcome_status
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            ("A1",10.0,None,None,None,950.0,None,None,"TRUE_10X","READY"),
        )
        sqlite.connection.commit()

        mirror = DuckDBAnalyticsMirror(duckdb)
        stats = mirror.refresh_from_sqlite(sqlite)
        assert stats.forward_outcomes == 1
        assert stats.backtest_predictions == 2
        assert mirror.paired_model_rows(
            model_a="S15.3_V1.2",
            model_b="S15.3_V1.4",
        ) == [("SEC_A|2024-01-02",80.0,84.0,1,1,12.0)]
        assert mirror.route_performance_rows(model_version="S15.3_V1.2") == [
            ("F10",1,80.0,950.0)
        ]
    finally:
        duckdb.close()
        sqlite.close()



def test_phase11_acceptance_gate_requires_exact_scope():
    items = [
        OptimizationAcceptanceItem(name=name, passed=True, evidence="tested")
        for name in PHASE11_ACCEPTANCE_ITEMS
    ]
    require_phase11_complete(items)
    assert len(PHASE11_ACCEPTANCE_ITEMS) == 6
