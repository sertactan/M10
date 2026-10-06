from __future__ import annotations

from dataclasses import dataclass

import pytest

from data.cache.sec_json_mirror import SecJsonMirror
from data.providers.http_json import JsonHttpResponse


class _HTTP:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers_seen = []

    async def get_json_response(self, url, *, headers=None, allow_not_modified=False, params=None):
        self.headers_seen.append(dict(headers or {}))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.mark.asyncio
async def test_sec_mirror_uses_etag_then_304_cache(tmp_path):
    mirror = SecJsonMirror(tmp_path)
    url = "https://data.sec.gov/example.json"
    first = JsonHttpResponse(
        payload={"version": 1},
        status_code=200,
        etag='"abc"',
        last_modified="Tue, 06 Oct 2026 00:00:00 GMT",
        not_modified=False,
    )
    second = JsonHttpResponse(
        payload=None,
        status_code=304,
        etag='"abc"',
        last_modified="Tue, 06 Oct 2026 00:00:00 GMT",
        not_modified=True,
    )
    http = _HTTP([first, second])

    a = await mirror.fetch_json(http, url, headers={"User-Agent": "M10 test@example.com"})
    b = await mirror.fetch_json(http, url, headers={"User-Agent": "M10 test@example.com"})

    assert a.source == "NETWORK"
    assert b.source == "NOT_MODIFIED"
    assert b.payload == {"version": 1}
    assert http.headers_seen[1]["If-None-Match"] == '"abc"'
    assert "If-Modified-Since" in http.headers_seen[1]


@pytest.mark.asyncio
async def test_sec_mirror_uses_last_known_good_on_outage(tmp_path):
    mirror = SecJsonMirror(tmp_path)
    url = "https://data.sec.gov/example.json"
    http = _HTTP([
        JsonHttpResponse(
            payload={"facts": [1, 2, 3]},
            status_code=200,
            etag='"v1"',
            last_modified=None,
            not_modified=False,
        ),
        RuntimeError("SEC temporarily unavailable"),
    ])

    await mirror.fetch_json(http, url)
    fallback = await mirror.fetch_json(http, url)

    assert fallback.source == "LAST_KNOWN_GOOD"
    assert fallback.payload == {"facts": [1, 2, 3]}


@pytest.mark.asyncio
async def test_sec_mirror_fails_closed_without_any_cache(tmp_path):
    mirror = SecJsonMirror(tmp_path)
    http = _HTTP([RuntimeError("offline")])

    with pytest.raises(RuntimeError, match="offline"):
        await mirror.fetch_json(http, "https://data.sec.gov/missing.json")
