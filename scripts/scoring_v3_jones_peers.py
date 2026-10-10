"""Run offline, cache-first SEC peer audit; write only a new private V3 report.

Usage (Windows): python scripts/scoring_v3_jones_peers.py

No network is used, regardless of environment SEC credentials. The official
bulk SEC Companyfacts ZIP, local universe, and captured INOD submissions are
read only. A current SIC observation is never turned into historical industry
evidence. The optional manifest must provide independently verified dated SEC
SIC evidence; it cannot be generated from current SEC Submissions SIC fields.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import zipfile

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from app.scoring_v3_jones_peers import read_universe, scan_available


def _default_runtime() -> Path:
    if not os.environ.get("LOCALAPPDATA"):
        raise ValueError("LOCALAPPDATA is unavailable")
    return Path(os.environ["LOCALAPPDATA"]) / "S153ResearchTerminal" / "runtime"


def _sha(data):
    return sha256(data).hexdigest()


def _validate_receipt(root: Path) -> tuple[datetime, dict]:
    receipt_path = root / "scoring_completion" / "sec_submission_probe" / "receipt.json"
    submissions = root / "sec_submissions" / "CIK0000903651.json"
    if any(not p.is_file() or p.is_symlink() for p in (receipt_path, submissions)):
        raise ValueError("INOD official SEC submissions receipt/cache missing")
    receipt = json.loads(receipt_path.read_text(encoding="utf8"))
    raw = submissions.read_bytes()
    digest = _sha(raw)
    if (receipt.get("cik") != "0000903651" or receipt.get("sha256") != digest
            or receipt.get("bytes") != len(raw) or receipt.get("http_status") != 200):
        raise ValueError("INOD SEC submissions receipt does not match stored bytes")
    captured = datetime.fromisoformat(receipt["checked_at"].replace("Z", "+00:00"))
    if captured.tzinfo is None:
        raise ValueError("SEC receipt missing UTC clock")
    return captured.astimezone(timezone.utc), {
        "company": "INOD", "sha256": digest, "bytes": len(raw),
        "observed_at": captured.isoformat(), "http_status": 200,
        "new_network_requests": 0,
    }


def _write_private(output: Path, report: dict, root: Path) -> None:
    score_root = (root / "scoring_completion").resolve()
    resolved = output.resolve()
    if (resolved.parent.parent != score_root
            or not resolved.parent.name.startswith("v3_jones")
            or resolved.name != "report.json"
            or output.exists() or output.is_symlink()
            or Path(str(output) + ".sha256").exists()):
        raise ValueError("Output must be a NEW runtime/scoring_completion/v3_jones*/report.json")
    # Never overwrite even if another worker created the file meanwhile.
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True,
                     allow_nan=False).encode("utf8")
    with output.open("xb") as handle:
        handle.write(raw)
    with Path(str(output) + ".sha256").open("x", encoding="ascii") as handle:
        handle.write(_sha(raw) + "\n")


def audit(runtime: Path, *, output: Path | None = None,
          dated_manifest: Path | None = None, as_of: datetime | None = None) -> dict:
    runtime = runtime.resolve()
    at = as_of if as_of is not None else datetime.now(timezone.utc)
    if at.tzinfo is None:
        raise ValueError("Timezone-aware as_of required")
    at = at.astimezone(timezone.utc)
    observed, submissions_receipt = _validate_receipt(runtime)
    universe, inventory = read_universe(runtime / "data/runtime/operational.db")
    if dated_manifest is None:
        historical = {}
        manifest = {"status": "NO_FY2025_DATED_SIC_PROVENANCE",
                    "verified_historical_industry_entries": 0}
    else:
        if not dated_manifest.is_file() or dated_manifest.is_symlink():
            raise ValueError("A local dated SEC classification manifest is required")
        raw = dated_manifest.read_bytes()
        parsed = json.loads(raw)
        manifest_entries = parsed.get("by_cik")
        if not isinstance(manifest_entries, dict):
            raise ValueError("Expected by_cik dictionary for dated SEC evidence")
        historical = {}
        for cik, row in manifest_entries.items():
            if not isinstance(row, dict) or not isinstance(row.get("header_path"), str):
                raise ValueError("Every historical SEC SIC entry requires header_path")
            if not cik.isdigit() or not 1 <= len(cik) <= 10:
                raise ValueError("Historical SEC SIC manifest contains invalid CIK")
            header_path = (dated_manifest.parent / row["header_path"]).resolve()
            if (not header_path.is_file() or header_path.is_symlink()
                    or header_path.stat().st_size > 20_000_000):
                raise ValueError("Historical SEC header file missing/unsafe/oversized")
            historical[cik.zfill(10)] = {
                "header_bytes": header_path.read_bytes(),
                "header_sha256": row.get("header_sha256"),
                "observed_at": row.get("observed_at"),
                "source_ref": row.get("source_ref"),
            }
        manifest = {"status": "USER_SUPPLIED_HISTORICAL_EVIDENCE_UNVERIFIED_BY_RUNTIME",
                    "sha256": _sha(raw), "provided_entries": len(historical)}
    archive = runtime / "bulk/sec/companyfacts.zip"
    with zipfile.ZipFile(archive) as zf:
        meta = {"archive_entries": len(zf.infolist()),
                "compressed_bytes": archive.stat().st_size,
                "archive_name": archive.name, "new_network_requests": 0}
    observation = scan_available(
        universe, archive=archive, submissions_directory=runtime / "sec_submissions",
        as_of=at, observed_at=observed, dated_classifications=historical,
    )
    report = {
        "schema": "MERIDYEN_S11_V3_PRIVATE_CACHE_AUDIT_V1",
        "generated_at": at.isoformat(), "official_source": "SEC_EDGAR_BULK_COMPANYFACTS",
        "scope": "CURRENT_RESEARCH_ONLY_NOT_HISTORICAL_PIT",
        "canonical_accepted": False, "network_requests": 0,
        "universe": inventory, "sec_bulk_zip": meta,
        "sec_submissions": submissions_receipt,
        "historical_industry": manifest, "INOD_S11": observation,
    }
    if output:
        _write_private(output, report, runtime)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runtime", type=Path, default=_default_runtime())
    ap.add_argument("--output", type=Path)
    ap.add_argument("--dated-sec-sic-manifest", type=Path)
    args = ap.parse_args(argv)
    default_name = ("v3_jones_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    output = args.output or (args.runtime / "scoring_completion" / default_name / "report.json")
    report = audit(args.runtime, output=output, dated_manifest=args.dated_sec_sic_manifest)
    result = report["INOD_S11"]
    print(json.dumps({
        "report": str(output), "universe": report["universe"]["total_security_master"],
        "SEC_companyfacts_zip_entries": report["sec_bulk_zip"]["archive_entries"],
        "INOD_companyfacts_sha256": result.get("source", {}).get("source_sha256"),
        "INOD_exact_selected_fields": len(result.get("target", {}).get("selected", [])),
        "verified_dated_peer_count": result.get("eligible_peer_count", 0),
        "S11": result.get("score"), "blockers": result.get("blockers"),
        "network_requests": 0,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
