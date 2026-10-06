from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from core.backtest.spec_manifest import (
    REQUIRED_BACKTEST_SOURCES,
    Phase6SpecificationBinding,
)


class Phase6SpecBundleError(RuntimeError):
    """Raised when the authoritative Phase 6 bundle fails integrity validation."""


@dataclass(frozen=True)
class Phase6SpecArtifact:
    name: str
    path: str
    sha256: str


@dataclass(frozen=True)
class Phase6SpecBundle:
    bundle_id: str
    artifacts: tuple[Phase6SpecArtifact, ...]

    def by_name(self) -> dict[str, Phase6SpecArtifact]:
        return {artifact.name: artifact for artifact in self.artifacts}

    def to_binding(self) -> Phase6SpecificationBinding:
        items = self.by_name()
        return Phase6SpecificationBinding(
            historical_backtest_specification=_ref(items[REQUIRED_BACKTEST_SOURCES[0]]),
            pit_controls_specification=_ref(items[REQUIRED_BACKTEST_SOURCES[1]]),
            corporate_action_adjustment_specification=_ref(items[REQUIRED_BACKTEST_SOURCES[2]]),
            trading_calendar_specification=_ref(items[REQUIRED_BACKTEST_SOURCES[3]]),
            benchmark_specification=_ref(items[REQUIRED_BACKTEST_SOURCES[4]]),
            golden_backtest_test_cases=_ref(items[REQUIRED_BACKTEST_SOURCES[5]]),
        )


def _ref(artifact: Phase6SpecArtifact) -> str:
    return f"{artifact.path}#sha256={artifact.sha256}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_verified_bundle(root: str | Path) -> Phase6SpecBundle:
    root = Path(root)
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        raise Phase6SpecBundleError("Phase 6 canonical bundle manifest.json is missing")

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    bundle_id = str(payload.get("bundle_id") or "").strip()
    if not bundle_id or bundle_id.upper().startswith("PENDING"):
        raise Phase6SpecBundleError("Phase 6 bundle_id is missing or still PENDING")

    raw_artifacts = payload.get("artifacts")
    if not isinstance(raw_artifacts, list):
        raise Phase6SpecBundleError("Phase 6 manifest artifacts must be a list")

    artifacts: list[Phase6SpecArtifact] = []
    seen_names: set[str] = set()
    seen_paths: set[str] = set()

    for raw in raw_artifacts:
        if not isinstance(raw, dict):
            raise Phase6SpecBundleError("Each Phase 6 artifact entry must be an object")
        name = str(raw.get("name") or "").strip()
        relative_path = str(raw.get("path") or "").strip()
        expected_sha = str(raw.get("sha256") or "").strip().lower()

        if name not in REQUIRED_BACKTEST_SOURCES:
            raise Phase6SpecBundleError(f"Unexpected Phase 6 artifact name: {name!r}")
        if name in seen_names:
            raise Phase6SpecBundleError(f"Duplicate Phase 6 artifact name: {name}")
        if not relative_path or relative_path in seen_paths:
            raise Phase6SpecBundleError(f"Missing or duplicate Phase 6 artifact path for {name}")
        if len(expected_sha) != 64 or any(c not in "0123456789abcdef" for c in expected_sha):
            raise Phase6SpecBundleError(f"Invalid SHA-256 for Phase 6 artifact: {name}")

        path = (root / relative_path).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError as exc:
            raise Phase6SpecBundleError(
                f"Phase 6 artifact path escapes canonical bundle root: {relative_path}"
            ) from exc

        if not path.is_file():
            raise Phase6SpecBundleError(f"Phase 6 artifact file is missing: {relative_path}")
        if path.stat().st_size == 0:
            raise Phase6SpecBundleError(f"Phase 6 artifact file is empty: {relative_path}")

        actual_sha = _sha256(path)
        if actual_sha != expected_sha:
            raise Phase6SpecBundleError(
                f"Phase 6 artifact hash mismatch for {name}: "
                f"expected {expected_sha}, got {actual_sha}"
            )

        artifacts.append(
            Phase6SpecArtifact(name=name, path=relative_path, sha256=actual_sha)
        )
        seen_names.add(name)
        seen_paths.add(relative_path)

    missing = [name for name in REQUIRED_BACKTEST_SOURCES if name not in seen_names]
    if missing:
        raise Phase6SpecBundleError(
            "Phase 6 canonical bundle is incomplete; missing: " + "; ".join(missing)
        )
    if len(artifacts) != len(REQUIRED_BACKTEST_SOURCES):
        raise Phase6SpecBundleError("Phase 6 canonical bundle must contain exactly six artifacts")

    return Phase6SpecBundle(bundle_id=bundle_id, artifacts=tuple(artifacts))
