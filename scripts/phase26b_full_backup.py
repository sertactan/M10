from __future__ import annotations

"""Create-only snapshot of M10 user application state, excluding prior snapshots."""

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.phase26a_verified_backup import inventory


EXCLUDED_RUNTIME = {"phase26a", "phase26b"}


def collect_app_state(app_root: Path, original_price: Path) -> dict[str, Path]:
    app_root = app_root.resolve()
    if not app_root.is_dir() or app_root.is_symlink():
        raise ValueError("Application state directory unavailable")
    files: dict[str, Path] = {"external/original_price.csv": original_price}
    for top in ("runtime", "logs", "backups"):
        directory = app_root / top
        if not directory.is_dir() or directory.is_symlink():
            raise ValueError(f"Application state directory missing: {top}")
        for root, dirs, names in os.walk(directory, followlinks=False):
            parent = Path(root)
            if top == "runtime" and parent == directory:
                dirs[:] = [d for d in dirs if d not in EXCLUDED_RUNTIME]
            for name in names:
                source = parent / name
                if source.is_symlink() or getattr(source, "is_junction", lambda: False)():
                    raise ValueError(f"Linked application state file: {source}")
                if source.is_file():
                    files[f"app_state/{source.relative_to(app_root).as_posix()}"] = source
            for name in dirs:
                source = parent / name
                if source.is_symlink() or getattr(source, "is_junction", lambda: False)():
                    raise ValueError(f"Linked application state directory: {source}")
    settings = app_root / "settings.json"
    if not settings.is_file() or settings.is_symlink():
        raise ValueError("Application settings unavailable")
    files["app_state/settings.json"] = settings
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-root", type=Path, required=True)
    parser.add_argument("--price-csv", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    db = args.app_root / "runtime" / "data" / "runtime" / "operational.db"
    files = collect_app_state(args.app_root, args.price_csv)
    files.pop("app_state/runtime/data/runtime/operational.db", None)
    result = inventory(db, files, args.out)
    print(json.dumps({"status": result["status"], "entries": len(result["entries"]),
                      "bytes": sum(row["bytes"] for row in result["entries"]),
                      "manifest": str(args.out / "manifest.json")}, sort_keys=True))


if __name__ == "__main__":
    main()