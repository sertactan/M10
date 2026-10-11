"""Bind existing normalized S1-S3 research legs to original SEC acceptance times.

This is a source-timing receipt, never a new canonical factor or model score.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re


LEGS = ("D01_REVENUE_GROWTH_1Y_LEG", "D02_EPS_GROWTH_1Y_LEG",
        "D03_REVENUE_ACCELERATION_LEG", "F54_DIL_RESEARCH_LEG")


def _time(value: str) -> datetime:
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("naive SEC timestamp")
    return stamp


def bind_sec_acceptance(report_path: Path, submissions_path: Path, ticker: str) -> dict:
    report_bytes = report_path.read_bytes()
    subs_bytes = submissions_path.read_bytes()
    report = json.loads(report_bytes)
    subs = json.loads(subs_bytes)
    receipt_hash = sha256(subs_bytes).hexdigest()
    if report.get("sec_submissions_sha256") != receipt_hash:
        raise ValueError("SEC submissions SHA does not match report receipt")
    matches = [s for s in report["stocks"] if s["ticker"] == ticker]
    if len(matches) != 1:
        raise ValueError("ticker missing or ambiguous")
    stock = matches[0]
    cik = str(subs["cik"]).zfill(10)
    recent = subs["filings"]["recent"]
    accessions = recent["accessionNumber"]
    accepted = recent["acceptanceDateTime"]
    forms = recent["form"]
    if len(accessions) != len(accepted) or len(accessions) != len(forms):
        raise ValueError("SEC submissions parallel arrays differ")
    entries = dict(zip(accessions, zip(accepted, forms)))
    observed = []
    for key in LEGS:
        row = stock.get("features", {}).get(key)
        if row is None:
            continue
        source = row.get("source_ref", "")
        if not source.endswith(f"CIK{cik}.json"):
            raise ValueError(f"{key}: CIK/source mismatch")
        if row.get("unit") != "0_100" or not 0 <= float(row["value"]) <= 100:
            raise ValueError(f"{key}: invalid normalized leg")
        if not re.fullmatch(r"[0-9a-f]{64}", row.get("evidence_hash") or ""):
            raise ValueError(f"{key}: missing evidence hash")
        as_of = _time(row["as_of"])
        available = _time(row["available_at"])
        if available > as_of:
            raise ValueError(f"{key}: available after as-of")
        if not row.get("evidence"):
            raise ValueError(f"{key}: no fact evidence")
        for evidence in row["evidence"]:
            accession = evidence.get("accession")
            if accession not in entries:
                raise ValueError(f"{key}: accession absent from original submissions")
            if not re.fullmatch(r"[0-9a-f]{64}", evidence.get("hash") or ""):
                raise ValueError(f"{key}: invalid fact hash")
            accepted_at, form = entries[accession]
            accepted_time = _time(accepted_at)
            evidence_available = _time(evidence["available_at"])
            if form not in ("10-K", "10-Q") or accepted_time > evidence_available or evidence_available > available or available > as_of:
                raise ValueError(f"{key}: SEC timing/form conflict")
            if evidence.get("source_ref") != source:
                raise ValueError(f"{key}: evidence source mismatch")
            observed.append({"leg": key, "accession": accession,
                             "form": form, "accepted_at": accepted_at,
                             "research_available_at": evidence["available_at"],
                             "period": evidence.get("period"), "fact_hash": evidence.get("hash")})
    return {"ticker": ticker, "cik": cik,
            "report_sha256": sha256(report_bytes).hexdigest(),
            "submissions_sha256": receipt_hash,
            "partial_legs_bound": len({x["leg"] for x in observed}),
            "evidence_rows_bound": len(observed),
            "evidence": observed,
            "public_dissemination_verified": False,
            "canonical_pit_accepted": False,
            "s1_s2_s3_complete_scores": 0}
