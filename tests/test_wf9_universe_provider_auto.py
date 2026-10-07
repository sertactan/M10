from datetime import date

import pytest

from scripts.sync_free_pit_universe import _load_snapshot


class _Alpha:
    def __init__(self, *, configured=True, value=None, error=None):
        self.configured = configured
        self.value = value
        self.error = error

    async def list_historical_us_securities(self, as_of):
        if self.error:
            raise self.error
        return self.value


class _Massive:
    def __init__(self, *, configured=True, value=None, error=None):
        self.configured = configured
        self.value = value
        self.error = error

    async def list_us_securities(self, *, as_of, active):
        if self.error:
            raise self.error
        return self.value


@pytest.mark.asyncio
async def test_auto_prefers_alpha_when_available():
    alpha = _Alpha(value=["A"])
    massive = _Massive(value=["M"])
    rows, source = await _load_snapshot(
        as_of=date(2020, 1, 31),
        mode="AUTO",
        alpha=alpha,
        massive=massive,
    )
    assert rows == ["A"]
    assert source == "ALPHAVANTAGE_PIT"


@pytest.mark.asyncio
async def test_auto_falls_back_to_massive_after_alpha_failure():
    alpha = _Alpha(error=RuntimeError("rate limited"))
    massive = _Massive(value=["M"])
    rows, source = await _load_snapshot(
        as_of=date(2020, 1, 31),
        mode="AUTO",
        alpha=alpha,
        massive=massive,
    )
    assert rows == ["M"]
    assert source == "MASSIVE_PIT"


@pytest.mark.asyncio
async def test_auto_requires_at_least_one_pit_provider():
    alpha = _Alpha(configured=False)
    massive = _Massive(configured=False)
    with pytest.raises(RuntimeError, match="No PIT-capable"):
        await _load_snapshot(
            as_of=date(2020, 1, 31),
            mode="AUTO",
            alpha=alpha,
            massive=massive,
        )
