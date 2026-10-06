from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx


class ProviderHTTPError(RuntimeError):
    pass


@dataclass(frozen=True)
class JsonHttpResponse:
    payload: Any | None
    status_code: int
    etag: str | None
    last_modified: str | None
    not_modified: bool = False


class JsonHttpClient:
    def __init__(self, timeout_seconds: float = 30.0, max_retries: int = 3) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    async def get_json_response(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        allow_not_modified: bool = False,
    ) -> JsonHttpResponse:
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.get(url, params=params, headers=headers)
                    if allow_not_modified and response.status_code == 304:
                        return JsonHttpResponse(
                            payload=None,
                            status_code=304,
                            etag=response.headers.get("ETag"),
                            last_modified=response.headers.get("Last-Modified"),
                            not_modified=True,
                        )
                    if response.status_code == 429 or response.status_code >= 500:
                        retry_after = response.headers.get("Retry-After")
                        delay = float(retry_after) if retry_after else min(8.0, 0.5 * (2**attempt))
                        if attempt >= self.max_retries:
                            response.raise_for_status()
                        await asyncio.sleep(delay)
                        continue
                    response.raise_for_status()
                    return JsonHttpResponse(
                        payload=response.json(),
                        status_code=response.status_code,
                        etag=response.headers.get("ETag"),
                        last_modified=response.headers.get("Last-Modified"),
                        not_modified=False,
                    )
                except (httpx.HTTPError, ValueError) as exc:
                    last_error = exc
                    if attempt >= self.max_retries:
                        break
                    await asyncio.sleep(min(8.0, 0.5 * (2**attempt)))
        raise ProviderHTTPError(f"GET failed for {url}: {last_error}")

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        response = await self.get_json_response(url, params=params, headers=headers)
        return response.payload
