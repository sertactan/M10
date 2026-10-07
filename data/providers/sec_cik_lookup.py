from __future__ import annotations

import re
from pathlib import Path

import httpx

from core.universe.identity import normalize_cik, normalize_name
from data.providers.sec_access import resolve_sec_user_agent


class SecCikLookupUnavailable(RuntimeError):
    pass


class SecCikNameLookupProvider:
    """Conservative SEC company-name -> CIK resolver.

    Only normalized names mapping to exactly one CIK are returned. Ambiguous
    names are intentionally excluded.
    """

    url = "https://www.sec.gov/Archives/edgar/cik-lookup-data.txt"

    def __init__(self, *, timeout_seconds: float = 180.0) -> None:
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def parse(text: str) -> dict[str, str]:
        candidates: dict[str, set[str]] = {}
        for line in text.splitlines():
            match = re.match(r"^(.*):(\d+):\s*$", line.strip())
            if not match:
                continue
            name = normalize_name(match.group(1))
            cik = normalize_cik(match.group(2))
            if not name or cik is None:
                continue
            candidates.setdefault(name, set()).add(cik)
        return {
            name: next(iter(ciks))
            for name, ciks in candidates.items()
            if len(ciks) == 1
        }

    async def load(self, cache_path: Path | None = None) -> dict[str, str]:
        if cache_path is not None and cache_path.exists():
            return self.parse(cache_path.read_text(encoding="utf-8", errors="replace"))

        headers = {
            "User-Agent": resolve_sec_user_agent(),
            "Accept-Encoding": "gzip, deflate",
        }
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = await client.get(self.url)
            response.raise_for_status()
        text = response.content.decode("utf-8", errors="replace")
        mapping = self.parse(text)
        if not mapping:
            raise SecCikLookupUnavailable("SEC CIK lookup produced no unique mappings")
        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(text, encoding="utf-8")
        return mapping
