from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.bulk_data_bootstrap import (
    discover_stooq_us_daily_ascii_url,
    import_sec_companyfacts_zip,
)
from data.database.sqlite_store import SQLiteStore
from data.providers.sec_access import DEFAULT_SEC_USER_AGENT, resolve_sec_user_agent
from data.providers.stooq_price import StooqPriceProvider


def test_default_sec_user_agent_works_without_environment(monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    assert resolve_sec_user_agent() == DEFAULT_SEC_USER_AGENT
    assert "github.com/sertactan/M10" in resolve_sec_user_agent()


def test_user_sec_user_agent_still_has_priority(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "Example Corp ops@example.com")
    assert resolve_sec_user_agent() == "Example Corp ops@example.com"
    assert resolve_sec_user_agent("Explicit Agent explicit@example.com") == (
        "Explicit Agent explicit@example.com"
    )


def test_discovers_us_daily_ascii_zip_from_stooq_page():
    html = """
    <a href="db/h/1_pl_txt.zip">Poland</a>
    <a href="/db/h/2_us_txt.zip">U.S. Daily ASCII</a>
    <a href="/db/h/2_us_xls.zip">U.S. Spreadsheet</a>
    """
    url = discover_stooq_us_daily_ascii_url(html)
    assert url == "https://stooq.com/db/h/2_us_txt.zip"


def test_stooq_bulk_streaming_splits_symbol_series(tmp_path: Path):
    archive = tmp_path / "stooq.zip"
    text = (
        "<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>\n"
        "AAA.US,D,20261001,000000,10,11,9,10.5,1000,0\n"
        "AAA.US,D,20261002,000000,10.5,12,10,11.5,1200,0\n"
        "BBB.US,D,20261001,000000,20,21,19,20.5,2000,0\n"
    )
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("data/us.txt", text)

    provider = StooqPriceProvider()
    groups = list(
        provider.iter_bulk_zip_series(
            archive,
            security_lookup=lambda ticker: {"AAA": "SEC_AAA", "BBB": "SEC_BBB"}.get(ticker),
            retrieved_at=datetime(2026, 10, 6, tzinfo=timezone.utc),
        )
    )
    assert len(groups) == 2
    assert [bar.security_id for bar in groups[0]] == ["SEC_AAA", "SEC_AAA"]
    assert [bar.security_id for bar in groups[1]] == ["SEC_BBB"]


def test_sec_companyfacts_bulk_import_keeps_only_canonical_metrics(tmp_path: Path):
    store = SQLiteStore(tmp_path / "bulk.sqlite")
    store.initialize()
    try:
        now = datetime(2026, 10, 6, tzinfo=timezone.utc).isoformat()
        store.connection.execute(
            """
            INSERT INTO security_master (
                security_id,ticker,name,exchange,market,cik,active,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                "SEC_TEST",
                "TEST",
                "Test Inc.",
                "NASDAQ",
                "US",
                "0000000001",
                1,
                now,
                now,
            ),
        )
        store.connection.commit()

        payload = {
            "facts": {
                "us-gaap": {
                    "Revenues": {
                        "units": {
                            "USD": [
                                {
                                    "start": "2024-01-01",
                                    "end": "2024-12-31",
                                    "val": 100.0,
                                    "accn": "0000000001-25-000001",
                                    "fy": 2024,
                                    "fp": "FY",
                                    "form": "10-K",
                                    "filed": "2025-02-15",
                                }
                            ]
                        }
                    },
                    "SomeUnsupportedTag": {
                        "units": {
                            "USD": [
                                {
                                    "start": "2024-01-01",
                                    "end": "2024-12-31",
                                    "val": 999.0,
                                    "form": "10-K",
                                    "filed": "2025-02-15",
                                }
                            ]
                        }
                    },
                }
            }
        }
        archive = tmp_path / "companyfacts.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("CIK0000000001.json", json.dumps(payload))

        securities, facts = import_sec_companyfacts_zip(
            SimpleNamespace(sqlite=store),
            archive,
        )
        assert securities == 1
        assert facts == 1

        rows = store.connection.execute(
            "SELECT metric_name,source,validation_status FROM fundamental_facts_source"
        ).fetchall()
        assert [row["metric_name"] for row in rows] == ["REVENUE"]
        assert rows[0]["source"] == "SEC_EDGAR"
        assert rows[0]["validation_status"] == "SEC_CANONICAL"
    finally:
        store.close()
