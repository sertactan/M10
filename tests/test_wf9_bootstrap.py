from datetime import date
from types import SimpleNamespace

from data.database.sqlite_store import SQLiteStore
from scripts.bootstrap_wf9_canonical_data import (
    _already_covered,
    _month_count,
)


def test_wf9_default_window_is_144_months():
    assert _month_count(date(2013, 1, 1), date(2024, 12, 31)) == 144


def test_wf9_price_bootstrap_accepts_only_backtest_selection(tmp_path):
    store = SQLiteStore(tmp_path / "wf9.sqlite")
    store.initialize()
    try:
        now = "2026-10-07T00:00:00+00:00"
        store.connection.execute(
            """
            INSERT INTO security_master (
                security_id,ticker,name,exchange,market,active,created_at,updated_at
            ) VALUES ('S','AAA','A','NASDAQ','US',1,?,?)
            """,
            (now, now),
        )
        store.connection.execute(
            """
            INSERT INTO canonical_price_selection (
                selection_id,security_id,purpose,start_date,end_date,
                source,source_symbol,reason,selected_at
            ) VALUES ('UI','S','UI_LIVE_FALLBACK','2012-01-01','2026-02-04',
                      'YAHOO_COMPAT','AAA','ui only',?)
            """,
            (now,),
        )
        store.connection.commit()
        app = SimpleNamespace(sqlite=store)
        target = SimpleNamespace(security_id="S")
        assert not _already_covered(
            app, target, date(2012, 1, 1), date(2026, 2, 4)
        )

        store.connection.execute(
            """
            INSERT INTO canonical_price_selection (
                selection_id,security_id,purpose,start_date,end_date,
                source,source_symbol,reason,selected_at
            ) VALUES ('BT','S','BACKTEST_ADJUSTED','2012-01-01','2026-02-04',
                      'MASSIVE','AAA','canonical',?)
            """,
            (now,),
        )
        store.connection.commit()
        assert _already_covered(
            app, target, date(2012, 1, 1), date(2026, 2, 4)
        )
    finally:
        store.close()
