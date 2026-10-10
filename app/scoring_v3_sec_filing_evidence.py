"""Source-hashed SEC filing-body research for INOD S13; no automatic risk scores.

SEC Submissions identifies documents; only byte-verified primary document bodies
provide passage evidence. Keyword hits are candidate passages, never seven
reviewed risk judgments or independently serious flags. All paths are offline.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
import re
from collections.abc import Mapping

from app.forensic_evidence import BLOCK_WEIGHTS, compute_s13

VERSION = "M10_V3_SEC_FILING_BODY_FORENSIC_RESEARCH_V1"
CIK = "0000903651"
SEC_HOST = "https://www.sec.gov"
MAX_BODY_BYTES = 18_000_000
ACCESSION = re.compile(r"\d{10}-\d{2}-\d{6}\Z")
PRIMARY = re.compile(r"[A-Za-z0-9_.-]{1,180}\.(?:htm|html|txt)\Z", re.IGNORECASE)
SHA = re.compile(r"[a-fA-F0-9]{64}\Z")

# These locate possibly relevant filing passages. They are never a risk rubric.
TERMS = {
    "AUD": ("independent registered public accounting firm", "auditor", "audit opinion",
            "internal control over financial reporting", "material weakness",
            "significant deficiency", "going concern", "change in accountants"),
    "RPT": ("related party", "related parties", "related-party", "transactions with related"),
    "REC": ("accounts receivable", "unbilled receivable", "credit losses",
            "allowance for doubtful", "customer concentration", "concentration of credit"),
    "DIL": ("stock-based compensation", "stock based compensation",
            "shares outstanding", "equity incentive", "dilutive", "dilution"),
    "REV": ("revenue recognition", "contract liabilities", "deferred revenue",
            "performance obligation", "revenue from contracts"),
    "ACQ": ("acquisition", "business combination", "purchase price allocation",
            "goodwill", "intangible assets"),
    "GOV": ("board of directors", "audit committee", "corporate governance",
            "director independence", "executive compensation", "proxy statement"),
}
SERIOUS_CANDIDATE_TERMS = (
    "material weakness", "substantial doubt", "restatement", "material misstatement",
    "investigation by the sec", "fraud", "going concern",
    "disagreement with accountants", "non-reliance on previously issued",
)


def _utc(raw: str) -> datetime:
    if not isinstance(raw, str):
        raise ValueError("OFFSET_AWARE_TIMESTAMP_REQUIRED")
    try:
        d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("INVALID_TIMESTAMP") from exc
    if d.utcoffset() is None:
        raise ValueError("OFFSET_AWARE_TIMESTAMP_REQUIRED")
    return d.astimezone(timezone.utc)


def _record(cik: str, arrays: dict, index: int) -> dict:
    acc = arrays["accessionNumber"][index]
    form = arrays["form"][index]
    primary = arrays["primaryDocument"][index]
    if not isinstance(acc, str) or not ACCESSION.fullmatch(acc):
        raise ValueError("INVALID_ACCESSION")
    if not isinstance(primary, str) or not PRIMARY.fullmatch(primary):
        raise ValueError("UNSAFE_PRIMARY_DOCUMENT")
    filed = date.fromisoformat(arrays["filingDate"][index])
    accepted = _utc(arrays["acceptanceDateTime"][index])
    period = arrays["reportDate"][index]
    if period:
        date.fromisoformat(period)
    name = f"{acc.replace('-', '')}_{primary}"
    return {
        "ticker": "INOD", "cik": cik, "accession": acc, "form": form,
        "filing_date": filed.isoformat(), "accepted_at": accepted.isoformat(),
        "sec_report_date": period or None,
        "period_end": (period or None) if form in ("10-K", "10-Q") else None,
        "primary_document": primary,
        "cache_name": name,
        "source_ref": (f"{SEC_HOST}/Archives/edgar/data/{int(cik)}/"
                       f"{acc.replace('-', '')}/{primary}"),
    }


def filing_manifest(submissions_raw: bytes, *, through: str = "2026-10-11",
                    max_8k: int = 30) -> list[dict]:
    """Derive explicit SEC URLs from cached original submissions parallel arrays."""
    if not isinstance(submissions_raw, bytes) or not 0 < len(submissions_raw) <= 5_000_000:
        raise ValueError("SEC_SUBMISSIONS_INVALID_SIZE")
    source = json.loads(submissions_raw)
    if not isinstance(source, dict) or str(source.get("cik", "")).zfill(10) != CIK:
        raise ValueError("SEC_SUBMISSIONS_ISSUER_MISMATCH")
    recent = source["filings"]["recent"]
    keys = ("accessionNumber", "form", "primaryDocument", "filingDate",
            "acceptanceDateTime", "reportDate")
    columns = [recent[k] for k in keys]
    if not all(isinstance(c, list) for c in columns) or len({len(c) for c in columns}) != 1:
        raise ValueError("SEC_SUBMISSIONS_ARRAY_LENGTH_MISMATCH")
    end = date.fromisoformat(through)
    if end < date(2026, 1, 1) or end > date(2026, 12, 31) or not 0 <= max_8k <= 60:
        raise ValueError("INVALID_RESEARCH_WINDOW")
    chosen = []
    for i in range(len(columns[0])):
        form, filed, period = recent["form"][i], date.fromisoformat(recent["filingDate"][i]), recent["reportDate"][i]
        if filed > end:
            continue
        if ((form == "10-K" and period in ("2024-12-31", "2025-12-31"))
                or (form == "10-Q" and date(2026, 1, 1) <= filed <= end)
                or (form in ("8-K", "8-K/A") and date(2026, 1, 1) <= filed <= end)):
            chosen.append(_record(CIK, recent, i))
    annuals = [r for r in chosen if r["form"] == "10-K"]
    if len(annuals) != 2 or {r["period_end"] for r in annuals} != {"2024-12-31", "2025-12-31"}:
        raise ValueError("FY2024_FY2025_10K_AMBIGUOUS_OR_MISSING")
    quarterly = [r for r in chosen if r["form"] == "10-Q"]
    eight = [r for r in chosen if r["form"] in ("8-K", "8-K/A")]
    if len(eight) > max_8k:
        raise ValueError("2026_8K_BUDGET_TOO_SMALL_REQUIRES_EXPLICIT_SELECTION")
    if len({r["accession"] for r in chosen}) != len(chosen):
        raise ValueError("DUPLICATE_ACCESSION_IN_MANIFEST")
    return sorted(annuals + quarterly + eight,
                  key=lambda r: (r["filing_date"], r["accession"]))


class _BodyText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.ignored += 1
        if tag in ("p", "div", "tr", "li", "br", "h1", "h2", "h3", "h4", "td"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.ignored = max(0, self.ignored - 1)
        if tag in ("p", "div", "tr", "li", "h1", "h2", "h3", "h4"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


def _extract_text(raw: bytes) -> str:
    if not isinstance(raw, bytes) or not 512 <= len(raw) <= MAX_BODY_BYTES:
        raise ValueError("FILING_BODY_MISSING_OR_OVERSIZE")
    decoded = raw.decode("utf-8", errors="replace")
    if "<html" not in decoded[:20000].lower() and "<body" not in decoded[:20000].lower():
        raise ValueError("NOT_AN_HTML_FILING_BODY")
    parser = _BodyText()
    parser.feed(decoded)
    text = re.sub(r"[ \t\r\f\v]+", " ", "".join(parser.parts))
    text = re.sub(r"\n\s*\n+", "\n", text)
    if len(text) < 1000:
        raise ValueError("FILING_BODY_TOO_SHORT_TO_REVIEW")
    return text


def _hits(text: str, terms: tuple[str, ...], *, limit: int = 5) -> list[dict]:
    low = text.casefold()
    rows = []
    for term in terms:
        # Lower-case literal matching plus anchored excerpts; avoid infinite loops.
        for m in list(re.finditer(re.escape(term.casefold()), low))[:2]:
            start, stop = max(0, m.start() - 190), min(len(text), m.end() + 230)
            excerpt = re.sub(r"\s+", " ", text[start:stop]).strip()
            rows.append({"term": term, "char_offset": m.start(),
                         "excerpt": excerpt, "excerpt_sha256": sha256(excerpt.encode()).hexdigest()})
    return sorted(rows, key=lambda r: r["char_offset"])[:limit]


def analyze_filing_body(metadata: Mapping, body: bytes, *, retrieved_at: str) -> dict:
    """Extract verifiable passages, never set risk=0 from absent terms."""
    if not isinstance(metadata, Mapping) or metadata.get("cik") != CIK:
        raise ValueError("FOREIGN_ISSUER_OR_MISSING_METADATA")
    acc = metadata.get("accession")
    if not isinstance(acc, str) or not ACCESSION.fullmatch(acc):
        raise ValueError("INVALID_ACCESSION")
    if not isinstance(metadata.get("source_ref"), str) or not metadata["source_ref"].startswith(
            f"{SEC_HOST}/Archives/edgar/data/{int(CIK)}/{acc.replace('-', '')}/"):
        raise ValueError("NONCANONICAL_SEC_SOURCE_URL")
    fetched = _utc(retrieved_at)
    if _utc(metadata["accepted_at"]) > fetched:
        raise ValueError("RETRIEVED_BEFORE_SEC_ACCEPTANCE")
    text = _extract_text(body)
    sections = {key: _hits(text, keywords) for key, keywords in TERMS.items()}
    flags = _hits(text, SERIOUS_CANDIDATE_TERMS, limit=20)
    return {
        "accession": acc, "form": metadata["form"],
        "filing_date": metadata["filing_date"], "period_end": metadata["period_end"],
        "sec_report_date": metadata["sec_report_date"],
        "accepted_at": metadata["accepted_at"], "retrieved_at": fetched.isoformat(),
        "source_ref": metadata["source_ref"], "source_content_sha256": sha256(body).hexdigest(),
        "extracted_text_sha256": sha256(text.encode()).hexdigest(),
        "extracted_chars": len(text), "sections": sections,
        "independent_serious_flags": None,
        "unadjudicated_serious_term_hits": flags,
        "all_seven_blocks_reviewed": False,
        "independence_review_complete": False,
        "risk_assigned": False, "historical_pit_accepted": False,
    }


def assess_filing_collection(manifest: list[dict], evidence: list[dict],
                             *, as_of: str) -> dict:
    """Describe precisely what source body documents and seven-block reviews lack."""
    _utc(as_of)
    wanted = {row["accession"]: row for row in manifest}
    actual = {}
    for item in evidence:
        acc = item.get("accession")
        if acc not in wanted or acc in actual or item.get("source_ref") != wanted[acc]["source_ref"]:
            raise ValueError("UNEXPECTED_DUPLICATE_OR_MISMATCHED_FILING_BODY")
        if not SHA.fullmatch(str(item.get("source_content_sha256", ""))):
            raise ValueError("FILING_BODY_SHA256_MISSING")
        actual[acc] = item
    missing = sorted(set(wanted) - set(actual))
    block_summary = {}
    for block in BLOCK_WEIGHTS:
        sources = [
            {"accession": r["accession"], "source_content_sha256": r["source_content_sha256"],
             "sections": r["sections"][block]}
            for r in evidence if r["sections"].get(block)
        ]
        block_summary[block] = {
            "status": "HUMAN_FILING_REVIEW_REQUIRED",
            "filing_passage_sources": sources,
            "passage_sources_count": len(sources),
            "risk": None, "coverage_complete": False,
        }
    return {
        "version": VERSION, "ticker": "INOD", "cik": CIK,
        "as_of": _utc(as_of).isoformat(),
        "status": "REVIEW_REQUIRED",
        "expected_filing_count": len(wanted), "body_filing_count": len(actual),
        "missing_body_accessions": missing,
        "filings": evidence, "blocks": block_summary,
        "independent_serious_flags_review": "REVIEW_REQUIRED",
        "serious_flag_count": None,
        "S13": None, "S14": None, "canonical_accepted": False,
        "notes": ["Term hits are not confirmed risk or serious flags.",
                  "No absence-of-term inference, zero-risk default or automated S13 score.",
                  "Retrieval time is not historical public dissemination."],
    }


def reviewed_s13_only(packet: Mapping | None, source_evidence: list[dict],
                      *, as_of: str) -> dict:
    """Optional explicit reviewed packet, delegated to frozen S13 evidence gate.

    The automated collector never creates reviews, flag_review, or serious_flags.
    A reviewer packet must refer to the same previously hashed local bodies.
    Hash equality is an integrity check; it cannot verify the human judgments.
    """
    at = _utc(as_of)
    if not isinstance(packet, Mapping) or not isinstance(source_evidence, list):
        return {"status": "REVIEW_REQUIRED", "S13": None, "review_missing":
                ["INDEPENDENT_MANUAL_FILING_REVIEW"], "canonical_accepted": False}
    source_by_accession = {
        r.get("accession"): r for r in source_evidence
        if isinstance(r, Mapping) and SHA.fullmatch(str(r.get("source_content_sha256", "")))
    }
    filings = packet.get("filings")
    if (not isinstance(filings, list) or not filings
            or any(not isinstance(f, Mapping)
                   or f.get("accession") not in source_by_accession
                   or f.get("content_sha256") != source_by_accession[f["accession"]]["source_content_sha256"]
                   or f.get("source_ref") != source_by_accession[f["accession"]]["source_ref"]
                   for f in filings)):
        return {"status": "REVIEW_REQUIRED", "S13": None, "review_missing":
                ["VERIFIED_SEC_FILING_BODY_HASH_AND_URL_BINDING"], "canonical_accepted": False}
    output = compute_s13(packet, at)
    return {
        "status": "RESEARCH_REVIEW_COMPLETE" if output["score"] is not None else "REVIEW_REQUIRED",
        "S13": output["score"], "review_missing": output["missing"],
        "evidence": output["evidence"], "canonical_accepted": False,
    }
