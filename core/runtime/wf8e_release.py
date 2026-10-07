from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from core.runtime.readiness import check_release_readiness


WF8E_RELEASE_GATE_VERSION = "WF8E_RELEASE_GATE_V1_2026-10-07"

WF8_REQUIRED_TABLES = (
    "wf5_replay_runs",
    "wf6_walk_forward_runs",
    "wf7_validation_runs",
    "wf8_hardening_runs",
    "wf8_reproducibility_manifests",
    "wf8_production_activations",
    "wf8_activation_events",
)

WF8_REQUIRED_HIDDENIMPORTS = (
    "core.forecast.wf7_validated_provider",
    "core.backtest.wf8_hardening",
    "core.backtest.wf8_reproducibility",
    "core.backtest.wf8_activation",
)

WF8_REQUIRED_WINDOWS_STEPS = (
    "Clean-install offline first-run smoke test",
    "Corrupt database recovery smoke test",
    "Upgrade migration smoke test",
    "WF8-E final release gate",
)


@dataclass(frozen=True)
class WF8ECheck:
    name: str
    passed: bool
    evidence: str


@dataclass(frozen=True)
class WF8EReleaseEvidence:
    gate_version: str
    commit: str
    status: str
    installer_sha256: str | None
    checks: tuple[WF8ECheck, ...]
    evidence_hash: str


def _stable_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_file(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_declared_sha(path: Path) -> str | None:
    if not path.exists():
        return None
    text=path.read_text(encoding="utf-8",errors="replace")
    match=re.search(r"Hash\s*:\s*([0-9A-Fa-f]{64})",text)
    if match:
        return match.group(1).lower()
    compact=re.search(r"\b([0-9A-Fa-f]{64})\b",text)
    return compact.group(1).lower() if compact else None


def _contains_all(text: str, values: Iterable[str]) -> tuple[bool,list[str]]:
    missing=[value for value in values if value not in text]
    return (not missing,missing)


def build_wf8e_release_evidence(
    *,
    root: Path,
    packaged_root: Path,
    installer_path: Path,
    sha_file: Path,
    commit: str,
) -> WF8EReleaseEvidence:
    checks: list[WF8ECheck]=[]

    readiness=check_release_readiness(root)
    checks.append(WF8ECheck(
        "source_release_readiness",
        readiness.ready,
        "ready" if readiness.ready else ",".join(readiness.blockers),
    ))

    schema_source=(root/"data/database/schema.sql")
    source_schema=schema_source.read_text(encoding="utf-8") if schema_source.exists() else ""
    ok,missing=_contains_all(source_schema,WF8_REQUIRED_TABLES)
    checks.append(WF8ECheck(
        "source_wf8_schema_contract",
        ok,
        "all WF8 tables present" if ok else "missing="+",".join(missing),
    ))

    spec_path=root/"packaging/windows/S153ResearchTerminal.spec"
    spec_text=spec_path.read_text(encoding="utf-8") if spec_path.exists() else ""
    ok,missing=_contains_all(spec_text,WF8_REQUIRED_HIDDENIMPORTS)
    checks.append(WF8ECheck(
        "pyinstaller_wf8_hiddenimports",
        ok,
        "all WF8 hiddenimports present" if ok else "missing="+",".join(missing),
    ))

    workflow_path=root/".github/workflows/windows-build.yml"
    workflow=workflow_path.read_text(encoding="utf-8") if workflow_path.exists() else ""
    ok,missing=_contains_all(workflow,WF8_REQUIRED_WINDOWS_STEPS)
    if "--doctor" not in workflow:
        missing.append("--doctor")
        ok=False
    checks.append(WF8ECheck(
        "windows_smoke_contract",
        ok,
        "required Windows smoke/recovery/migration/final-gate steps present"
        if ok else "missing="+",".join(missing),
    ))

    packaged_schema=packaged_root/"data/database/schema.sql"
    packaged_text=(
        packaged_schema.read_text(encoding="utf-8")
        if packaged_schema.exists() else ""
    )
    ok,missing=_contains_all(packaged_text,WF8_REQUIRED_TABLES)
    checks.append(WF8ECheck(
        "packaged_wf8_schema",
        ok,
        str(packaged_schema) if ok else "missing="+",".join(missing),
    ))

    installer_exists=installer_path.exists() and installer_path.stat().st_size>0
    checks.append(WF8ECheck(
        "windows_installer_exists",
        installer_exists,
        str(installer_path),
    ))

    declared=_extract_declared_sha(sha_file)
    actual=_sha256_file(installer_path) if installer_exists else None
    sha_ok=bool(declared and actual and declared==actual)
    checks.append(WF8ECheck(
        "installer_sha256_verified",
        sha_ok,
        f"declared={declared};actual={actual}",
    ))

    commit_ok=bool(commit.strip()) and commit.strip().lower() not in {"unknown","none"}
    checks.append(WF8ECheck(
        "release_commit_identity",
        commit_ok,
        commit,
    ))

    status="RELEASE_READY" if all(item.passed for item in checks) else "RELEASE_BLOCKED"
    payload={
        "gate_version":WF8E_RELEASE_GATE_VERSION,
        "commit":commit,
        "status":status,
        "installer_sha256":actual,
        "checks":[asdict(item) for item in checks],
    }
    evidence_hash=hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()
    return WF8EReleaseEvidence(
        gate_version=WF8E_RELEASE_GATE_VERSION,
        commit=commit,
        status=status,
        installer_sha256=actual,
        checks=tuple(checks),
        evidence_hash=evidence_hash,
    )
