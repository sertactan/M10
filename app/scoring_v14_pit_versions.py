"""Source-bound filing version and issuer-identity anchors; never PIT admission."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
import json
import re


ACCESSIONS = ("0001410578-25-000194", "0001104659-26-020655")
CONCEPTS = ("CashAndCashEquivalentsAtCarryingValue",
            "AllowanceForDoubtfulAccountsReceivableCurrent")
NUMERIC_TAG = re.compile(r"<ix:nonFraction\b([^>]*)>(.*?)</ix:nonFraction>", re.I | re.S)
NONNUMERIC_TAG = re.compile(r"<ix:nonNumeric\b([^>]*)>(.*?)</ix:nonNumeric>", re.I | re.S)
ATTR = re.compile(r"([\w:]+)\s*=\s*(['\"])(.*?)\2", re.S)
HTML_TAG = re.compile(r"<[^>]+>")


def _utc(value: str) -> datetime:
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("OFFSET_AWARE_TIMESTAMP_REQUIRED")
    return stamp.astimezone(timezone.utc)


def _facts(html: bytes, *, concept: str, period_end: str) -> int:
    text = html.decode("utf-8", errors="strict")
    found = set()
    for match in NUMERIC_TAG.finditer(text):
        attrs = {key.lower(): value for key, _, value in ATTR.findall(match.group(1))}
        if (attrs.get("name", "").lower() != "us-gaap:" + concept.lower()
                or attrs.get("scale") != "3"
                or f"As_Of_{period_end}" not in attrs.get("contextref", "")
                or "USD" not in attrs.get("unitref", "")):
            continue
        digits = unescape(HTML_TAG.sub("", match.group(2))).strip().replace(",", "")
        if not re.fullmatch(r"\d+", digits):
            raise ValueError("NONNUMERIC_IXBRL_FACT")
        found.add(int(digits) * 1000)
    if len(found) != 1:
        raise ValueError("PRIMARY_FILING_FACT_MISSING_OR_AMBIGUOUS:" + concept)
    return found.pop()


def _dei(html: bytes, *, name: str, year: int) -> str:
    text = html.decode("utf-8", errors="strict")
    found = set()
    for match in NONNUMERIC_TAG.finditer(text):
        attrs = {key.lower(): value for key, _, value in ATTR.findall(match.group(1))}
        if (attrs.get("name", "").lower() == "dei:" + name.lower()
                and f"Duration_1_1_{year}_To_12_31_{year}" in attrs.get("contextref", "")):
            found.add(unescape(HTML_TAG.sub("", match.group(2))).strip())
    if len(found) != 1:
        raise ValueError("FILING_IDENTITY_MISSING_OR_AMBIGUOUS:" + name)
    return found.pop()


def _official_companyfact(companyfacts: dict, *, concept: str, accession: str) -> int:
    units = companyfacts["facts"]["us-gaap"][concept]["units"]["USD"]
    candidates = {row["val"] for row in units
                  if row.get("accn") == accession and row.get("end") == "2024-12-31"
                  and row.get("start") is None and row.get("form") == "10-K"}
    if len(candidates) != 1:
        raise ValueError("COMPANYFACTS_VERSION_MISSING_OR_AMBIGUOUS:" + concept)
    return candidates.pop()


def audit_versions(submissions_bytes: bytes, submissions_receipt_bytes: bytes,
                   companyfacts_bytes: bytes, bodies: dict[str, bytes],
                   body_receipts: dict[str, bytes], *, as_of: str) -> dict:
    """Confirm two original bodies' changing FY2024 comparative values.

    As-of selection below uses SEC accepted-at only as an administrative floor.
    It is not historical publication or provider available-at selection.
    """
    decision = _utc(as_of)
    sec = json.loads(submissions_bytes)
    sec_receipt = json.loads(submissions_receipt_bytes)
    if (sha256(submissions_bytes).hexdigest() != sec_receipt.get("sha256")
            or len(submissions_bytes) != sec_receipt.get("bytes")
            or sec_receipt.get("http_status") != 200
            or str(sec.get("cik", "")).zfill(10) != "0000903651"):
        raise ValueError("SEC_SUBMISSIONS_SEAL_OR_ISSUER_INVALID")
    facts = json.loads(companyfacts_bytes)
    if int(facts.get("cik", 0)) != 903651:
        raise ValueError("COMPANYFACTS_ISSUER_MISMATCH")
    recent = sec["filings"]["recent"]
    index = {accession: i for i, accession in enumerate(recent["accessionNumber"])}
    if len(index) != len(recent["accessionNumber"]):
        raise ValueError("SEC_DUPLICATE_ACCESSION")
    versions = []
    for accession, year in zip(ACCESSIONS, (2024, 2025)):
        i = index[accession]
        if recent["form"][i] != "10-K" or recent["reportDate"][i] != f"{year}-12-31":
            raise ValueError("SEC_FILING_IDENTITY_MISMATCH")
        body, receipt = bodies[accession], json.loads(body_receipts[accession])
        if (sha256(body).hexdigest() != receipt.get("sha256")
                or len(body) != receipt.get("bytes")
                or receipt.get("accession") != accession
                or receipt.get("form") != "10-K"):
            raise ValueError("PRIMARY_BODY_SEAL_MISMATCH")
        identity = {field: _dei(body, name=field, year=year)
                    for field in ("EntityCentralIndexKey", "TradingSymbol", "Security12bTitle", "SecurityExchangeName")}
        if identity["EntityCentralIndexKey"] != "0000903651" or identity["TradingSymbol"] != "INOD":
            raise ValueError("PRIMARY_BODY_IDENTITY_MISMATCH")
        values = {}
        for concept in CONCEPTS:
            from_body = _facts(body, concept=concept, period_end="12_31_2024")
            from_facts = _official_companyfact(facts, concept=concept, accession=accession)
            if from_body != from_facts:
                raise ValueError("BODY_COMPANYFACTS_VERSION_CONFLICT:" + concept)
            values[concept] = from_body
        versions.append({"accession": accession, "form": "10-K", "fiscal_year": year,
                         "accepted_at": _utc(recent["acceptanceDateTime"][i]).isoformat(),
                         "body_sha256": receipt["sha256"],
                         "body_retrieved_at": receipt.get("retrieved_at"),
                         "body_authenticity_independently_verified": receipt.get("source_authenticity_independently_verified") is True,
                         "filing_identity": identity, "fy2024_comparative_usd": values,
                         "first_public_at": None, "historical_provider_available_at": None})
    if _utc(versions[0]["accepted_at"]) >= _utc(versions[1]["accepted_at"]):
        raise ValueError("VERSION_CHRONOLOGY_INVALID")
    changes = {concept: {"original_usd": versions[0]["fy2024_comparative_usd"][concept],
                         "later_comparative_usd": versions[1]["fy2024_comparative_usd"][concept]}
               for concept in CONCEPTS}
    if any(v["original_usd"] == v["later_comparative_usd"] for v in changes.values()):
        raise ValueError("EXPECTED_COMPARATIVE_CHANGE_NOT_FOUND")
    amendments = [{"accession": accession, "form": recent["form"][i],
                   "report_date": recent["reportDate"][i],
                   "accepted_at": _utc(recent["acceptanceDateTime"][i]).isoformat()}
                  for accession, i in index.items()
                  if recent["form"][i] in {"10-K/A", "10-Q/A"}
                  and recent["reportDate"][i] in {"2024-12-31", "2025-12-31"}]
    amendments.sort(key=lambda row: (row["accepted_at"], row["accession"]))
    administrative_visible = [v["accession"] for v in versions if _utc(v["accepted_at"]) <= decision]
    return {"schema": "M10_V14_PIT_VERSION_DIAGNOSTIC_V1", "cik": "0000903651",
            "source_sha256": {"submissions": sha256(submissions_bytes).hexdigest(),
                              "submissions_receipt": sha256(submissions_receipt_bytes).hexdigest(),
                              "companyfacts_current_snapshot": sha256(companyfacts_bytes).hexdigest(),
                              **{accession + "_receipt": sha256(body_receipts[accession]).hexdigest() for accession in ACCESSIONS}},
            "as_of": decision.isoformat(), "versions": versions,
            "changed_comparatives": changes,
            "amendment_rows_in_current_submissions_snapshot": amendments,
            "administrative_acceptance_visible_accessions": administrative_visible,
            "amendment_form_observed_in_two_version_chain": False,
            "formal_restatement_status": "UNDETERMINED",
            "version_change_classification": "LATER_COMPARATIVE_CHANGED_NOT_FORMAL_RESTATEMENT_PROOF",
            "filing_level_identity_anchors": 2,
            "daily_historical_share_class_mapping_certified": False,
            "first_publication_verified": 0,
            "historical_provider_available_at_verified": 0,
            "canonical_asof_versions": 0,
            "s16c_normalized_pit_features": 0}
