"""Recovered S6 Dechow misstatement score; strict three-year evidence contract.

The original specification fixes L coefficients and F_D scaling but leaves the
RSST WC/NCO/FIN mappings and the extreme fallback tier underspecified. These
balances must arrive with independent issuer-period evidence and a reviewed
decomposition; no synthetic substitution is made for missing source fields.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import math
import re
from urllib.parse import urlsplit


VERSION = "S6_DECHOW_RECOVERED_RESEARCH_V1"
SOURCE_SHA256 = "53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794"
CONTRACT_LINES = (1180, 1277)
REQUIRED = (
    "assets", "receivables", "inventory", "ppe", "cash", "sales",
    "net_income", "wc", "nco", "fin",
)
SHA = re.compile(r"[0-9a-fA-F]{64}\Z")


def _stamp(raw):
    if not isinstance(raw, str):
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return value.astimezone(timezone.utc) if value.tzinfo is not None else None
    except ValueError:
        return None


def _source(item, at, end):
    if not isinstance(item, dict):
        return None
    value = item.get("value")
    available = _stamp(item.get("available_at"))
    url = urlsplit(str(item.get("source_ref", "")))
    if (type(value) not in (int, float) or not math.isfinite(value)
        or not available or available > at or item.get("period_end") != end
        or item.get("source") not in {"SEC_EDGAR", "SEC_EDGAR_LOCAL_ARCHIVE_ACCEPTED_UNVERIFIED"}
        or url.scheme != "https" or url.netloc.lower() not in {"data.sec.gov", "www.sec.gov", "sec.gov"}
        or not item.get("accession")
        or not SHA.fullmatch(str(item.get("evidence_hash", "")))):
        return None
    return item


def _missing(at, issues, refs, diagnostics=None):
    payload = {"version": VERSION, "as_of": at.isoformat(),
               "contract_sha256": SOURCE_SHA256, "contract_lines": CONTRACT_LINES,
               "score": None, "missing": sorted(set(issues)), "inputs": refs,
               "diagnostics": diagnostics or {}}
    return {"score": None, "status": "DATA_MISSING", "missing": payload["missing"],
            "components": diagnostics or {}, "evidence": payload,
            "evidence_hash": sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
            "scope": "RESEARCH_ONLY_NOT_CANONICAL_PIT", "canonical_accepted": False}


def calculate_dechow(periods: list[dict], *, as_of: datetime,
                     decomposition_review: dict | None = None,
                     issuance_review: dict | None = None,
                     peer_percentile: dict | None = None) -> dict:
    """S6 if 3 true FYs, all accounting fields, and a justified score tier exist.

    Each input is {value,source,source_ref,accession,evidence_hash,
    available_at,period_end}. Three periods must have contiguous FY start/end.
    `decomposition_review` explicitly attests the WC/NCO/FIN definitions and
    input source IDs; the model does not invent RSST accounting mappings.
    `issuance_review` must prove issued 0/1 including an affirmative no-issuance
    finding, never infer a zero from missing issuance facts.
    An independent empirical peer percentile remains unavailable until a frozen,
    reproducible peer/cohort-ranking contract is implemented. A supplied
    percentile is deliberately rejected rather than trusted by assertion.
    """
    if not isinstance(as_of, datetime) or not as_of.tzinfo or as_of.utcoffset() is None:
        raise ValueError("S6 requires an offset-aware research as_of")
    at = as_of.astimezone(timezone.utc)
    missing, refs = [], []
    if peer_percentile is not None:
        return _missing(at, ["EVIDENCED_PEER_PERCENTILE_REPRODUCIBLE_NOT_IMPLEMENTED"], [])
    if not isinstance(periods, list) or len(periods) != 3:
        return _missing(at, ["THREE_CONSECUTIVE_FISCAL_YEARS"], [])
    valid = []
    for index, period in enumerate(periods):
        try:
            start = date.fromisoformat(period["start"])
            end = date.fromisoformat(period["end"])
            if not 330 <= (end-start).days+1 <= 400:
                raise ValueError("Not annual")
        except (ValueError, TypeError, KeyError):
            missing.append(f"FY_{index}_INVALID_DATES")
            continue
        if end > at.date() or (valid and (valid[-1][1] + timedelta(days=1)) != start):
            missing.append("FISCAL_PERIOD_GAP_OR_FUTURE")
        facts = period.get("facts", {})
        if not isinstance(facts, dict):
            facts = {}
        values = {}
        for key in REQUIRED:
            evidence = _source(facts.get(key), at, end.isoformat())
            if evidence is None:
                missing.append(f"FY_{index}_{key.upper()}_SOURCE")
            else:
                values[key] = float(evidence["value"])
                refs.append({"year": end.isoformat(), "field": key,
                             **{k:evidence[k] for k in ("value","period_end","source","source_ref",
                                                        "accession","evidence_hash","available_at")}})
        valid.append((start, end, values))
    if not (isinstance(decomposition_review, dict)
            and decomposition_review.get("verified") is True
            and all(decomposition_review.get(k) for k in ("reviewer", "methodology_ref", "source_hash"))
            and SHA.fullmatch(str(decomposition_review.get("source_hash", "")))):
        missing.append("AUDITED_RSST_WC_NCO_FIN_DECOMPOSITION")
    if not (isinstance(issuance_review, dict) and issuance_review.get("verified") is True
            and type(issuance_review.get("issued")) is int and issuance_review["issued"] in (0, 1)
            and issuance_review.get("source_ref")
            and SHA.fullmatch(str(issuance_review.get("evidence_hash", "")))
            and _stamp(issuance_review.get("available_at"))
            and _stamp(issuance_review["available_at"]) <= at):
        missing.append("DOCUMENTED_DEBT_EQUITY_ISSUANCE_OR_CONFIRMED_ABSENCE")
    if missing:
        return _missing(at, missing, refs)
    (_, _, old), (_, _, prev), (_, end, curr) = valid
    try:
        avg = (curr["assets"] + prev["assets"]) / 2
        prior_avg = (prev["assets"] + old["assets"]) / 2
        if min(avg, prior_avg, curr["assets"], prev["assets"], old["assets"],
               curr["sales"], prev["sales"]) <= 0:
            raise ArithmeticError("S6 positive assets/sales gate")
        rec_change = curr["receivables"] - prev["receivables"]
        old_rec_change = prev["receivables"] - old["receivables"]
        cashsales = curr["sales"] - rec_change
        old_cashsales = prev["sales"] - old_rec_change
        if not old_cashsales:
            raise ArithmeticError("S6 previous cash sales zero")
        components = {
            "RSST": sum(curr[k] - prev[k] for k in ("wc", "nco", "fin")) / avg,
            "delta_REC": rec_change / avg,
            "delta_INV": (curr["inventory"] - prev["inventory"]) / avg,
            "SOFT": (curr["assets"] - curr["ppe"] - curr["cash"]) / curr["assets"],
            "delta_CASHSALES": (cashsales - old_cashsales) / abs(old_cashsales),
            "delta_ROA": curr["net_income"] / avg - prev["net_income"] / prior_avg,
            "ISSUE": issuance_review["issued"],
        }
        L = (-7.893 + .790*components["RSST"] + 2.518*components["delta_REC"]
             + 1.191*components["delta_INV"] + 1.979*components["SOFT"]
             + .171*components["delta_CASHSALES"] - .932*components["delta_ROA"]
             + 1.029*components["ISSUE"])
        misstatement = 1/(1+math.exp(-L)) if L >= 0 else math.exp(L)/(1+math.exp(L))
        F = misstatement / .0037
        if not all(math.isfinite(n) for n in (*components.values(), F)):
            raise ArithmeticError("S6 non-finite derived component")
        components.update(logistic_L=L, misstatement_probability=misstatement,
                          F_D=F, fiscal_year_end=end.isoformat())
    except (ArithmeticError, OverflowError, ZeroDivisionError):
        return _missing(at, ["VALID_RSST_AND_THREE_PERIOD_DENOMINATORS"], refs)
    if F < .75:
        score = 95
        components["normalization"] = "FROZEN_ABSOLUTE_UNAMBIGUOUS_BIN"
    elif .75 < F < 1.0:
        score = 85
        components["normalization"] = "FROZEN_ABSOLUTE_UNAMBIGUOUS_BIN"
    elif 1.0 < F < 1.85:
        score = 70
        components["normalization"] = "FROZEN_ABSOLUTE_UNAMBIGUOUS_BIN"
    elif 1.85 < F < 2.45:
        score = 50
        components["normalization"] = "FROZEN_ABSOLUTE_UNAMBIGUOUS_BIN"
    else:
        return _missing(at, ["S6_AMBIGUOUS_SCORE_BIN_ENDPOINT_OR_EXTREME"], refs, components)
    payload = {"version": VERSION, "as_of": at.isoformat(), "inputs": refs,
               "contract_sha256": SOURCE_SHA256, "contract_lines": CONTRACT_LINES,
               "score": score, "components": components,
               "decomposition_review": decomposition_review,
               "issuance_review": issuance_review, "peer_percentile": None,
               "source_content_hashes_verified": False, "historical_pit_accepted": False}
    return {"score": float(score), "status": "VERIFIED_RESEARCH_FORMULA", "missing": [],
            "components": components, "evidence": payload,
            "evidence_hash": sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
            "scope": "RESEARCH_ONLY_NOT_CANONICAL_PIT", "canonical_accepted": False}
