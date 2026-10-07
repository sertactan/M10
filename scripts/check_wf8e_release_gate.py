from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from core.runtime.wf8e_release import build_wf8e_release_evidence


def main() -> int:
    parser=argparse.ArgumentParser(description="WF8-E final Windows/runtime release gate")
    parser.add_argument("--root",default=".")
    parser.add_argument("--packaged-root",required=True)
    parser.add_argument("--installer",required=True)
    parser.add_argument("--sha-file",required=True)
    parser.add_argument("--commit",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()

    evidence=build_wf8e_release_evidence(
        root=Path(args.root).resolve(),
        packaged_root=Path(args.packaged_root).resolve(),
        installer_path=Path(args.installer).resolve(),
        sha_file=Path(args.sha_file).resolve(),
        commit=args.commit,
    )
    output=Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(
        json.dumps(asdict(evidence),indent=2,default=str),
        encoding="utf-8",
    )
    print(output.read_text(encoding="utf-8"))
    return 0 if evidence.status=="RELEASE_READY" else 2


if __name__=="__main__":
    raise SystemExit(main())
