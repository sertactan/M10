from __future__ import annotations

"""Phase16: verify & restore immutable SQLite snapshots without overwriting live DB.

Recovery is local-first. Cloud transport must use an independently configured
rclone crypt remote (see scripts/sync_learning_backup.py). Never commit
backups or credentials to M10's public GitHub repository.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
from uuid import uuid4


def sha256_file(path: Path) -> str:
    digest=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024),b""):
            digest.update(block)
    return digest.hexdigest()


def read_manifest(manifest_path: Path) -> dict:
    manifest=json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if not isinstance(manifest,dict):
        raise ValueError("Backup manifest is not a JSON object")
    name=manifest.get("database_file")
    if (not isinstance(name,str) or name in ("",".","..")
        or Path(name).name!=name or "/" in name or "\\" in name
        or not name.endswith(".sqlite3")):
        raise ValueError("Unsafe or missing manifest database filename")
    if manifest.get("engine")!="MERIDYEN_LEARNING_V2" or manifest.get("integrity")!="ok":
        raise ValueError("Manifest is not a verified Learning V2 snapshot")
    digest=manifest.get("sha256")
    if not isinstance(digest,str) or len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("Manifest SHA-256 is missing or malformed")
    return manifest


def verify_snapshot(snapshot: Path, manifest: dict) -> dict:
    source=Path(snapshot)
    if not source.is_file():
        raise ValueError("Snapshot database missing")
    if sha256_file(source)!=manifest["sha256"]:
        raise ValueError("Snapshot SHA-256 mismatch")
    conn=sqlite3.connect(source.resolve().as_uri()+"?mode=ro",uri=True)
    try:
        check=conn.execute("PRAGMA integrity_check").fetchone()
        if not check or check[0]!="ok":
            raise ValueError("Restored SQLite integrity_check failed")
        names={x[0] for x in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        required={"learning_v2_sources","learning_v2_outcomes","learning_v2_feedback"}
        if not required.issubset(names):
            raise ValueError("Snapshot lacks baseline Learning V2 schema")
    finally:
        conn.close()
    return {"status":"SNAPSHOT_VALID","sha256":manifest["sha256"],
            "bytes":source.stat().st_size,"sqlite_integrity":"ok"}


def restore_snapshot(manifest_file: Path, destination: Path, *, snapshot: Path | None=None) -> dict:
    """Restore to a NEW local path only; refuses existing databases.

    A unique staging file is integrity-checked, then linked to destination
    exclusively so recovery never silently replaces a running SQLite DB.
    """
    manifest_path=Path(manifest_file)
    manifest=read_manifest(manifest_path)
    source=Path(snapshot) if snapshot else manifest_path.parent/manifest["database_file"]
    verify_snapshot(source,manifest)
    destination=Path(destination)
    if destination.resolve()==source.resolve():
        raise ValueError("Refusing in-place restore")
    if destination.exists():
        raise ValueError("Restore destination already exists; overwrite forbidden")
    destination.parent.mkdir(parents=True,exist_ok=True)
    temp=destination.parent/f".{destination.name}.restore-{uuid4().hex}.tmp"
    try:
        with source.open("rb") as reader, temp.open("xb") as writer:
            shutil.copyfileobj(reader,writer,1024*1024)
            writer.flush()
            os.fsync(writer.fileno())
        # Check both contents and full SQLite integrity before any publication.
        verified=verify_snapshot(temp,manifest)
        try:
            os.link(temp,destination)
        except FileExistsError as exc:
            raise ValueError("Restore destination became occupied") from exc
        if os.name!="nt":
            destination.chmod(0o600)
        return {"status":"RESTORED_NEW_DB_ONLY","destination":str(destination),
                "manifest_sha256":verified["sha256"],"sqlite_integrity":"ok",
                "original_untouched":True}
    finally:
        temp.unlink(missing_ok=True)
