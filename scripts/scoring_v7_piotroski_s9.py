"""Fetch official annual filings and create private S9 source receipts."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.task9_jones_cohort import SECCache, read_sec_contact
from app.scoring_v7_piotroski import TARGETS, create_receipt, seal_report, verify_s9_receipt


PRIVATE = Path("E:/M10/.scoring_v7_private")
V6_PRIVATE = Path("E:/M10/.scoring_v6_private")
OLD_CACHES = {"TMDX": V6_PRIVATE/"task9_jones_tmdx",
              "PENG": V6_PRIVATE/"task9_jones_peng",
              "ETON": V6_PRIVATE/"task9_jones_eton"}


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf8")).hexdigest()


def _seed_url(old_root: Path, new_root: Path, url: str):
    key = _url_hash(url)
    old_bin, old_meta = old_root/"responses"/(key+".bin"), old_root/"responses"/(key+".json")
    if not old_bin.is_file() or not old_meta.is_file():
        raise ValueError("REUSABLE_SEC_SOURCE_NOT_FOUND")
    raw = old_bin.read_bytes()
    metadata = json.loads(old_meta.read_text(encoding="utf8"))
    if metadata.get("url") != url or metadata.get("sha256") != hashlib.sha256(raw).hexdigest():
        raise ValueError("REUSABLE_SEC_SOURCE_HASH_INVALID")
    dest = new_root/"responses"
    dest.mkdir(parents=True, exist_ok=True)
    for source, target in ((old_bin, dest/(key+".bin")), (old_meta, dest/(key+".json"))):
        if target.exists():
            if target.read_bytes() != source.read_bytes():
                raise ValueError("V7_SEC_CACHE_COLLISION")
        else:
            shutil.copyfile(source, target)


def main():
    runtime = Path(os.environ["LOCALAPPDATA"])/"S153ResearchTerminal"/"runtime"
    archive = runtime/"bulk/sec/companyfacts.zip"
    cache_root = PRIVATE/"task9_jones_piotroski"
    PRIVATE.mkdir(parents=True, exist_ok=True)
    if not archive.is_file():
        raise ValueError("PRIVATE_V7_RUNTIME_SOURCE_MISSING")
    for ticker, cfg in TARGETS.items():
        old = OLD_CACHES[ticker]
        _seed_url(old, cache_root, f"https://data.sec.gov/submissions/CIK{cfg['cik']}.json")
        header_url = (f"https://www.sec.gov/Archives/edgar/data/{int(cfg['cik'])}/"
                      f"{cfg['current_accession'].replace('-', '')}/{cfg['current_accession']}.txt")
        _seed_url(old, cache_root, header_url)

    contact = read_sec_contact(Path("E:/M10/.env"))
    if not contact:
        raise ValueError("CONFIGURED_SEC_CONTACT_REQUIRED")
    sec = SECCache(cache_root, contact=contact, request_budget=3)
    filing_bytes = {}
    for ticker, cfg in TARGETS.items():
        data, meta = sec.load(cfg["filing_url"], limit=20_000_000)
        if data is None or meta.get("http_status") != 200:
            raise ValueError("OFFICIAL_SEC_FILING_FETCH_FAILED")
        filing_bytes[ticker] = data

    summaries = []
    for ticker in TARGETS:
        result = create_receipt(ticker=ticker, runtime=runtime, cache_root=cache_root,
                                companyfacts_archive=archive,
                                filing_html=filing_bytes[ticker],
                                submissions_cache=cache_root)
        path = PRIVATE/"piotroski_s9"/ticker.lower()/"report.json"
        seal_report(result, path)
        verified = verify_s9_receipt(path, companyfacts_archive=archive,
                                     cache_root=cache_root, runtime=runtime)
        summaries.append({"ticker": ticker, "status": verified["score_status"],
                          "score": verified["score"], "signal_count": verified["signal_count"],
                          "score_decimal": verified["score_decimal"],
                          "filing_accession": verified["current_accession"],
                          "filing_body_sha256": verified["filing_body_sha256"],
                          "independent_decimal_pass": verified["independent_decimal_reference"]["signals"] == verified["signals"]})
    print(json.dumps({"status": "REAL_SCORE_ACCEPTED_RESEARCH", "scores": summaries,
                      "network_requests": sec.requests,
                      "http_statuses": dict(sec.http_statuses)}, sort_keys=True))


if __name__ == "__main__":
    main()
