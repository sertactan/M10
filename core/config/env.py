from __future__ import annotations

import os
from pathlib import Path


def load_local_env(path: str | Path) -> None:
    """Load a simple KEY=VALUE .env file without overriding process env.

    Secrets remain local because `.env` is gitignored. This intentionally supports
    the project's local-first Settings/API-key workflow without adding another
    runtime dependency.
    """
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)
