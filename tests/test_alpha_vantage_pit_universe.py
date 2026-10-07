from datetime import date, datetime, timezone

import pytest

from core.contracts.enums import Exchange
from data.providers.alpha_vantage_pit_universe import (
    AlphaVantagePitUnavailable,
    AlphaVantagePitUniverseProvider,
)


def test_alpha_vantage_listing_status_parser_filters_to_supported_common_stocks() -> None:
    payload = """symbol,name,exchange,assetType,ipoDate,delistingDate,status
AAA,AAA Corp,NASDAQ,Stock,2012-01-03,null,Active
BBB,BBB Corp,NYSE,Stock,2005-06-01,null,Active
CCC,CCC Corp,NYSE MKT,Stock,2010-04-05,null,Active
ETF1,ETF Fund,NYSE ARCA,ETF,2018-01-01,null,Active
SPACU,Example Acquisition Corp - Units,NASDAQ,Stock,2021-01-01,null,Active
SPACW,Example Acquisition Corp - Warrants,NASDAQ,Stock,2021-01-01,null,Active
PREF,Example Corp Preferred Series A,NYSE,Stock,2020-01-01,null,Active
OLD,Old Corp,NASDAQ,Stock,2000-01-01,2014-01-01,Delisted
"""
    rows = AlphaVantagePitUniverseProvider.parse_csv(
        payload,
        as_of=date(2013, 8, 3),
        availability_date=datetime(2026, 10, 7, tzinfo=timezone.utc),
    )
    assert {row.ticker for row in rows} == {"AAA", "BBB", "CCC"}
    assert {row.exchange for row in rows} == {
        Exchange.NASDAQ,
        Exchange.NYSE,
        Exchange.AMEX,
    }
    assert all(row.provider == "ALPHAVANTAGE_PIT" for row in rows)
    assert all(row.active is False for row in rows)


def test_alpha_vantage_listing_status_rejects_pre_2010_dates() -> None:
    with pytest.raises(AlphaVantagePitUnavailable, match="later than 2010-01-01"):
        AlphaVantagePitUniverseProvider.parse_csv(
            "symbol,name,exchange\nAAA,AAA Corp,NASDAQ\n",
            as_of=date(2009, 12, 31),
        )


def test_alpha_vantage_listing_status_rejects_api_error_payload() -> None:
    with pytest.raises(AlphaVantagePitUnavailable, match="API error"):
        AlphaVantagePitUniverseProvider.parse_csv(
            '{"Note":"rate limit"}',
            as_of=date(2013, 8, 3),
        )
