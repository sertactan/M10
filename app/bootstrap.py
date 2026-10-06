from __future__ import annotations

import sys
from pathlib import Path

from core.config.env import load_local_env
from core.config.loader import load_yaml
from core.config.models import ApplicationConfig, ModelConfig
from data.database.sqlite_store import SQLiteStore
from data.seeds.loader import bootstrap_bundled_jp_tr_hk_seed, bootstrap_bundled_us_seed
from core.runtime.paths import verify_writable_runtime, writable_runtime_root


class AppContainer:
    def __init__(self, root: Path) -> None:
        self.root = root
        load_local_env(root / ".env")
        self.app_config = load_yaml(root / "config" / "app.yaml", ApplicationConfig)
        self.v12_config = load_yaml(root / "config" / "s153_v12.yaml", ModelConfig)
        self.v14_config = load_yaml(root / "config" / "s153_v14.yaml", ModelConfig)
        self.v141_config = load_yaml(root / "config" / "s153_v141.yaml", ModelConfig)
        self.runtime_root = writable_runtime_root(root)
        self.sqlite = SQLiteStore(self.runtime_root / self.app_config.database.sqlite_path)
        self.bootstrap_counts: dict[str, int] = {}

    def initialize(self) -> None:
        if self.app_config.allow_mock_data:
            raise RuntimeError("Production bootstrap refuses allow_mock_data=true")
        if not self.app_config.strict_pit:
            raise RuntimeError("Production bootstrap requires strict_pit=true")
        verify_writable_runtime(self.runtime_root)
        self.sqlite.initialize()
        bootstrap_bundled_us_seed(self.sqlite)
        bootstrap_bundled_jp_tr_hk_seed(self.sqlite)

        rows = self.sqlite.connection.execute(
            """
            SELECT market,COUNT(*) AS n
            FROM security_master
            GROUP BY market
            """
        ).fetchall()
        self.bootstrap_counts = {
            str(row["market"]): int(row["n"])
            for row in rows
        }

        # A frozen/installed build is required to be useful without network
        # access on first launch. Development checkouts may intentionally omit
        # generated seed CSVs, but the packaged application may not.
        if getattr(sys, "frozen", False) and self.bootstrap_counts.get("US", 0) < 1000:
            raise RuntimeError(
                "Packaged offline US security seed is missing or incomplete"
            )

    def resolve_data_path(self, configured_path: str) -> Path:
        return self.runtime_root / configured_path

    def close(self) -> None:
        self.sqlite.close()
