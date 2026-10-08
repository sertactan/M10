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
    # Store both the immutable snapshot and its source manifest, so full
    # cloud disaster recovery works even if the local drive is destroyed.
    manifest_target=remote+REMOTE_PREFIX+"/"+Path(manifest_file).name
    _run(["rclone","copyto",str(source),target,"--immutable"])
    _run(["rclone","copyto",str(manifest_file),manifest_target,"--immutable"])
    with TemporaryDirectory(prefix="m16-remote-proof-") as temp:
        fetched=Path(temp)/manifest["database_file"]
        manifest_copy=Path(temp)/Path(manifest_file).name
        _run(["rclone","copyto",target,str(fetched)])
        _run(["rclone","copyto",manifest_target,str(manifest_copy)])
        if manifest_copy.read_bytes()!=Path(manifest_file).read_bytes():
            raise ValueError("Cloud manifest roundtrip does not match local manifest")
        verified=verify_snapshot(fetched,manifest)
    return {"status":"CLOUD_ROUNDTRIP_VERIFIED","destination":target,
            "manifest_destination":manifest_target,
            "sha256":verified["sha256"],"remote_type":"crypt",
            "remote_content_verified":True,"remote_manifest_verified":True,
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


def recover_from_cloud_manifest(remote: str, manifest_name: str, destination: Path):
    """Recover using ONLY a remote manifest name, no surviving local backup.

    The rclone crypt remote and configured encryption password are still
    required. The manifest and DB are read over the authenticated crypt
    transport into a private temporary working directory and verified.
    """
    import re
    if not re.fullmatch(r"meridyen-learning-v2-[A-Za-z0-9_-]+\.manifest\.json",manifest_name):
        raise ValueError("Unsafe cloud manifest name")
    validate_crypt_remote(remote)
    remote_manifest=remote+REMOTE_PREFIX+"/"+manifest_name
    with TemporaryDirectory(prefix="m16-disaster-restore-") as work:
        local_manifest=Path(work)/manifest_name
        _run(["rclone","copyto",remote_manifest,str(local_manifest)])
        data=read_manifest(local_manifest)
        if Path(data["database_file"]).with_suffix(".manifest.json").name!=manifest_name:
            raise ValueError("Manifest name and snapshot name mismatch")
        cloud_db=remote+REMOTE_PREFIX+"/"+data["database_file"]
        local_db=Path(work)/data["database_file"]
        _run(["rclone","copyto",cloud_db,str(local_db)])
        return restore_snapshot(local_manifest,destination,snapshot=local_db)


def prepare_for_remote(manifest_file: Path, remote: str):
    # Cloud restore does not require local snapshot, only trusted saved manifest.
    manifest=read_manifest(manifest_file)
    if not REMOTE_NAME.fullmatch(remote):
        raise ValueError("Malformed remote")
    return manifest,remote+REMOTE_PREFIX+"/"+manifest["database_file"]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",type=Path)
    p.add_argument("--remote-crypt",required=True)
    p.add_argument("--execute",action="store_true",help="Without this, do NOT upload/download")
    p.add_argument("--confirm-crypt-remote",action="store_true",
                   help="User authorizes checking rclone crypt configuration")
    p.add_argument("--restore-to",type=Path,
                   help="Recover cloud snapshot to a NEW file path; never overwrite")
    p.add_argument("--cloud-manifest-name",
                   help="Disaster recovery: remote manifest name; local --manifest need not exist")
    args=p.parse_args()
    try:
        if args.restore_to:
            if args.cloud_manifest_name:
                if not args.execute:
                    result={"status":"RESTORE_DRY_RUN","cloud_manifest":args.cloud_manifest_name,
                            "destination":str(args.restore_to),"no_files_written":True}
                else:
                    if not args.confirm_crypt_remote:
                        raise ValueError("Explicit --confirm-crypt-remote required")
                    result=recover_from_cloud_manifest(args.remote_crypt,args.cloud_manifest_name,args.restore_to)
                print(json.dumps(result,indent=2,ensure_ascii=False))
                return
            if args.manifest is None:
                raise ValueError("--manifest or --cloud-manifest-name is required")
            manifest,target=prepare_for_remote(args.manifest,args.remote_crypt)
            if not args.execute:
                result={"status":"RESTORE_DRY_RUN","remote_object":target,
                        "destination":str(args.restore_to),"no_files_written":True}
            else:
                if not args.confirm_crypt_remote:
                    raise ValueError("Explicit --confirm-crypt-remote required")
                result=download_verified(args.manifest,args.remote_crypt,args.restore_to)
        else:
            if args.manifest is None:
                raise ValueError("Upload requires --manifest")
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
