from __future__ import annotations

import asyncio
from typing import Any

import httpx


class ProviderHTTPError(RuntimeError):
    pass


class JsonHttpClient:
    def __init__(self, timeout_seconds: float = 30.0, max_retries: int = 3) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.get(url, params=params, headers=headers)
                    if response.status_code == 429 or response.status_code >= 500:
                        retry_after = response.headers.get("Retry-After")
                        delay = float(retry_after) if retry_after else min(8.0, 0.5 * (2**attempt))
                        if attempt >= self.max_retries:
                            response.raise_for_status()
                        await asyncio.sleep(delay)
                        continue
                    response.raise_for_status()
                    return response.json()
                except (httpx.HTTPError, ValueError) as exc:
                    last_error = exc
                    if attempt >= self.max_retries:
                        break
                    await asyncio.sleep(min(8.0, 0.5 * (2**attempt)))
        raise ProviderHTTPError(f"GET failed for {url}: {last_error}")
