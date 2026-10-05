from __future__ import annotations

import argparse
from pathlib import Path

from app.bootstrap import AppContainer


def doctor(root: Path) -> int:
    app = AppContainer(root)
    app.initialize()
    print(f"APP: {app.app_config.app_name}")
    print(f"MARKET: {app.app_config.market}")
    print(f"PIT: {'STRICT' if app.app_config.strict_pit else 'OFF'}")
    print(f"MOCK DATA: {'FORBIDDEN' if not app.app_config.allow_mock_data else 'ENABLED'}")
    print(f"V1.2: {app.v12_config.status}")
    print(f"V1.4: {app.v14_config.status}")
    print(f"SQLite: {app.sqlite.db_path}")
    app.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="S15.3 Research Terminal")
    parser.add_argument("--doctor", action="store_true", help="Validate Phase 0 architecture")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if args.doctor:
        return doctor(root)
    print("UI NOT IMPLEMENTED — Phase 9")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
