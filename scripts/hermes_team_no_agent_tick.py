"""Hermes --no-agent cron target, copied into private HERMES_HOME/scripts.

It only executes an already-enqueued M10 deterministic research audit, never
creates tasks, calls any LLM, sends Telegram messages, or trades.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def main():
    current = Path(__file__).resolve()
    # Source checkout or installed in E:/M10/data/runtime/hermes_v2/hermes_profile/scripts.
    if current.parent.name == "scripts" and current.parent.parent.name == "hermes_profile":
        root = current.parents[5]
    else:
        root = current.parents[1]
    interpreter = root / ".venv" / "Scripts" / "python.exe"
    if not interpreter.is_file() or not (root / "core" / "hermes_team" / "tasks.py").is_file():
        print("MERIDYEN_CRON_BLOCKED: M10_RUNTIME_UNAVAILABLE")
        return 2
    ledger = root / "data" / "runtime" / "hermes_v2" / "scheduled_tasks.sqlite3"
    try:
        run = subprocess.run(
            [str(interpreter), "-m", "scripts.hermes_team_tasks",
             "--db", str(ledger), "tick"],
            cwd=root, text=True, capture_output=True, timeout=120, check=False,
        )
        response = json.loads(run.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        print("MERIDYEN_CRON_BLOCKED: LOCAL_SUBPROCESS_FAILED")
        return 2
    if run.returncode != 0:
        print("MERIDYEN_CRON_BLOCKED: TASK_GATE_FAILED")
        return 2
    if response.get("status") == "NO_PENDING_WORK":
        return 0  # Silent Hermes cron tick, no notifications
    # Never print raw evidence/files/credentials in unattended cron output.
    print(json.dumps({"job_id": response.get("job_id"),
                      "status": response.get("status"),
                      "llm_called": False, "paper_only": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
