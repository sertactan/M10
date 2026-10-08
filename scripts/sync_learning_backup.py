from __future__ import annotations

"""Manually upload an *encrypted rclone crypt remote* SQLite backup.

Never upload a live database. No credentials are saved here.
Default is inspection-only; remote upload needs --execute and explicit
--confirm-crypt-remote, with rclone already configured by the account owner.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def prepare(manifest_file: Path, remote: str):
    manifest=json.loads(manifest_file.read_text(encoding="utf-8"))
    database=manifest_file.parent/manifest["database_file"]
    if not database.is_file():
        raise ValueError("snapshot database file missing")
    actual=hashlib.sha256(database.read_bytes()).hexdigest()
    if actual!=manifest.get("sha256"):
        raise ValueError("backup checksum mismatch; upload blocked")
    if manifest.get("integrity")!="ok":
        raise ValueError("backup integrity not established")
    if ":" not in remote or remote.startswith(":") or ".." in remote:
        raise ValueError("remote must be an explicitly configured rclone crypt name, e.g. meridyen_crypt:")
    target=remote.rstrip("/")+"/Database_Backups/Encrypted/"+database.name
    return database,target


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",required=True,type=Path)
    p.add_argument("--remote-crypt",required=True,
                   help="Owner-configured rclone crypt remote (not plain Drive)")
    p.add_argument("--execute",action="store_true")
    p.add_argument("--confirm-crypt-remote",action="store_true")
    args=p.parse_args()
    try:
        source,target=prepare(args.manifest,args.remote_crypt)
        if not args.execute:
            print(json.dumps({"status":"DRY_RUN_NO_UPLOAD","source":str(source),
                              "destination":target,"encrypted_remote_claim":"NOT_VERIFIED"}))
            return
        if not args.confirm_crypt_remote:
            raise ValueError("use --confirm-crypt-remote only after verifying rclone remote type is crypt")
        # '--immutable' prevents accidental overwrite of cloud backup versions.
        subprocess.run(["rclone","copyto",str(source),target,"--immutable"],check=True)
        print(json.dumps({"status":"UPLOADED_VIA_RCLONE_CRYPT","destination":target,
                          "remote_crypt_type":"USER_ATTESTED_NOT_INDEPENDENTLY_VALIDATED"}))
    except (ValueError,OSError,subprocess.CalledProcessError) as exc:
        p.exit(2,"BACKUP_UPLOAD_BLOCKED: "+str(exc)+"\n")


if __name__=="__main__":
    main()
