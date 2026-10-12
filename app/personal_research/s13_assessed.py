"""Local, pure S13 Personal AI-Assessed research calculator.

The evidence packet contains SEC filing metadata and local original body bytes,
source_findings from task9_forensic_review, seven explicit ai_reviews, and an
independent flag_review plus serious_flags list. Every AI judgment is labeled
as an unapproved proposal. No filesystem/network access or expert signature.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
import re
from urllib.parse import urlsplit

from app.forensic_evidence import BLOCK_WEIGHTS, RUBRIC, SOURCE, SOURCE_SHA256
from app.scoring_v3_sec_filing_evidence import _extract_text

VERSION = "S13_PERSONAL_AI_ASSESSED_V1.0"
BLOCKS = tuple(BLOCK_WEIGHTS)
HEX64 = re.compile(r"[a-fA-F0-9]{64}\Z")
ACCESSION = re.compile(r"\d{10}-\d{2}-\d{6}\Z")
SEC_PATH = re.compile(r"/Archives/edgar/data/(\d+)/(\d{18})/[^/?#]+\Z")
FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A", "8-K", "8-K/A"}


def _filled(v):
    return isinstance(v, str) and bool(v.strip())


def _sha(v):
    return isinstance(v, str) and bool(HEX64.fullmatch(v))


def _date(v):
    try:
        dt = v if isinstance(v, datetime) else datetime.fromisoformat(v.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.utcoffset() is not None else None
    except (AttributeError, TypeError, ValueError):
        return None


def _strings(v):
    return (isinstance(v, list) and all(_filled(x) for x in v)
            and len(set(v)) == len(v))


def _url(v, cik, accession):
    if not _filled(v):
        return False
    try:
        p = urlsplit(v)
        m = SEC_PATH.fullmatch(p.path)
        return bool(p.scheme == "https" and p.netloc.lower() in ("sec.gov", "www.sec.gov")
                    and not p.query and not p.fragment and m and
                    int(m[1]) == int(cik) and m[2] == accession.replace("-", ""))
    except (ValueError, TypeError):
        return False


def _initial(packet):
    issuer = packet.get("issuer") if isinstance(packet, Mapping) else None
    if isinstance(packet, Mapping) and not isinstance(issuer, Mapping):
        issuer = {"ticker": packet.get("ticker"), "cik": packet.get("cik")}
    return {
        "version": VERSION, "model": "S13_PERSONAL", "status": "UNRESOLVED",
        "score": None, "S13_Personal": None, "canonical_accepted": False,
        "original_status": "REVIEW_REQUIRED", "numeric_result_type": "UNRESOLVED",
        "receipt_sha256": None,
        "expert_approved": False, "historical_pit_accepted": False,
        "scope": "PERSONAL_RESEARCH_AI_ASSESSED", "missing": [],
        "issuer": issuer,
        "blocks": {b: {"status": "UNRESOLVED", "weight": BLOCK_WEIGHTS[b],
                       "risk": None, "positives": [], "negatives": [],
                       "considered_findings": [], "observations": [],
                       "verified_source_findings": [], "reasons": []} for b in BLOCKS},
        "flags": [], "components": {},
        "source_contract": {
            "name": SOURCE, "sha256": SOURCE_SHA256, "lines": [1707, 1833],
            "weights": dict(BLOCK_WEIGHTS), "risk_rubric": list(RUBRIC)},
        "provenance": {"source_content_hashes_verified": False,
                       "verified_filing_count": 0, "verified_finding_count": 0,
                       "decision_provenance": "AI_PROPOSAL_UNAPPROVED",
                       "semantic_accuracy_of_ai_claims_independently_verified": False,
                       "historical_availability_verified": False}
    }


def _problem(out, issue, block=None, review=False):
    out["missing"].append(issue)
    if block in BLOCKS:
        out["blocks"][block]["reasons"].append(issue)
        out["blocks"][block]["status"] = "REVIEW_REQUIRED" if review else "UNRESOLVED"


def _filings(packet, out, at, cik):
    rows = packet.get("filings")
    if not isinstance(rows, list) or not rows:
        _problem(out, "MISSING_SEC_ORIGINAL_BODIES")
        return {}
    seen = {}
    for ix, r in enumerate(rows):
        if not isinstance(r, Mapping):
            _problem(out, f"INVALID_FILING:{ix}")
            continue
        acc = r.get("accession")
        raw = r.get("body_bytes", r.get("body"))
        digest = r.get("source_content_sha256", r.get("content_sha256"))
        accepted, retrieved = _date(r.get("accepted_at")), _date(r.get("retrieved_at"))
        form = r.get("form", r.get("form_type"))
        issuer_cik = str(r.get("cik", ""))
        if not (isinstance(acc, str) and ACCESSION.fullmatch(acc)
                and issuer_cik.isdigit() and int(issuer_cik) == int(cik)
                and acc not in seen and _url(r.get("source_ref"), cik, acc)
                and isinstance(form, str) and form in FORMS
                and isinstance(raw, bytes) and _sha(digest)
                and sha256(raw).hexdigest() == digest.lower()
                and accepted and retrieved and accepted <= retrieved <= at):
            _problem(out, f"INVALID_FILING:{ix}")
            continue
        try:
            fulltext = _extract_text(raw)
        except (ValueError, TypeError):
            _problem(out, f"INVALID_FILING_BODY:{ix}")
            continue
        if r.get("extracted_text_sha256") is not None and (
                not _sha(r["extracted_text_sha256"]) or
                sha256(fulltext.encode()).hexdigest() != r["extracted_text_sha256"].lower()):
            _problem(out, f"EXTRACTED_TEXT_HASH_MISMATCH:{ix}")
            continue
        seen[acc] = {"source_ref": r["source_ref"],
                     "content_sha256": digest.lower(), "text": fulltext}
    out["provenance"]["verified_filing_count"] = len(seen)
    out["provenance"]["source_content_hashes_verified"] = bool(seen) and len(seen) == len(rows)
    return seen


def _findings(packet, out, filings):
    source = packet.get("source_packet", packet)
    rows = packet.get("source_findings")
    if isinstance(rows, Mapping):
        rows = [{**f, "block": b} if isinstance(f, Mapping) else f
                for b, vals in rows.items() if b in BLOCKS and isinstance(vals, list)
                for f in vals]
    if rows is None and isinstance(source, Mapping) and isinstance(source.get("blocks"), Mapping):
        rows = []
        for b in BLOCKS:
            area = source["blocks"].get(b, {})
            if isinstance(area, Mapping):
                rows.extend({**f, "block": b} if isinstance(f, Mapping) else f
                            for f in area.get("findings", area.get("source_findings", [])))
    if not isinstance(rows, list) or not rows:
        _problem(out, "MISSING_LOCATED_SOURCE_FINDINGS")
        return {}
    seen = {}
    for ix, row in enumerate(rows):
        if not isinstance(row, Mapping):
            _problem(out, f"UNVERIFIED_FINDING:{ix}")
            continue
        b, acc, fid, anchor = (row.get(k) for k in
                               ("block", "accession", "finding_id", "anchor"))
        if b in BLOCKS:
            out["blocks"][b]["observations"].append({
                "finding_id": fid, "accession": acc,
                "section_reference": row.get("section_reference"),
                "source_ref": row.get("source_ref"),
                "filing_body_sha256": row.get("filing_body_sha256"),
                "observed_claim": row.get("observed_claim"),
                "inference_boundary": row.get("inference_boundary"),
                "verification": "RECEIPT_ONLY_UNVERIFIED"})
        filing = filings.get(acc) if isinstance(acc, str) else None
        excerpt = row.get("context_excerpt")
        offset = row.get("extracted_text_offset")
        if not (b in BLOCKS and filing and _filled(fid) and fid not in seen
                and _filled(anchor) and _filled(excerpt)
                and type(offset) is int and offset >= 0
                and _filled(row.get("section_reference"))
                and _filled(row.get("observed_claim"))
                and _filled(row.get("inference_boundary"))
                and _sha(row.get("context_sha256"))
                and sha256(excerpt.encode()).hexdigest() == row["context_sha256"].lower()
                and _sha(row.get("filing_body_sha256"))
                and row["filing_body_sha256"].lower() == filing["content_sha256"]
                and row.get("source_ref") == filing["source_ref"]
                and fid == f"{b}:{acc}:{sha256(anchor.encode()).hexdigest()[:12]}"):
            _problem(out, f"UNVERIFIED_FINDING:{ix}", b)
            continue
        text = filing["text"]
        regexp = r"\s+".join(re.escape(word) for word in anchor.split())
        matched = re.compile(regexp, re.IGNORECASE).match(text, offset) if regexp else None
        # Bind the context digest to the precise anchor occurrence. Checking
        # whether the excerpt appears anywhere in the filing is insufficient
        # when the same contractual language occurs more than once.
        contextual = (re.sub(
            r"\s+", " ", text[max(0, offset - 300):
                              min(len(text), matched.end() + 1550)]).strip()[:2200]
                      if matched else None)
        near = re.sub(r"\s+", " ", excerpt)
        needed = row.get("required_nearby_context", [])
        if (not matched or excerpt != contextual
                or not re.search(regexp, excerpt, re.IGNORECASE)
                or not _strings(needed)
                or any(re.sub(r"\s+", " ", p).casefold() not in near.casefold()
                       for p in needed)):
            _problem(out, f"UNLOCATED_OR_UNCORROBORATED_FINDING:{ix}", b)
            continue
        seen[fid] = {"finding_id": fid, "block": b, "accession": acc,
                     "source_ref": filing["source_ref"],
                     "filing_body_sha256": filing["content_sha256"],
                     "section_reference": row["section_reference"],
                     "anchor": anchor, "extracted_text_offset": offset,
                     "context_sha256": row["context_sha256"].lower(),
                     "observed_claim": row["observed_claim"],
                     "inference_boundary": row["inference_boundary"],
                     "kind": row.get("kind")}
        out["blocks"][b]["observations"][-1]["verification"] = "LOCAL_BYTES_AND_EXACT_LOCATOR_VERIFIED"
        out["blocks"][b]["verified_source_findings"].append(seen[fid])
    out["provenance"]["verified_finding_count"] = len(seen)
    return seen


def _review_blocks(packet, out, facts, at):
    reviews = packet.get("ai_reviews")
    if not isinstance(reviews, list):
        reviews = []
        _problem(out, "MISSING_AI_REVIEWS", review=True)
    if any(not isinstance(r, Mapping) or r.get("block") not in BLOCKS for r in reviews):
        _problem(out, "INVALID_AI_REVIEW_COLLECTION", review=True)
    for b in BLOCKS:
        area = out["blocks"][b]
        ids = {i for i, f in facts.items() if f["block"] == b}
        selections = [r for r in reviews if isinstance(r, Mapping) and r.get("block") == b]
        if not ids:
            _problem(out, f"{b}:MISSING_VERIFIED_SOURCE_CONTEXT", b)
        if len(selections) != 1:
            _problem(out, f"{b}:CONTRADICTORY_OR_MISSING_AI_DECISION", b, True)
            continue
        r = selections[0]
        positive, negative, considered = (r.get(k) for k in
                                           ("positive_finding_ids", "negative_finding_ids",
                                            "considered_finding_ids"))
        risk = r.get("risk")
        stamp = _date(r.get("assessed_at"))
        if not (type(risk) is int and risk in RUBRIC
                and r.get("assessment_type") == "AI_PROPOSAL"
                and r.get("coverage_complete") is True and stamp and stamp <= at
                and all(_filled(r.get(k)) for k in
                        ("rationale", "materiality_reason", "alternative_explanation"))
                and _strings(positive) and _strings(negative) and _strings(considered)
                and set(considered) == ids and set(positive).isdisjoint(negative)
                and set(positive + negative) == ids):
            _problem(out, f"{b}:INCOMPLETE_AI_DECISION", b, True)
            continue
        area.update(status="AI_ASSESSED", risk=risk,
                    positives=[facts[i] for i in sorted(positive)],
                    negatives=[facts[i] for i in sorted(negative)],
                    considered_findings=sorted(considered),
                    rationale=r["rationale"],
                    materiality_reason=r["materiality_reason"],
                    alternative_explanation=r["alternative_explanation"],
                    assessed_at=stamp.isoformat())


def _flags(packet, out, facts, at):
    review = packet.get("flag_review")
    all_ids = set(facts)
    if not (isinstance(review, Mapping)
            and review.get("assessment_type") == "AI_PROPOSAL"
            and review.get("coverage_complete") is True
            and review.get("independence_review_complete") is True
            and _filled(review.get("rationale"))
            and _strings(review.get("reviewed_finding_ids"))
            and set(review["reviewed_finding_ids"]) == all_ids
            and (stamp := _date(review.get("assessed_at"))) is not None
            and stamp <= at):
        _problem(out, "INCOMPLETE_INDEPENDENT_FLAG_REVIEW", review=True)
    raw = packet.get("serious_flags")
    if not isinstance(raw, list):
        _problem(out, "MISSING_EXPLICIT_SERIOUS_FLAGS", review=True)
        return
    dedup, seen_ids, used = {}, set(), {}
    for ix, r in enumerate(raw):
        if not isinstance(r, Mapping):
            _problem(out, f"INVALID_SERIOUS_FLAG:{ix}", review=True)
            continue
        b, key, fid = r.get("block"), r.get("independence_key"), r.get("flag_id")
        ids = r.get("finding_ids")
        if not (b in BLOCKS and out["blocks"][b]["risk"] in RUBRIC
                and out["blocks"][b]["risk"] > 0
                and r.get("assessment_type") == "AI_PROPOSAL"
                and r.get("severity") == "SERIOUS"
                and _filled(key) and _filled(fid)
                and _filled(r.get("finding")) and _filled(r.get("independence_basis"))
                and _strings(ids) and bool(ids)
                and all(i in facts and facts[i]["block"] == b for i in ids)
                and fid not in seen_ids):
            _problem(out, f"INVALID_SERIOUS_FLAG:{ix}", b, True)
            continue
        seen_ids.add(fid)
        if any(i in used and used[i] != key for i in ids):
            _problem(out, f"CONTRADICTORY_FLAG_INDEPENDENCE:{ix}", b, True)
            continue
        for i in ids:
            used[i] = key
        if key in dedup:
            previous = dedup[key]
            if previous["independence_basis"] != r["independence_basis"]:
                _problem(out, f"CONTRADICTORY_FLAG_BASIS:{ix}", b, True)
                continue
            previous["flag_ids"].add(fid)
            previous["blocks"].add(b)
            previous["finding_ids"].update(ids)
        else:
            dedup[key] = {"independence_key": key,
                          "independence_basis": r["independence_basis"],
                          "finding": r["finding"], "severity": "SERIOUS",
                          "flag_ids": {fid}, "blocks": {b}, "finding_ids": set(ids)}
    out["flags"] = [
        {**item, "flag_ids": sorted(item["flag_ids"]),
         "blocks": sorted(item["blocks"]), "finding_ids": sorted(item["finding_ids"]),
         "provenance": [facts[i] for i in sorted(item["finding_ids"])]}
        for _, item in sorted(dedup.items())]


def assess_s13(packet: Mapping | None) -> dict:
    """Calculate only a fully sourced, seven-block Personal research estimate.

    receipt_sha256 digests an attempted assessment of an identified,
    timestamped issuer; it is not an SEC evidence hash or an approval. An
    absent packet or unusable issuer/time has no assessment to receipt.
    """
    out = _initial(packet)
    if not isinstance(packet, Mapping):
        _problem(out, "MISSING_PERSONAL_S13_PACKET")
        return _seal(out, issue_receipt=False)
    issuer, at = out["issuer"], _date(packet.get("as_of"))
    if not (isinstance(issuer, Mapping) and at
            and _filled(issuer.get("ticker")) and str(issuer.get("cik", "")).isdigit()
            and int(str(issuer["cik"])) > 0):
        _problem(out, "INVALID_AS_OF_OR_ISSUER")
        return _seal(out, issue_receipt=False)
    if packet.get("period_end") is not None:
        try:
            if date.fromisoformat(packet["period_end"]) > at.date():
                _problem(out, "PERIOD_END_AFTER_AS_OF")
        except (ValueError, TypeError):
            _problem(out, "INVALID_PERIOD_END")
    contract = packet.get("source_contract")
    source_packet = packet.get("source_packet")
    if contract is None and isinstance(source_packet, Mapping):
        contract = source_packet.get("source_contract")
    if contract is not None and (not isinstance(contract, Mapping)
                                or contract.get("sha256") != SOURCE_SHA256
                                or contract.get("weights") != BLOCK_WEIGHTS
                                or contract.get("risk_rubric") != list(RUBRIC)):
        _problem(out, "FROZEN_CONTRACT_MISMATCH")
    if isinstance(source_packet, Mapping):
        unresolved = source_packet.get("unresolved_anchors", [])
        if not isinstance(unresolved, list):
            _problem(out, "INVALID_SOURCE_PACKET_UNRESOLVED_ANCHORS")
        elif unresolved:
            _problem(out, "SOURCE_PACKET_HAS_UNRESOLVED_ANCHORS")
    filings = _filings(packet, out, at, str(issuer["cik"]))
    facts = _findings(packet, out, filings)
    _review_blocks(packet, out, facts, at)
    _flags(packet, out, facts, at)
    if out["missing"]:
        out["missing"] = sorted(set(out["missing"]))
        if any(b["status"] == "REVIEW_REQUIRED" for b in out["blocks"].values()):
            out["status"] = "REVIEW_REQUIRED"
        return _seal(out)
    base_risk = sum(Decimal(str(BLOCK_WEIGHTS[b])) *
                    Decimal(out["blocks"][b]["risk"]) for b in BLOCKS)
    count = len(out["flags"])
    penalty = 15 if count >= 5 else 10 if count == 4 else 5 if count == 3 else 0
    clipped = min(Decimal(100), base_risk + Decimal(penalty))
    score = float(Decimal(100) - clipped)
    out.update(status="AI_ASSESSED_RESEARCH", score=score, S13_Personal=score,
               numeric_result_type="SCENARIO",
               components={"block_risks": {b: out["blocks"][b]["risk"] for b in BLOCKS},
                           "weighted_base_risk": float(base_risk),
                           "independent_serious_flag_count": count,
                           "deduplicated_flag_mentions": sum(
                               len(f["flag_ids"]) for f in out["flags"]) - count,
                           "independent_serious_flag_penalty": penalty,
                           "forensic_risk_clipped": float(clipped)})
    return _seal(out)


def _seal(out: dict, *, issue_receipt: bool = True) -> dict:
    """Stable result digest, when an assessment can identify issuer and time."""
    out["components"]["categories"] = {
        b: {"risk": out["blocks"][b]["risk"],
            "status": out["blocks"][b]["status"],
            "observations": len(out["blocks"][b]["observations"]),
            "verified_findings": len(out["blocks"][b]["verified_source_findings"])}
        for b in BLOCKS}
    out["components"]["flags"] = {
        "independent_count": len(out["flags"]) if not out["missing"] else None,
        "independent_issues": [f["independence_key"] for f in out["flags"]]}
    if not issue_receipt:
        # Preserve the full diagnostic schema without manufacturing a
        # receipt for a nonexistent or unidentified assessment request.
        return out
    receipt = {k: v for k, v in out.items() if k != "receipt_sha256"}
    out["receipt_sha256"] = sha256(json.dumps(
        receipt, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        allow_nan=False).encode("utf-8")).hexdigest()
    return out
