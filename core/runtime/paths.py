from __future__ import annotations

import os
import sys
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
