from __future__ import annotations

import hashlib
from pathlib import Path

from core.runtime.wf8e_release import (
    WF8E_RELEASE_GATE_VERSION,
    build_wf8e_release_evidence,
)


def _make_package(tmp_path: Path, root: Path):
    packaged=tmp_path/"_internal"
    schema=packaged/"data/database/schema.sql"
    schema.parent.mkdir(parents=True,exist_ok=True)
    schema.write_text(
        (root/"data/database/schema.sql").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    installer=tmp_path/"Setup.exe"
    installer.write_bytes(b"installer-bytes")
    digest=hashlib.sha256(installer.read_bytes()).hexdigest()
    sha=tmp_path/"SHA256.txt"
    sha.write_text(f"Algorithm : SHA256\nHash : {digest}\nPath : {installer}\n",encoding="utf-8")
    return packaged,installer,sha


def test_wf8e_release_gate_passes_current_source_contract(tmp_path: Path) -> None:
    root=Path(__file__).resolve().parents[1]
    packaged,installer,sha=_make_package(tmp_path,root)
    evidence=build_wf8e_release_evidence(
        root=root,
        packaged_root=packaged,
        installer_path=installer,
        sha_file=sha,
        commit="abc123",
    )
    assert evidence.gate_version==WF8E_RELEASE_GATE_VERSION
    assert evidence.status=="RELEASE_READY"
    assert all(check.passed for check in evidence.checks)


def test_wf8e_release_gate_blocks_sha_mismatch(tmp_path: Path) -> None:
    root=Path(__file__).resolve().parents[1]
    packaged,installer,sha=_make_package(tmp_path,root)
    sha.write_text("Hash : "+"0"*64,encoding="utf-8")
    evidence=build_wf8e_release_evidence(
        root=root,
        packaged_root=packaged,
        installer_path=installer,
        sha_file=sha,
        commit="abc123",
    )
    assert evidence.status=="RELEASE_BLOCKED"
    check={item.name:item for item in evidence.checks}
    assert check["installer_sha256_verified"].passed is False
