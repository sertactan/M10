from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path


class ReleaseVersionMismatch(RuntimeError):
    pass


def read_versions(root: Path) -> dict[str, str]:
    canonical = (root / "config" / "RELEASE_VERSION.txt").read_text(encoding="utf-8").strip()
    if not canonical:
        raise ReleaseVersionMismatch("config/RELEASE_VERSION.txt is empty")

    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    package = str(pyproject["project"]["version"]).strip()

    installer_text = (root / "packaging" / "windows" / "S153ResearchTerminal.iss").read_text(
        encoding="utf-8"
    )
    match = re.search(r"(?m)^AppVersion=(.+?)\s*$", installer_text)
    if match is None:
        raise ReleaseVersionMismatch("Inno Setup AppVersion is missing")
    installer = match.group(1).strip()

    return {
        "release": canonical,
        "package": package,
        "installer": installer,
    }


def require_aligned(root: Path) -> dict[str, str]:
    versions = read_versions(root)
    values = set(versions.values())
    if len(values) != 1:
        rendered = ", ".join(f"{key}={value}" for key, value in versions.items())
        raise ReleaseVersionMismatch("release versions are not aligned: " + rendered)
    return versions


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify canonical release-version alignment")
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()

    versions = require_aligned(args.root.resolve())
    version = versions["release"]
    print(f"RELEASE VERSION: {version}")
    print("VERSION ALIGNMENT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
