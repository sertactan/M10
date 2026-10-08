from __future__ import annotations

"""Phase16: opt-in encrypted rclone backup transport with restore verification.

- Verifies *configured rclone type=crypt*, never exposes config secrets.
- Uploads only consistent SQLite backup snapshots (never active DB).
- Downloads a round-trip copy and checks SHA256 + SQLite integrity before
  claiming success. Existing remote objects are never overwritten.
- Requires local user's rclone authentication; no cloud sync by default.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

from core.learning_v2.recovery import read_manifest,verify_snapshot,restore_snapshot

REMOTE_NAME=re.compile(r"^[A-Za-z0-9_-]+:$")
REMOTE_PREFIX="Database_Backups/Encrypted"


def prepare(manifest_file: Path, remote: str):
    manifest=read_manifest(Path(manifest_file))
    database=Path(manifest_file).parent/manifest["database_file"]
    verify_snapshot(database,manifest)
    if not REMOTE_NAME.fullmatch(remote):
        raise ValueError("Remote must be a configured crypt name only, e.g. meridyen_crypt:")
    target=remote+REMOTE_PREFIX+"/"+database.name
    return database,target


def _run(command):
    try:
        return subprocess.run(command,check=True,capture_output=True,text=True)
    except (subprocess.CalledProcessError,OSError) as exc:
        # rclone stderr can contain remote paths, tokens or credentials.
        raise ValueError(f"rclone command failed: {command[1]}") from exc


def validate_crypt_remote(remote: str):
    if not REMOTE_NAME.fullmatch(remote):
        raise ValueError("Malformed rclone remote name")
    # Never print the returned config, which may contain secrets.
    output=_run(["rclone","config","show",remote[:-1]]).stdout
    # Only parse the isolated configured section for the requested remote.
    section=f"[{remote[:-1]}]"
    sections=re.split(r"(?m)^\[(.+?)\]\s*$",output)
    typ=None
    for i in range(1,len(sections),2):
        if "["+sections[i]+"]"==section:
            for line in sections[i+1].splitlines():
                match=re.match(r"^\s*type\s*=\s*(\w+)\s*$",line)
                if match:
                    typ=match.group(1).lower()
            break
    if typ!="crypt":
        raise ValueError("Remote is not independently confirmed as rclone type=crypt")
    return True


def upload_verified(manifest_file: Path, remote: str):
    source,target=prepare(manifest_file,remote)
    validate_crypt_remote(remote)
    manifest=read_manifest(manifest_file)
    # Immutable prevents replacing a prior cloud snapshot.
    _run(["rclone","copyto",str(source),target,"--immutable"])
    with TemporaryDirectory(prefix="m16-remote-proof-") as temp:
        fetched=Path(temp)/manifest["database_file"]
        _run(["rclone","copyto",target,str(fetched)])
        verified=verify_snapshot(fetched,manifest)
    return {"status":"CLOUD_ROUNDTRIP_VERIFIED","destination":target,
            "sha256":verified["sha256"],"remote_type":"crypt",
            "remote_content_verified":True,
            "confidentiality":"NO_SECRETS_IN_GITHUB"}


def download_verified(manifest_file: Path, remote: str, destination: Path):
    """Restore from an rclone crypt remote into a NEW local DB path only."""
    _,target=prepare_for_remote(manifest_file,remote)
    validate_crypt_remote(remote)
    manifest=read_manifest(manifest_file)
    with TemporaryDirectory(prefix="m16-remote-restore-") as temp:
        fetched=Path(temp)/manifest["database_file"]
        _run(["rclone","copyto",target,str(fetched)])
        return restore_snapshot(manifest_file,destination,snapshot=fetched)


def prepare_for_remote(manifest_file: Path, remote: str):
    # Cloud restore does not require local snapshot, only trusted saved manifest.
    manifest=read_manifest(manifest_file)
    if not REMOTE_NAME.fullmatch(remote):
        raise ValueError("Malformed remote")
    return manifest,remote+REMOTE_PREFIX+"/"+manifest["database_file"]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",required=True,type=Path)
    p.add_argument("--remote-crypt",required=True)
    p.add_argument("--execute",action="store_true",help="Without this, do NOT upload/download")
    p.add_argument("--confirm-crypt-remote",action="store_true",
                   help="User authorizes checking rclone crypt configuration")
    p.add_argument("--restore-to",type=Path,
                   help="Recover cloud snapshot to a NEW file path; never overwrite")
    args=p.parse_args()
    try:
        if args.restore_to:
            manifest,target=prepare_for_remote(args.manifest,args.remote_crypt)
            if not args.execute:
                result={"status":"RESTORE_DRY_RUN","remote_object":target,
                        "destination":str(args.restore_to),"no_files_written":True}
            else:
                if not args.confirm_crypt_remote:
                    raise ValueError("Explicit --confirm-crypt-remote required")
                result=download_verified(args.manifest,args.remote_crypt,args.restore_to)
        else:
            _,target=prepare(args.manifest,args.remote_crypt)
            if not args.execute:
                result={"status":"DRY_RUN_NO_UPLOAD","remote_object":target}
            else:
                if not args.confirm_crypt_remote:
                    raise ValueError("Explicit --confirm-crypt-remote required")
                result=upload_verified(args.manifest,args.remote_crypt)
        print(json.dumps(result,indent=2,ensure_ascii=False))
    except (ValueError,OSError,subprocess.CalledProcessError) as exc:
        p.exit(2,"BACKUP_SYNC_BLOCKED: "+str(exc)+"\n")


if __name__=="__main__":
    main()
