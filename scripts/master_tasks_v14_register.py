"""Check the V14 40-gate record against V13."""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.master_tasks_v14_register import validate_v14

root = Path(__file__).resolve().parents[1]
print(json.dumps(validate_v14(root / "docs/MASTER_TASKS_V14_REGISTER.json",
                              root / "docs/MASTER_TASKS_V13_REGISTER.json"), sort_keys=True))
