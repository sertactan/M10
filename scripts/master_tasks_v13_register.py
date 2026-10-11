"""Validate the V13 register against the sealed V12 gate inventory."""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.master_tasks_v13_register import validate_v13

root = Path(__file__).resolve().parents[1]
print(json.dumps(validate_v13(root / "docs/MASTER_TASKS_V13_REGISTER.json",
                              root / "docs/MASTER_TASKS_V12_REGISTER.json"), sort_keys=True))
