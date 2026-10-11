"""INOD original SEC FY2025 S8 extension: private receipt creation/replay."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v10_extension_s8 import PARENT, audit_extension, seal_bytes, verify_extension_receipt


def main(argv=None) -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    group = cli.add_mutually_exclusive_group(required=True)
    group.add_argument("--out", type=Path, help="New private extension_s8 JSON receipt")
    group.add_argument("--verify", type=Path, help="Recompute and verify private receipt")
    args = cli.parse_args(argv)
    target = (args.out or args.verify).resolve()
    if target.suffix.lower() != ".json" or PARENT.resolve() not in target.parents:
        raise ValueError("RECEIPT_MUST_BE_PRIVATE_EXTENSION_S8_JSON")
    if args.verify is not None:
        report = verify_extension_receipt(target)
    else:
        side = Path(str(target) + ".sha256")
        if target.exists() or side.exists() or target.is_symlink() or side.is_symlink():
            raise FileExistsError("WILL_NOT_REPLACE_EXISTING_EVIDENCE")
        report = audit_extension()
        target.parent.mkdir(parents=True, exist_ok=True)
        contents = (json.dumps(report, indent=2, ensure_ascii=False,
                               sort_keys=True, allow_nan=False) + "\n").encode("utf8")
        with target.open("xb") as f:
            f.write(contents)
        with side.open("x", encoding="ascii") as f:
            f.write(seal_bytes(contents) + "\n")
        verify_extension_receipt(target)
    print(json.dumps({
        "status": "SOURCE_REPLAY_PASS",
        "receipt": str(target),
        "receipt_sha256": seal_bytes(target.read_bytes()),
        "conditional_altman_Z_double_prime": report["conditional_Altman"][
            "Z_double_prime_if_X3_is_operating_profit_and_X4_all_equity"],
        "new_real_FULL_S8_scores": report["new_real_FULL_S8_scores"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
