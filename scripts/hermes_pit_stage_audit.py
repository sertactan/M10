"""Verify existing private Phase25Q stage without modifying it."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.hermes_team.pit_stage import audit_stage


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-dir", type=Path, required=True)
    value = audit_stage(parser.parse_args().stage_dir)
    print(json.dumps(value, indent=2, ensure_ascii=False))
    return 0 if value["status"] == "SOURCE_STAGING_VERIFIED_RESEARCH_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
