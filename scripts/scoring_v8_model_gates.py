"""Read-only V8 evidence-gap audit over the inherited sealed V7 report.

Without --phase27 and --phase28 the checksum and baseline contract are checked,
but the prior source-replay validator is not invoked; that distinction is in
the result. This command fetches no data and does not update score databases.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v8_model_gates import audit_v7_report, load_sealed_v7


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True, help="Original sealed V7 report.json")
    parser.add_argument("--phase27", type=Path, help="Source-replay staging database (optional pair)")
    parser.add_argument("--phase28", type=Path, help="Source-replay staging database (optional pair)")
    parser.add_argument("--out", type=Path, help="A NEW isolated private .json output path")
    args = parser.parse_args(argv)
    report, digest, level = load_sealed_v7(args.report, phase27=args.phase27,
                                           phase28=args.phase28)
    audit = audit_v7_report(report, report_sha256=digest, verification=level)
    if args.out is not None:
        path = args.out
        if path.suffix.lower() != ".json" or path.is_symlink() or path.exists():
            raise ValueError("output must be a new isolated .json path")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as f:
            json.dump(audit, f, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            f.write("\n")
    print(json.dumps({k: v for k, v in audit.items()
                      if k not in ("stocks",)}, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
