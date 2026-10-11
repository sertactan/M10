"""Offline, independent evidence gates for frozen S10 (2020-24) and S11 peers.

Uses only previously cached original SEC bytes and unchanged M10 scoring code.
Old S11 private reports are *claims* until original SEC cache-only replay agrees.
No web access, production mutation, synthetic financial rows or score promotion.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from decimal import Decimal, localcontext
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Mapping
import zipfile

from app.recovered_jones import MIN_OTHER_PEERS
from app.scoring_v6_jones_acceptance import _material
from app.scoring_v8_s8_s10 import TARGETS
from app.scoring_v9_s8_s10 import verify_frozen_source
from app.scoring_v10_s10 import (
    FROZEN_S10_SHA256, full_s10_gate, issuer_annual_inventory,
    prove_crmd_receivables,
    sic_from_original_10k_header, tca_dd_design,
)
from app.task9_jones_cohort import SECCache, scan_task9


S11_TARGETS = {
    "TMDX": {"cik": "0001756262", "sic": "3845", "pages": 10,
             "revenue_tag": "Revenues", "anchor": "2025-12-31"},
    "PENG": {"cik": "0001616533", "sic": "3674", "pages": 12,
             "revenue_tag": "RevenueFromContractWithCustomerExcludingAssessedTax",
             "anchor": "2025-08-29"},
}
FROZEN_S11_SHA256 = FROZEN_S10_SHA256
_SGML_URL = re.compile(
    r"https://www\.sec\.gov/Archives/edgar/data/(\d+)/"
    r"(\d{18})/(\d{10}-\d{2}-\d{6})\.txt\Z"
)


def sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _json_file(path: Path) -> dict:
    if not path.is_file() or path.is_symlink():
        raise ValueError("ORIGINAL_PRIVATE_SOURCE_REQUIRED:" + str(path))
    return json.loads(path.read_bytes())


def _verify_legacy_receipt(report: Path) -> tuple[dict, str]:
    if report.is_symlink() or not report.is_file():
        raise ValueError("S11_LEGACY_PRIVATE_REPORT_MISSING")
    raw = report.read_bytes()
    seal = Path(str(report) + ".sha256")
    if not seal.is_file() or seal.is_symlink() or seal.read_text("ascii").strip() != sha(raw):
        raise ValueError("S11_LEGACY_RECEIPT_SHA_MISMATCH")
    return json.loads(raw), sha(raw)


def s11_cohort_acceptance(summary: Mapping, *, ticker: str) -> dict:
    """Check evidence/identity, count and normalizer before considering a score.

    This does not substitute for SEC byte replay, which is performed separately.
    """
    cfg = S11_TARGETS[ticker]
    target = summary.get("target") or {}
    peers = summary.get("peer_observations") or []
    errors = []
    if (summary.get("ticker") != ticker or summary.get("target_cik") != cfg["cik"]
            or target.get("historical_sic") != cfg["sic"]
            or target.get("form_accession") != TARGETS[ticker]["accession"]
            or target.get("source_selected_count") != 8 or target.get("missing")):
        errors.append("TARGET_ORIGINAL_10K_SIC_OR_EIGHT_FIELDS_UNPROVEN")
    if (summary.get("required_peers") != MIN_OTHER_PEERS
            or summary.get("verified_same_sic_independent_peers") != len(peers)
            or len({p.get("cik") for p in peers}) != len(peers)):
        errors.append("PEER_COUNT_OR_UNIQUE_CIK_INCONSISTENT")
    if any(
        p.get("industry", {}).get("scheme") != "SIC"
        or p.get("industry", {}).get("code") != cfg["sic"]
        or p.get("cik") == cfg["cik"]
        or p.get("period_end") is None
        or abs((date.fromisoformat(p["period_end"]) -
                date.fromisoformat(cfg["anchor"])).days) > 45
        for p in peers
    ):
        errors.append("PEER_HISTORICAL_SIC_OR_YEAR_MISMATCH")
    if len(peers) < MIN_OTHER_PEERS:
        errors.append("S11_INDEPENDENT_ORIGINAL_SIC_PEERS_BELOW_20")
    if (summary.get("s11_score") is not None or
            summary.get("status") != "DATA_MISSING" or
            summary.get("canonical_accepted") is not False or
            summary.get("historical_pit_accepted") is not False):
        errors.append("INCONSISTENT_HISTORICAL_UNSCORED_RECEIPT")
    return {"ticker": ticker, "sic": cfg["sic"],
            "fiscal_anchor": cfg["anchor"], "accession":target.get("form_accession"),
            "original_sgml_header_sha256": target.get("header_sha256"),
            "target_financial_companyfacts_sha256":
                summary.get("target_financial_companyfacts_sha256"),
            "eight_original_target_inputs":target.get("source_selected_count"),
            "source_verified_independent_peers": len(peers),
            "required_independent_peers":MIN_OTHER_PEERS,
            "financial_precheck_8_of_8":summary.get("precheck_8_of_8"),
            "peer_ciks":sorted(p["cik"] for p in peers if "cik" in p),
            "peer_companyfacts_sha256":sorted(
                {p["cik"]: next((r.get("companyfacts_sha256")
                                  for r in summary.get("ranked_candidates", [])
                                  if r.get("cik") == p["cik"]), None)
                 for p in peers if "cik" in p}.items()),
            "reject_reason_counts":summary.get("ranked_rejection_counts"),
            "rejection_reasons":errors,"full_research_score":None,
            "canonical_PIT_accepted":False}


def offline_replay_s11(ticker: str, *, legacy_root: Path, runtime: Path) -> dict:
    """Re-evaluate prior private receipt through unchanged SEC original byte code.

    Every SEC request is disabled. A cache miss therefore fails replay closed;
    a previously successful report alone never establishes current acceptance.
    """
    cfg = S11_TARGETS[ticker]
    root = Path(legacy_root).resolve()
    report = root / ("jones_" + ticker.lower()) / "report.json"
    old, seal = _verify_legacy_receipt(report)
    baseline = s11_cohort_acceptance(old, ticker=ticker)
    if any(e for e in baseline["rejection_reasons"]
           if e != "S11_INDEPENDENT_ORIGINAL_SIC_PEERS_BELOW_20"):
        raise ValueError("S11_HISTORICAL_PRIVATE_EVIDENCE_CONTRADICTED")
    clock = datetime.fromisoformat(old["as_of"].replace("Z", "+00:00"))
    if clock.utcoffset() is None:
        raise ValueError("S11_PRIOR_AS_OF_TZ_MISSING")
    cache_path = root / ("task9_jones_" + ticker.lower())
    session = SECCache(cache_path, contact=None, request_budget=0, clock=lambda:clock)
    replay = scan_task9(
        session, runtime=Path(runtime), max_pages=cfg["pages"],
        max_candidates=80, as_of=clock, target_cik=cfg["cik"],
        target_ticker=ticker, sic=cfg["sic"],
        target_revenue_tag=cfg["revenue_tag"], anchor_end=cfg["anchor"],
    )
    checked = s11_cohort_acceptance(replay, ticker=ticker)
    stable = ("ticker", "target_cik", "target_financial_companyfacts_sha256",
              "precheck_8_of_8", "verified_same_sic_independent_peers",
              "required_peers", "s11_score", "s11_missing", "stop_reason")
    divergences=[k for k in stable if old.get(k)!=replay.get(k)]
    divergences += [k for k in ("target","ranked_rejection_counts")
                    if old.get(k)!=replay.get(k)]
    # Current clock instants may differ on nonmaterial observed-at metadata;
    # financial source records, origin SIC and accession hashes must coincide.
    if ([_material(p) for p in old.get("peer_observations",[])] !=
            [_material(p) for p in replay.get("peer_observations",[])]):
        divergences.append("peer_original_financial_material")
    if session.requests != 0 or divergences:
        raise ValueError("S11_OFFLINE_ORIGINAL_BYTE_REPLAY_CONFLICT:"
                         + ticker + ":" + ",".join(divergences)
                         + ":requests=" + str(session.requests))
    if checked["rejection_reasons"] != baseline["rejection_reasons"]:
        raise ValueError("S11_COHORT_EVIDENCE_REPLAY_CONFLICT")
    return {**checked, "legacy_report_sha256":seal,
            "offline_SEC_original_bytes_replayed":True,
            "offline_SEC_requests":session.requests,
            "original_response_cache_hits":session.cached,
            "legacy_SEC_network_requests":old.get("network_requests"),
            "source_status":"ORIGINAL_SIC_FINANCIALS_REPLAYED_MINIMUM_PEERS_UNMET"}


def verified_cached_historical_headers(response_dirs: list[Path]) -> dict:
    """Inventory *existing* original 10-K SGML headers by actual fiscal year.

    Does not use current SIC lists as historical membership. Corrupt metadata
    is rejected, so no FY or issuer is counted from a filename or bare claim.
    """
    unique = {}
    bad = Counter()
    for directory in response_dirs:
        if not directory.is_dir():
            continue
        for meta_path in sorted(directory.glob("*.json")):
            if meta_path.is_symlink():
                bad["SYMLINK_METADATA"] += 1
                continue
            try:
                meta = _json_file(meta_path)
                match = _SGML_URL.fullmatch(str(meta.get("url", "")))
                if not match:
                    continue
                data_path = meta_path.with_suffix(".bin")
                if not data_path.is_file() or data_path.is_symlink():
                    bad["ORIGINAL_BYTES_MISSING"] += 1
                    continue
                raw = data_path.read_bytes()
                if meta.get("sha256") != sha(raw) or meta.get("http_status") not in (200, 206):
                    bad["SOURCE_SHA_OR_STATUS_MISMATCH"] += 1
                    continue
                sec_header = raw.decode("latin-1", "replace").split("</SEC-HEADER>", 1)[0]
                period = re.search(r"CONFORMED PERIOD OF REPORT:\s*(\d{8})", sec_header)
                if not period:
                    bad["NO_ANNUAL_PERIOD_HEADER"] += 1
                    continue
                fiscal_end = date(int(period[1][:4]), int(period[1][4:6]), int(period[1][6:]))
                proven = sic_from_original_10k_header(
                    raw, cik=match[1], accession=match[3], report_date=fiscal_end.isoformat())
                key = (proven["cik"], fiscal_end.year, proven["sic"])
                if key in unique and unique[key]["sha256"] != proven["header_sha256"]:
                    bad["DIVERGENT_ORIGINAL_HEADER_FOR_SAME_CIK_FY_SIC"] += 1
                    continue
                unique[key] = {"cik": proven["cik"], "year":fiscal_end.year,
                               "sic":proven["sic"], "accession":match[3],
                               "sha256":proven["header_sha256"]}
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                bad["MALFORMED_OR_UNVERIFIABLE_SEC_HEADER"] += 1
    return {"verified_2020_2024_original_SIC_headers":{
                str(year):[v for v in sorted(unique.values(),key=lambda x:(x["year"],x["cik"]))
                           if v["year"] == year] for year in range(2020,2025)},
            "all_verified_headers_count":len(unique),
            "rejected_cache_entries":dict(sorted(bad.items())),
            "historical_SIC_claims_from_current_directory":0}


def recompute_source_tca(inventory: Mapping, year: int, design: Mapping) -> dict:
    """Independent high precision check against exact pinned SEC dollar inputs."""
    if design["status"] != "REAL_ORIGINAL_SEC_ANNUAL_TCA_DESIGN_DIAGNOSTIC":
        return {"status":design["status"], "reason":design.get("missing", []),
                "score":None}
    previous = inventory["annual"][year - 1]
    current = inventory["annual"][year]
    with localcontext() as context:
        context.prec = 65
        def value(rec, key):
            source = rec["facts"][key]
            if source.get("status") != "SOURCE_EXACT":
                raise ValueError("S10_INDEPENDENT_ACCOUNTING_FACT_MISSING")
            return Decimal(source["USD"])
        pca,ca = value(previous,"current_assets"),value(current,"current_assets")
        pcash,cash = value(previous,"cash_equivalents"),value(current,"cash_equivalents")
        pcl,cl = value(previous,"current_liabilities"),value(current,"current_liabilities")
        pd,debt = previous["short_term_debt"],current["short_term_debt"]
        if pd.get("value_USD") is None or debt.get("value_USD") is None:
            raise ValueError("S10_INDEPENDENT_SHORT_TERM_DEBT_UNPROVEN")
        tca = ca-pca-cash+pcash-cl+pcl+Decimal(debt["value_USD"])-Decimal(pd["value_USD"])
        avg = (value(current,"assets")+value(previous,"assets"))/2
        if avg<=0 or tca != Decimal(design["row"]["tca"]):
            raise ValueError("S10_INDEPENDENT_DECIMAL_TCA_DISAGREEMENT")
        if abs(tca/avg-Decimal(design["row"]["normalized"]["tca_over_average_assets"])) > Decimal("1e-25"):
            raise ValueError("S10_INDEPENDENT_DECIMAL_NORMALIZATION_DISAGREEMENT")
    return {"status":"SEC_ORIGINAL_TCA_INDEPENDENT_DECIMAL_CONFIRMED",
            "source_original_accessions":design["row"]["original_accessions"],
            "source_companyfacts_sha256": inventory["companyfacts_sha256"],
            "tca_USD":str(tca),"average_assets_USD":str(avg),
            "scaled_TCA":str(tca/avg),"score":None}


def audit_s10_historical_window(archive: Path, historical: Mapping,
                                *, crmd_zero_evidence: Mapping | None = None) -> dict:
    """Bounded five-member ZIP analysis. No collection of thousands of peers."""
    observations={}
    with zipfile.ZipFile(archive) as z:
        for ticker, cfg in TARGETS.items():
            info=z.getinfo("CIK"+cfg["cik"]+".json")
            if info.file_size > 40_000_000:
                raise ValueError("S10_PINNED_SEC_ISSUER_OVERSIZE")
            raw=z.read(info)
            inventory=issuer_annual_inventory(
                ticker,raw,years=tuple(range(2019,2026)),
                crmd_zero_evidence=(crmd_zero_evidence if ticker=="CRMD" else None))
            yearly={}
            for fy in range(2020,2025):
                design=tca_dd_design(inventory,fy)
                yearly[str(fy)]=recompute_source_tca(inventory,fy,design)
            observations[ticker]={
                "issuer_companyfacts_sha256":inventory["companyfacts_sha256"],
                "original_annual_accessions":{
                    str(y):inventory["annual"][y]["accession"] for y in range(2019,2026)},
                "source_bounded_real_TCA_design_years": [
                    int(y) for y, v in yearly.items()
                    if v["status"] == "SEC_ORIGINAL_TCA_INDEPENDENT_DECIMAL_CONFIRMED"],
                "five_fiscal_year_results":yearly,
                "verified_annual_SIC_regime_20plus_cohorts":0,
                "full_research_S10":None,
            }
    by_year=historical["verified_2020_2024_original_SIC_headers"]
    # An original SIC header alone never establishes the audited accounting
    # regime or the six real DD fields, so it cannot constitute an eligible row.
    count_by_year={year:len(items) for year,items in by_year.items()}
    return {"period":"FY2020-FY2024", "source":"PINNED_OFFICIAL_SEC_BULK_MEMBERS",
            "FY2019_opening_required":True, "FY2025_CFO_lead_required":True,
            "FY2026_CFO_lead_required":False,
            "cached_historical_original_10k_SIC_headers_per_year":count_by_year,
            "SEC_original_regime_and_full_DD_peer_panels_20plus":0,
            "frozen_five_year_gate":full_s10_gate([],[]),
            "original_sigma_and_percentile_tie_rule":"UNSPECIFIED_IN_FROZEN_SOURCE",
            "stocks": observations,"full_new_S10_scores":0}


def audit_extension(*, runtime: Path, legacy_root: Path,
                    task9_cache: Path, s10_cache: Path) -> dict:
    verify_frozen_source()
    if FROZEN_S10_SHA256 != FROZEN_S11_SHA256:
        raise ValueError("FROZEN_CONTRACT_SHA_MISMATCH")
    response_dirs=[Path(legacy_root)/("task9_jones_"+t.lower())/"responses"
                   for t in ("TMDX","PENG","ETON")]
    response_dirs += [Path(task9_cache)/"responses",Path(s10_cache)/"responses"]
    header_inventory=verified_cached_historical_headers(response_dirs)
    # Exact FY2021-23 debt-zero statement reconciliation already independently
    # source-verified by the existing V10 worker. Reuse its original immutable
    # SEC 10-K bytes and hashes; without this evidence no zero debt is assumed.
    from scripts.scoring_v10_s10 import cached_original
    crmd_proof=prove_crmd_receivables(cached_original(2022),cached_original(2023))
    s10=audit_s10_historical_window(Path(runtime)/"bulk/sec/companyfacts.zip",
                                    header_inventory, crmd_zero_evidence=crmd_proof)
    s11={}
    for ticker in ("TMDX","PENG"):
        s11[ticker]=offline_replay_s11(ticker,legacy_root=legacy_root,runtime=runtime)
    return {"schema":"M10_SCORING_V10_EXTENSION_PEERS_ORIGINAL_SEC_OFFLINE_V1",
            "frozen_original_source_sha256":FROZEN_S10_SHA256,
            "S10":s10,"S11":s11,
            "historical_SEC_SIC_header_cache":header_inventory,
            "new_verified_full_research_scores":0,
            "new_canonical_PIT_scores":0,
            "network_requests":0,
            "limitation":"PREEXISTING_SEC_CACHES_ONLY; NO HISTORICAL_S10_PANELS",
            "permitted_result":"DATA_MISSING_FOR_S10_TMDX_PENG_S11"}
