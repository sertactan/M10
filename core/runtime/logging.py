from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def runtime_state_dir(app_name: str = "S153ResearchTerminal") -> Path:
    local = os.getenv("LOCALAPPDATA")
    if local:
        root = Path(local) / app_name
    else:
        root = Path.home() / ".local" / "state" / app_name
    root.mkdir(parents=True, exist_ok=True)
    return root


def configure_logging(
    *,
    app_name: str = "S153ResearchTerminal",
    level: int = logging.INFO,
) -> Path:
    log_dir = runtime_state_dir(app_name) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "app.log"

    root = logging.getLogger()
    root.setLevel(level)
    if not any(getattr(handler, "_s153_handler", False) for handler in root.handlers):
        handler = RotatingFileHandler(
            path,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        handler._s153_handler = True  # type: ignore[attr-defined]
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s"
            )
        )
        root.addHandler(handler)
    return path
