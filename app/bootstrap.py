from __future__ import annotations

from pathlib import Path

from core.config.env import load_local_env
from core.config.loader import load_yaml
from core.config.models import ApplicationConfig, ModelConfig
from data.database.sqlite_store import SQLiteStore
from core.runtime.paths import writable_runtime_root


class AppContainer:
    def __init__(self, root: Path) -> None:
        self.root = root
        load_local_env(root / ".env")
        self.app_config = load_yaml(root / "config" / "app.yaml", ApplicationConfig)
        self.v12_config = load_yaml(root / "config" / "s153_v12.yaml", ModelConfig)
        self.v14_config = load_yaml(root / "config" / "s153_v14.yaml", ModelConfig)
        self.runtime_root = writable_runtime_root(root)
        self.sqlite = SQLiteStore(self.runtime_root / self.app_config.database.sqlite_path)

    def initialize(self) -> None:
        if self.app_config.allow_mock_data:
            raise RuntimeError("Production bootstrap refuses allow_mock_data=true")
        if not self.app_config.strict_pit:
            raise RuntimeError("Production bootstrap requires strict_pit=true")
        self.sqlite.initialize()

    def resolve_data_path(self, configured_path: str) -> Path:
        return self.runtime_root / configured_path

    def close(self) -> None:
        self.sqlite.close()
