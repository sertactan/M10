from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

from core.runtime.logging import runtime_state_dir


def writable_runtime_root(project_root: Path) -> Path:
    override = os.getenv("S153_RUNTIME_ROOT")
    if override:
        root = Path(override).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root
    if getattr(sys, "frozen", False):
        root = runtime_state_dir() / "runtime"
        root.mkdir(parents=True, exist_ok=True)
        return root
    return project_root


def resolve_runtime_path(project_root: Path, configured_path: str) -> Path:
    return writable_runtime_root(project_root) / configured_path


def verify_writable_runtime(root: Path) -> Path:
    """Fail fast when the runtime directory cannot safely persist application state."""
    root.mkdir(parents=True, exist_ok=True)
    probe = root / f".s153-write-probe-{uuid.uuid4().hex}.tmp"
    try:
        with probe.open("xb") as handle:
            handle.write(b"S153_RUNTIME_WRITE_TEST")
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise RuntimeError(
            f"Runtime directory is not writable: {root}: {exc}"
        ) from exc
    finally:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
    return root
