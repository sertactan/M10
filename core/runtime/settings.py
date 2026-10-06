from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.runtime.logging import runtime_state_dir


class RuntimeSettings:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (runtime_state_dir() / "settings.json")

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def save(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(value, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temp.replace(self.path)
