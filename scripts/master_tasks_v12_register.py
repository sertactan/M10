"""Read the V12 task register and fail if any DONE gate lacks evidence."""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.master_tasks_v12_register import validate_register

path = Path(__file__).resolve().parents[1] / "docs/MASTER_TASKS_V12_REGISTER.json"
print(json.dumps(validate_register(path), sort_keys=True))
