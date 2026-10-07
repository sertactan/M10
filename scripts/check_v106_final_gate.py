from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


class FinalProductionBlocked(RuntimeError):
    pass


def _git_changed_paths(code_identity: str, current_commit: str) -> list[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{code_identity}..{current_commit}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise FinalProductionBlocked("cannot verify code identity ancestry: " + proc.stderr.strip())
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def require_final_evidence(
    evidence_path: Path,
    *,
    current_commit: str | None = None,
) -> dict:
    if not evidence_path.exists():
        raise FinalProductionBlocked(f"WF9 production evidence missing: {evidence_path}")
    payload=json.loads(evidence_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "WF9_EVIDENCE_V1":
        raise FinalProductionBlocked("WF9 evidence schema is not WF9_EVIDENCE_V1")
    if payload.get("mode") != "FULL_EXECUTION":
        raise FinalProductionBlocked("WF9 evidence is not a full execution")
    code_identity=str(payload.get("code_identity") or "")
    if not re.fullmatch(r"[0-9a-fA-F]{40}",code_identity):
        raise FinalProductionBlocked("WF9 evidence code_identity is not a 40-character commit SHA")

    report=payload.get("report") or {}
    if report.get("status") != "COMPLETE_AND_ACTIVATED":
        raise FinalProductionBlocked(
            "WF9 status is not COMPLETE_AND_ACTIVATED: " + str(report.get("status"))
        )
    preflight=report.get("preflight") or {}
    blockers=list(preflight.get("blockers") or [])
    if blockers:
        raise FinalProductionBlocked("WF9 preflight contains blockers: " + ", ".join(blockers))
    if int(preflight.get("requested_snapshot_dates") or 0) != 144:
        raise FinalProductionBlocked("WF9 evidence does not contain 144 requested snapshots")
    if int(preflight.get("exact_pit_dates") or 0) != 144:
        raise FinalProductionBlocked("WF9 evidence does not contain 144 exact PIT snapshots")
    if int(preflight.get("total_price_covered") or 0) <= 0:
        raise FinalProductionBlocked("WF9 evidence has no canonical adjusted price coverage")
    for key in (
        "wf5_run_id","wf6_run_id","wf7_run_id","hardening_id","manifest_id","activation_id"
    ):
        if not report.get(key):
            raise FinalProductionBlocked(f"WF9 evidence missing {key}")

    if current_commit:
        allowed={
            "release_evidence/WF9_PRODUCTION_EVIDENCE.json",
            "config/WF8_PRODUCTION_RELEASE_MARKER.txt",
        }
        changed=_git_changed_paths(code_identity,current_commit)
        forbidden=[path for path in changed if path not in allowed]
        if forbidden:
            raise FinalProductionBlocked(
                "runtime code changed after WF9 evidence: " + ", ".join(forbidden)
            )
    return payload


def main() -> int:
    parser=argparse.ArgumentParser(description="Fail-closed v1.0.6 Final Production gate")
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("release_evidence/WF9_PRODUCTION_EVIDENCE.json"),
    )
    parser.add_argument("--current-commit")
    args=parser.parse_args()
    payload=require_final_evidence(args.evidence,current_commit=args.current_commit)
    print("WF9 FINAL EVIDENCE: PASS")
    print("CODE IDENTITY: " + str(payload["code_identity"]))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
