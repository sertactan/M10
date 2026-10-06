from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class UpdateManifestError(RuntimeError):
    pass


@dataclass(frozen=True)
class UpdateManifest:
    version: str
    download_url: str
    sha256: str
    release_notes_url: str | None = None


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = value.strip().lstrip("v").split(".")
    if not parts or any(not part.isdigit() for part in parts):
        raise UpdateManifestError(f"Unsupported version format: {value}")
    return tuple(int(part) for part in parts)


def parse_manifest(payload: dict[str, Any]) -> UpdateManifest:
    version = str(payload.get("version") or "").strip()
    download_url = str(payload.get("download_url") or "").strip()
    sha256 = str(payload.get("sha256") or "").strip().lower()
    if not version or not download_url:
        raise UpdateManifestError("version and download_url are required")
    if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
        raise UpdateManifestError("sha256 must be a 64-character hex digest")
    _version_tuple(version)
    return UpdateManifest(
        version=version,
        download_url=download_url,
        sha256=sha256,
        release_notes_url=(
            str(payload["release_notes_url"]).strip()
            if payload.get("release_notes_url")
            else None
        ),
    )


def is_newer_version(*, current: str, candidate: str) -> bool:
    return _version_tuple(candidate) > _version_tuple(current)


def fetch_update_manifest(
    url: str,
    *,
    timeout_seconds: float = 5.0,
) -> UpdateManifest:
    response = httpx.get(url, timeout=timeout_seconds, follow_redirects=True)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise UpdateManifestError("update manifest must be a JSON object")
    return parse_manifest(payload)
