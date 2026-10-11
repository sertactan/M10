"""Run and independently replay V8 Piotroski candidate audits, fully offline."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v8_s9_audit import PILOTS, audit_company
from app.task9_jones_cohort import SECCache, SECStop, read_sec_contact


def _checksum(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _cached_response(root: Path, url: str) -> bytes:
    key = _checksum(url.encode())
    body = root / "responses" / (key + ".bin")
    info = root / "responses" / (key + ".json")
    if not body.is_file() or not info.is_file() or body.is_symlink() or info.is_symlink():
        raise ValueError("OFFICIAL_SEC_CACHED_RESPONSE_MISSING:" + url)
    raw = body.read_bytes()
    meta = json.loads(info.read_text(encoding="utf-8"))
    if meta.get("url") != url or meta.get("sha256") != _checksum(raw) or meta.get("http_status") not in (200, 206):
        raise ValueError("SEC_CACHE_SOURCE_FINGERPRINT_CHANGED")
    return raw


def sources(runtime: Path, v6_private: Path, v8_private: Path) -> dict:
    sub_inod = runtime / "sec_submissions" / "CIK0000903651.json"
    body_inod = runtime / "scoring_completion" / "v3_filing_bodies" / "000110465926020655_inod-20251231x10k.htm"
    sub_crmd = _cached_response(v6_private / "task9_jones_eton",
        "https://data.sec.gov/submissions/CIK0001410098.json")
    body_url = ("https://www.sec.gov/Archives/edgar/data/1410098/"
                "000121390026023889/ea0278169-10k_cormedix.htm")
    crmd_body = None
    crmd_cache = v8_private / "task9_jones_v8_piotroski"
    try:
        crmd_body = _cached_response(crmd_cache, body_url)
    except ValueError as err:
        if not str(err).startswith("OFFICIAL_SEC_CACHED_RESPONSE_MISSING"):
            raise
    if not sub_inod.is_file() or not body_inod.is_file():
        raise ValueError("INOD_OFFICIAL_SEC_V3_CACHED_SOURCE_MISSING")
    return {"INOD": (sub_inod.read_bytes(), body_inod.read_bytes()),
            "CRMD": (sub_crmd, crmd_body)}


def run(archive: Path, runtime: Path, v6_private: Path, v8_private: Path) -> dict:
    filing_sources = sources(runtime, v6_private, v8_private)
    result = {}
    with zipfile.ZipFile(archive) as z:
        for ticker, cfg in PILOTS.items():
            raw = z.read("CIK" + cfg["cik"] + ".json")
            sub, body = filing_sources[ticker]
            result[ticker] = audit_company(ticker, raw, sub, filing_body=body)
    return result


def store_or_verify(receipt: Path, archive: Path, runtime: Path,
                    v6_private: Path, v8_private: Path) -> dict:
    recomputed = run(archive, runtime, v6_private, v8_private)
    serialized = (json.dumps(recomputed, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    seal = Path(str(receipt) + ".sha256")
    if receipt.exists():
        if receipt.is_symlink() or not seal.is_file() or receipt.read_bytes() != serialized or seal.read_text("ascii").strip() != _checksum(serialized):
            raise ValueError("S9_V8_OFFLINE_REPLAY_OR_SEAL_CHANGED")
    else:
        if seal.exists() or receipt.is_symlink():
            raise ValueError("S9_V8_SEAL_COLLISION")
        receipt.parent.mkdir(parents=True, exist_ok=True)
        with receipt.open("xb") as fd:
            fd.write(serialized)
        with seal.open("x", encoding="ascii") as fd:
            fd.write(_checksum(serialized) + "\n")
    return recomputed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=Path("E:/M10/.scoring_v8_private/piotroski_audit/report.json"))
    parser.add_argument("--fetch-crmd-body-once", action="store_true",
                        help="One fair-access official SEC request, never retries HTTP 403/429")
    args = parser.parse_args()
    private = Path("E:/M10/.scoring_v8_private").resolve()
    if args.receipt.resolve().parent != private / "piotroski_audit":
        raise ValueError("PRIVATE_V8_S9_REPORT_DIR_REQUIRED")
    runtime = Path(os.environ["LOCALAPPDATA"]) / "S153ResearchTerminal" / "runtime"
    if args.fetch_crmd_body_once:
        contact = read_sec_contact(Path("E:/M10/.env"))
        if not contact:
            raise ValueError("VALID_CONFIGURED_SEC_CONTACT_REQUIRED")
        client = SECCache(private / "task9_jones_v8_piotroski", contact=contact,
                          request_budget=1)
        url = ("https://www.sec.gov/Archives/edgar/data/1410098/"
               "000121390026023889/ea0278169-10k_cormedix.htm")
        try:
            body, source_meta = client.load(url, limit=25_000_000)
        except SECStop as exc:
            print(json.dumps({"CRMD_10K_status":str(exc),
                              "requests": client.requests, "no_retry": True}))
            return
        if body is None:
            print(json.dumps({"CRMD_10K_status":source_meta.get("error", "NOT_FETCHED"),
                              "requests": client.requests}))
            return
    report = store_or_verify(args.receipt,
        runtime / "bulk" / "sec" / "companyfacts.zip", runtime,
        Path("E:/M10/.scoring_v6_private"), private)
    print(json.dumps({ticker: {"score": item["score"], "status": item["status"],
                             "verified_signals": item["signals_verified"],
                             "signals": item["signals_partial"], "missing": item["missing"],
                             "current_accession": item["current_filing"]["accession"],
                             "companyfacts_sha256": item["source_companyfacts_sha256"]}
                      for ticker, item in report.items()}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
