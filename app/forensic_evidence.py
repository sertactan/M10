"""Independent, offline S13 forensic evidence gate (current research only).

S13's recovered qualitative rubric requires *reviewed filing bodies*. SEC
companyfacts or a submissions-index receipt alone cannot support a zero-risk
finding. This module performs no IO and never infers a qualitative judgment.

The caller must supply an explicit reviewed packet; the supplied content hashes
are provenance claims, not a substitute for checking the original filing bytes.
The resulting score never certifies historical public availability or PIT.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import json
import re
from collections.abc import Mapping
from urllib.parse import urlsplit

from app.recovered_quality import SOURCE, SOURCE_SHA256

VERSION = "S13_FORENSIC_RECOVERED_V1_RESEARCH"
SOURCE_LINES = [1707, 1833]
BLOCK_WEIGHTS = {"AUD": .25, "RPT": .15, "REC": .20, "DIL": .15,
                 "REV": .10, "ACQ": .10, "GOV": .05}
RUBRIC = (0, 25, 50, 75, 100)
_HEX64 = re.compile(r"[0-9a-fA-F]{64}\Z")
_ACCESSION = re.compile(r"\d{10}-\d{2}-\d{6}\Z")
_ACCEPTED_FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A"}


def _stamp(value):
    if not isinstance(value, str):
        return None
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return instant.astimezone(timezone.utc) if instant.tzinfo else None
    except ValueError:
        return None


def _day(value):
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _sha(value):
    return isinstance(value, str) and bool(_HEX64.fullmatch(value))


def _fingerprint(data):
    return sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _base(as_of, missing, *, score=None, components=None, filings=(), reviews=(),
          flag_review=None, flags=(), issuer=None):
    evidence = {"contract": SOURCE, "contract_sha256": SOURCE_SHA256,
                "contract_lines": SOURCE_LINES, "risk_weights": BLOCK_WEIGHTS,
                "risk_rubric": RUBRIC, "issuer": issuer, "filings": list(filings),
                "reviews": list(reviews), "flag_review": flag_review,
                "independent_serious_flags": list(flags),
                "source_content_hashes_verified": False,
                "historical_pit_accepted": False,
                "time_semantics": "RETRIEVAL_NOT_PROOF_OF_FIRST_PUBLIC_DISSEMINATION"}
    components = components or {}
    receipt = {"as_of": as_of.isoformat(), "score": score,
               "evidence": evidence, "components": components, "version": VERSION}
    return {"score": score,
            "status": "VERIFIED_RESEARCH_FORMULA" if score is not None else "DATA_MISSING",
            "scope": "RESEARCH_ONLY_NOT_CANONICAL_PIT", "canonical_accepted": False,
            "version": VERSION, "as_of": as_of.isoformat(),
            "missing": sorted(set(missing)), "components": components,
            "evidence": evidence, "evidence_hash": _fingerprint(receipt)}


def _normalize_filing(row, issuer_cik, at):
    """Accept only traceable SEC filing-body metadata, not SEC index data."""
    if not isinstance(row, Mapping):
        return None
    identifier, cik = row.get("filing_id"), str(row.get("cik", ""))
    accepted, retrieved = _stamp(row.get("accepted_at")), _stamp(row.get("retrieved_at"))
    available = _stamp(row["available_at"]) if row.get("available_at") is not None else None
    period = _day(row.get("period_end"))
    url = row.get("source_ref")
    if not _nonempty(url):
        return None
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None
    # SEC Archives URL identifies the subject issuer, even if an agent filed it.
    match = re.fullmatch(r"/Archives/edgar/data/(\d+)/(\d{18})/[^?#]+", parsed.path)
    if not (match and parsed.scheme == "https" and parsed.netloc.lower() in
            {"sec.gov", "www.sec.gov"} and match.group(1).lstrip("0") == issuer_cik.lstrip("0")
            and match.group(2) == str(row.get("accession", "")).replace("-", "")):
        return None
    if not (_nonempty(identifier) and _ACCESSION.fullmatch(str(row.get("accession", "")))
            and cik.isdigit() and cik.lstrip("0") == issuer_cik.lstrip("0")
            and row.get("source") == "SEC_EDGAR"
            and row.get("form_type") in _ACCEPTED_FORMS
            and _sha(row.get("content_sha256"))
            and accepted and retrieved and period
            and period <= accepted.date() and accepted <= retrieved <= at
            and (available is None or accepted <= available <= retrieved)):
        return None
    if row.get("available_at") is not None and available is None:
        return None
    return {"filing_id": identifier, "cik": issuer_cik,
            "accession": row["accession"], "form_type": row["form_type"],
            "period_end": period.isoformat(), "source": "SEC_EDGAR",
            "source_ref": url, "content_sha256": row["content_sha256"].lower(),
            "accepted_at": accepted.isoformat(), "retrieved_at": retrieved.isoformat(),
            "available_at": available.isoformat() if available else None}


def _normalize_review(row, filing_ids, at):
    if not isinstance(row, Mapping):
        return None
    block = row.get("block")
    reviewed = _stamp(row.get("reviewed_at"))
    refs = row.get("filing_ids")
    risk = row.get("risk")
    if not (isinstance(block, str) and block in BLOCK_WEIGHTS and type(risk) is int and risk in RUBRIC
            and row.get("coverage_complete") is True
            and _nonempty(row.get("reviewer")) and _nonempty(row.get("rationale"))
            and reviewed and reviewed <= at
            and isinstance(refs, list) and bool(refs)
            and all(isinstance(ref, str) and ref in filing_ids for ref in refs)
            and len(refs) == len(set(refs))):
        return None
    return {"block": block, "risk": risk, "coverage_complete": True,
            "reviewer": row["reviewer"], "rationale": row["rationale"],
            "reviewed_at": reviewed.isoformat(), "filing_ids": sorted(refs)}


def _normalize_flag_review(row, filing_ids, at):
    if not isinstance(row, Mapping):
        return None
    reviewed = _stamp(row.get("reviewed_at"))
    refs = row.get("filing_ids")
    if not (row.get("coverage_complete") is True
            and row.get("independence_review_complete") is True
            and _nonempty(row.get("reviewer")) and _nonempty(row.get("rationale"))
            and reviewed and reviewed <= at
            and isinstance(refs, list) and bool(refs)
            and all(isinstance(ref, str) and ref in filing_ids for ref in refs)
            and len(refs) == len(set(refs))):
        return None
    return {"coverage_complete": True, "independence_review_complete": True,
            "reviewer": row["reviewer"], "rationale": row["rationale"],
            "reviewed_at": reviewed.isoformat(), "filing_ids": sorted(refs)}


def _normalize_flag(row, filing_ids, reviews):
    if not isinstance(row, Mapping):
        return None
    refs, block = row.get("filing_ids"), row.get("block")
    if not (isinstance(block, str) and block in BLOCK_WEIGHTS
            and block in reviews and reviews[block]["risk"] > 0
            and row.get("severity") == "SERIOUS"
            and all(_nonempty(row.get(field)) for field in
                    ("flag_id", "independence_key", "independence_basis", "finding"))
            and isinstance(refs, list) and bool(refs)
            and all(isinstance(ref, str) and ref in filing_ids
                    and ref in reviews[block]["filing_ids"] for ref in refs)
            and len(refs) == len(set(refs))):
        return None
    return {"flag_id": row["flag_id"], "block": block, "severity": "SERIOUS",
            "finding": row["finding"], "independence_key": row["independence_key"],
            "independence_basis": row["independence_basis"], "filing_ids": sorted(refs)}


def compute_s13(packet: Mapping | None, at: datetime) -> dict:
    """Calculate S13 iff all seven SEC filing risk reviews and flag audit exist.

    Packet shape: {issuer:{ticker,cik}, filings:[SEC filing-body receipts],
    reviews:[{block,risk,coverage_complete,filing_ids,reviewer,reviewed_at,
    rationale}], flag_review:{coverage_complete,independence_review_complete,
    filing_ids,reviewer,reviewed_at,rationale}, serious_flags:[{flag_id,block,
    severity:'SERIOUS',finding,independence_key,independence_basis,filing_ids}]}.

    A zero-risk or zero-serious-flags assessment must be explicitly supported by
    a complete human review. No attempt is made to decide qualitative severity.
    """
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Offset-aware as_of datetime required")
    at = at.astimezone(timezone.utc)
    if not isinstance(packet, Mapping):
        return _base(at, [*BLOCK_WEIGHTS, "INDEPENDENT_SERIOUS_FLAG_REVIEW", "SEC_FILING_BODY_EVIDENCE"])
    issuer = packet.get("issuer")
    if not isinstance(issuer, Mapping) or not _nonempty(issuer.get("ticker")) or not str(issuer.get("cik", "")).isdigit() or int(str(issuer["cik"])) == 0:
        return _base(at, [*BLOCK_WEIGHTS, "ISSUER_IDENTITY", "INDEPENDENT_SERIOUS_FLAG_REVIEW"])
    cik = str(issuer["cik"])
    issuer_record = {"ticker": issuer["ticker"], "cik": cik}
    missing = []
    filings_by_id = {}
    raw_filings = packet.get("filings")
    if not isinstance(raw_filings, list) or not raw_filings:
        missing.append("SEC_FILING_BODY_EVIDENCE")
        raw_filings = []
    for item in raw_filings:
        filing = _normalize_filing(item, cik, at)
        if filing is None or filing["filing_id"] in filings_by_id:
            missing.append("INVALID_OR_DUPLICATE_SEC_FILING_EVIDENCE")
        else:
            filings_by_id[filing["filing_id"]] = filing
    raw_reviews = packet.get("reviews")
    if not isinstance(raw_reviews, list):
        raw_reviews = []
    reviews = {}
    for item in raw_reviews:
        review = _normalize_review(item, filings_by_id, at)
        if review is None or review["block"] in reviews:
            missing.append("INVALID_OR_DUPLICATE_BLOCK_REVIEW")
        else:
            reviews[review["block"]] = review
    missing.extend(block for block in BLOCK_WEIGHTS if block not in reviews)
    flag_review = _normalize_flag_review(packet.get("flag_review"), filings_by_id, at)
    if flag_review is None:
        missing.append("INDEPENDENT_SERIOUS_FLAG_REVIEW")
    elif not all(set(review["filing_ids"]).issubset(flag_review["filing_ids"])
                 for review in reviews.values()):
        missing.append("INDEPENDENT_SERIOUS_FLAG_REVIEW_INCOMPLETE_FILING_SCOPE")
    raw_flags = packet.get("serious_flags")
    flags = []
    if not isinstance(raw_flags, list):
        missing.append("EXPLICIT_SERIOUS_FLAGS_LIST")
    else:
        seen_ids, seen_keys = set(), set()
        for item in raw_flags:
            flag = _normalize_flag(item, filings_by_id, reviews)
            if flag is None:
                missing.append("INVALID_SERIOUS_FLAG_EVIDENCE")
                continue
            if flag["flag_id"] in seen_ids or flag["independence_key"] in seen_keys:
                missing.append("DUPLICATE_OR_NOT_INDEPENDENT_SERIOUS_FLAGS")
            seen_ids.add(flag["flag_id"])
            seen_keys.add(flag["independence_key"])
            if flag_review and not set(flag["filing_ids"]).issubset(flag_review["filing_ids"]):
                missing.append("SERIOUS_FLAG_OUTSIDE_REVIEWED_FILING_SCOPE")
            flags.append(flag)
    filings = sorted(filings_by_id.values(), key=lambda x: x["filing_id"])
    ordered_reviews = [reviews[b] for b in BLOCK_WEIGHTS if b in reviews]
    flags.sort(key=lambda x: x["flag_id"])
    if missing:
        return _base(at, missing, filings=filings, reviews=ordered_reviews,
                     flag_review=flag_review, flags=flags, issuer=issuer_record)
    base_risk = sum(BLOCK_WEIGHTS[b] * reviews[b]["risk"] for b in BLOCK_WEIGHTS)
    count = len(flags)
    independent_penalty = 15 if count >= 5 else 10 if count >= 4 else 5 if count >= 3 else 0
    final_risk = max(0.0, min(100.0, base_risk + independent_penalty))
    return _base(at, [], score=100.0 - final_risk,
                 components={"block_risks": {b: reviews[b]["risk"] for b in BLOCK_WEIGHTS},
                             "weighted_base_risk": base_risk,
                             "independent_serious_flag_count": count,
                             "independent_serious_flag_penalty": independent_penalty,
                             "forensic_risk_clipped": final_risk},
                 filings=filings, reviews=ordered_reviews,
                 flag_review=flag_review, flags=flags, issuer=issuer_record)
