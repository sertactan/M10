from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data.providers.http_json import JsonHttpClient


@dataclass(frozen=True)
class MirroredJsonResult:
    payload: Any
    source: str
    etag: str | None
    last_modified: str | None
    retrieved_at: datetime


class SecJsonMirror:
    """Disk-backed SEC JSON mirror with conditional refresh and LKG fallback."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _key(url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def _paths(self, url: str) -> tuple[Path, Path]:
        key = self._key(url)
        return self.root / f"{key}.json", self.root / f"{key}.meta.json"

    def _load(self, url: str) -> tuple[Any, dict] | None:
        payload_path, meta_path = self._paths(url)
        if not payload_path.exists() or not meta_path.exists():
            return None
        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if meta.get("url") != url:
            return None
        return payload, meta

    def _store(
        self,
        url: str,
        payload: Any,
        *,
        etag: str | None,
        last_modified: str | None,
        retrieved_at: datetime,
    ) -> None:
        payload_path, meta_path = self._paths(url)
        payload_text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        meta = {
            "url": url,
            "etag": etag,
            "last_modified": last_modified,
            "retrieved_at": retrieved_at.astimezone(timezone.utc).isoformat(),
            "sha256": hashlib.sha256(payload_text.encode("utf-8")).hexdigest(),
        }

        payload_tmp = payload_path.with_suffix(payload_path.suffix + ".tmp")
        meta_tmp = meta_path.with_suffix(meta_path.suffix + ".tmp")
        payload_tmp.write_text(payload_text, encoding="utf-8")
        meta_tmp.write_text(
            json.dumps(meta, separators=(",", ":"), sort_keys=True),
            encoding="utf-8",
        )
        payload_tmp.replace(payload_path)
        meta_tmp.replace(meta_path)

    async def fetch_json(
        self,
        http: JsonHttpClient,
        url: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> MirroredJsonResult:
        cached = self._load(url)
        conditional_headers = dict(headers or {})
        if cached is not None:
            _, meta = cached
            if meta.get("etag"):
                conditional_headers["If-None-Match"] = str(meta["etag"])
            if meta.get("last_modified"):
                conditional_headers["If-Modified-Since"] = str(meta["last_modified"])

        try:
            response = await http.get_json_response(
                url,
                headers=conditional_headers,
                allow_not_modified=True,
            )
        except Exception:
            if cached is None:
                raise
            payload, meta = cached
            return MirroredJsonResult(
                payload=payload,
                source="LAST_KNOWN_GOOD",
                etag=meta.get("etag"),
                last_modified=meta.get("last_modified"),
                retrieved_at=datetime.fromisoformat(meta["retrieved_at"]),
            )

        now = datetime.now(timezone.utc)
        if response.not_modified:
            if cached is None:
                raise RuntimeError(f"SEC returned 304 without local mirror for {url}")
            payload, meta = cached
            return MirroredJsonResult(
                payload=payload,
                source="NOT_MODIFIED",
                etag=response.etag or meta.get("etag"),
                last_modified=response.last_modified or meta.get("last_modified"),
                retrieved_at=datetime.fromisoformat(meta["retrieved_at"]),
            )

        self._store(
            url,
            response.payload,
            etag=response.etag,
            last_modified=response.last_modified,
            retrieved_at=now,
        )
        return MirroredJsonResult(
            payload=response.payload,
            source="NETWORK",
            etag=response.etag,
            last_modified=response.last_modified,
            retrieved_at=now,
        )
