from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from core.models.s153_v14_spec_manifest import (
    REQUIRED_CANONICAL_SOURCES,
    V14SpecificationBinding,
)


class V14SpecBundleError(RuntimeError):
    """Raised when the authoritative V1.4 bundle is missing or fails integrity checks."""


@dataclass(frozen=True)
class V14SpecArtifact:
    name: str
    path: str
    sha256: str


@dataclass(frozen=True)
class V14SpecBundle:
    bundle_id: str
    artifacts: tuple[V14SpecArtifact, ...]

    def by_name(self) -> dict[str, V14SpecArtifact]:
        return {artifact.name: artifact for artifact in self.artifacts}

    def to_binding(self) -> V14SpecificationBinding:
        items = self.by_name()
        return V14SpecificationBinding(
            canonical_specification=_ref(items[REQUIRED_CANONICAL_SOURCES[0]]),
            factor_dna_definitions=_ref(items[REQUIRED_CANONICAL_SOURCES[1]]),
            router_gate_specification=_ref(items[REQUIRED_CANONICAL_SOURCES[2]]),
            dual_magnitude_destination_specification=_ref(items[REQUIRED_CANONICAL_SOURCES[3]]),
            golden_test_cases=_ref(items[REQUIRED_CANONICAL_SOURCES[4]]),
        )


def _ref(artifact: V14SpecArtifact) -> str:
    return f"{artifact.path}#sha256={artifact.sha256}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_verified_bundle(root: str | Path) -> V14SpecBundle:
    root = Path(root)
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        raise V14SpecBundleError("V1.4 canonical bundle manifest.json is missing")

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle_id = str(payload.get("bundle_id") or "").strip()
    if not bundle_id or bundle_id.upper().startswith("PENDING"):
        raise V14SpecBundleError("V1.4 canonical bundle_id is missing or still PENDING")

    raw_artifacts = payload.get("artifacts")
    if not isinstance(raw_artifacts, list):
        raise V14SpecBundleError("V1.4 canonical manifest artifacts must be a list")

    artifacts: list[V14SpecArtifact] = []
    seen_names: set[str] = set()
    seen_paths: set[str] = set()

    for raw in raw_artifacts:
        if not isinstance(raw, dict):
            raise V14SpecBundleError("Each V1.4 artifact entry must be an object")
        name = str(raw.get("name") or "").strip()
        relative_path = str(raw.get("path") or "").strip()
        expected_sha = str(raw.get("sha256") or "").strip().lower()

        if name not in REQUIRED_CANONICAL_SOURCES:
            raise V14SpecBundleError(f"Unexpected V1.4 canonical artifact name: {name!r}")
        if name in seen_names:
            raise V14SpecBundleError(f"Duplicate V1.4 canonical artifact name: {name}")
        if not relative_path or relative_path in seen_paths:
            raise V14SpecBundleError(f"Missing or duplicate V1.4 artifact path for {name}")
        if len(expected_sha) != 64 or any(c not in "0123456789abcdef" for c in expected_sha):
            raise V14SpecBundleError(f"Invalid SHA-256 for V1.4 artifact: {name}")

        path = (root / relative_path).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError as exc:
            raise V14SpecBundleError(
                f"V1.4 artifact path escapes canonical bundle root: {relative_path}"
            ) from exc
        if not path.is_file():
            raise V14SpecBundleError(f"V1.4 canonical artifact file is missing: {relative_path}")
        if path.stat().st_size == 0:
            raise V14SpecBundleError(f"V1.4 canonical artifact file is empty: {relative_path}")

        actual_sha = _sha256(path)
        if actual_sha != expected_sha:
            raise V14SpecBundleError(
                f"V1.4 canonical artifact hash mismatch for {name}: "
                f"expected {expected_sha}, got {actual_sha}"
            )

        artifacts.append(
            V14SpecArtifact(name=name, path=relative_path, sha256=actual_sha)
        )
        seen_names.add(name)
        seen_paths.add(relative_path)

    missing = [name for name in REQUIRED_CANONICAL_SOURCES if name not in seen_names]
    if missing:
        raise V14SpecBundleError(
            "V1.4 canonical bundle is incomplete; missing: " + "; ".join(missing)
        )
    if len(artifacts) != len(REQUIRED_CANONICAL_SOURCES):
        raise V14SpecBundleError("V1.4 canonical bundle must contain exactly five artifacts")

    return V14SpecBundle(bundle_id=bundle_id, artifacts=tuple(artifacts))
