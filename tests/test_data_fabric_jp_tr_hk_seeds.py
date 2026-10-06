from __future__ import annotations

from pathlib import Path

from data.database.sqlite_store import SQLiteStore
from data.seeds import loader as seed_loader
from scripts.build_jp_tr_hk_seed import parse_financedatabase_csv


ROOT = Path(__file__).resolve().parents[1]


def test_financedatabase_market_parser_normalizes_symbols() -> None:
    equity_header = (
        "symbol,name,summary,currency,sector,industry_group,industry,exchange,mic,"
        "market,country,state,city,zipcode,website,market_cap,isin,cusip,figi,"
        "composite_figi,shareclass_figi,delisted\n"
    )

    jp = parse_financedatabase_csv(
        equity_header
        + "7203.T,Toyota Motor Corp,,JPY,Consumer Discretionary,,,JPX,XJPX,"
          "Tokyo Stock Exchange,Japan,,,,,JP3633400001,,FIGI1,CFIGI1,SFIGI1,False\n",
        market="JP",
        exchange="JPX",
        mic="XJPX",
        country="Japan",
        suffix=".T",
        asset_type="Equity",
        snapshot_date="2026-10-06",
    )
    tr = parse_financedatabase_csv(
        equity_header
        + "THYAO.IS,Turk Hava Yollari AO,,TRY,Industrials,,,IST,XIST,"
          "Borsa Istanbul,Turkey,,,,,TRATHYAO91M5,,,,,False\n",
        market="TR",
        exchange="BIST",
        mic="XIST",
        country="Turkey",
        suffix=".IS",
        asset_type="Equity",
        snapshot_date="2026-10-06",
    )
    hk = parse_financedatabase_csv(
        equity_header
        + "0700.HK,Tencent Holdings Ltd,,HKD,Communication Services,,,HKG,XHKG,"
          "Hong Kong Stock Exchange,Hong Kong,,,,,HK070000865,,,,,False\n",
        market="HK",
        exchange="HKEX",
        mic="XHKG",
        country="Hong Kong",
        suffix=".HK",
        asset_type="Equity",
        snapshot_date="2026-10-06",
    )

    assert jp[0].ticker == "7203"
    assert jp[0].source_symbol == "7203.T"
    assert jp[0].mic == "XJPX"
    assert tr[0].ticker == "THYAO"
    assert tr[0].source_symbol == "THYAO.IS"
    assert hk[0].ticker == "0700"
    assert hk[0].source_symbol == "0700.HK"
    assert all(
        row.source_scope == "REFERENCE_ONLY"
        for row in (jp[0], tr[0], hk[0])
    )


def test_parser_ignores_delisted_rows() -> None:
    text = (
        "symbol,name,currency,exchange,mic,country,delisted\n"
        "1111.T,Active Co,JPY,JPX,XJPX,Japan,False\n"
        "2222.T,Old Co,JPY,JPX,XJPX,Japan,True\n"
    )
    rows = parse_financedatabase_csv(
        text,
        market="JP",
        exchange="JPX",
        mic="XJPX",
        country="Japan",
        suffix=".T",
        asset_type="Equity",
        snapshot_date="2026-10-06",
    )
    assert [row.ticker for row in rows] == ["1111"]


def test_bundled_jp_tr_hk_seed_loads_into_security_master(
    tmp_path: Path,
    monkeypatch,
) -> None:
    seed = tmp_path / "jp_tr_hk_current.csv"
    seed.write_text(
        """snapshot_date,market,exchange,mic,ticker,source_symbol,name,asset_type,currency,country,country_code,isin,sector,industry,figi,composite_figi,shareclass_figi,source,source_scope,redistribution_status
2026-10-06,JP,JPX,XJPX,7203,7203.T,Toyota Motor Corp,Equity,JPY,Japan,JP,JP3633400001,Consumer Discretionary,,,,,FINANCEDATABASE_MIT_REFERENCE,REFERENCE_ONLY,MIT_REFERENCE_REQUIRES_SOURCE_POLICY
2026-10-06,TR,BIST,XIST,THYAO,THYAO.IS,Turk Hava Yollari AO,Equity,TRY,Turkey,TR,TRATHYAO91M5,Industrials,,,,,FINANCEDATABASE_MIT_REFERENCE,REFERENCE_ONLY,MIT_REFERENCE_REQUIRES_SOURCE_POLICY
2026-10-06,HK,HKEX,XHKG,0700,0700.HK,Tencent Holdings Ltd,Equity,HKD,Hong Kong,HK,HK070000865,Communication Services,,,,,FINANCEDATABASE_MIT_REFERENCE,REFERENCE_ONLY,MIT_REFERENCE_REQUIRES_SOURCE_POLICY
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(seed_loader, "bundled_jp_tr_hk_seed_path", lambda: seed)

    store = SQLiteStore(tmp_path / "ops.sqlite")
    store.initialize(ROOT / "data" / "database" / "schema.sql")
    try:
        assert seed_loader.bootstrap_bundled_jp_tr_hk_seed(store) == 3

        rows = store.connection.execute(
            """
            SELECT ticker,exchange,market,primary_exchange_mic,aliases,source_scope
            FROM security_master
            WHERE market IN ('JP','TR','HK')
            ORDER BY market
            """
        ).fetchall()
        assert len(rows) == 3

        by_market = {row["market"]: row for row in rows}
        assert by_market["JP"]["ticker"] == "7203"
        assert by_market["JP"]["exchange"] == "JPX"
        assert by_market["JP"]["primary_exchange_mic"] == "XJPX"
        assert by_market["TR"]["ticker"] == "THYAO"
        assert by_market["TR"]["exchange"] == "BIST"
        assert by_market["HK"]["ticker"] == "0700"
        assert by_market["HK"]["exchange"] == "HKEX"
        assert all(row["source_scope"] == "REFERENCE_ONLY" for row in rows)
    finally:
        store.close()
