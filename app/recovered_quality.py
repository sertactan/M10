"""Recovered frozen quality formulas; pure current-research calculations.

No database/provider access. A complete formula score never establishes PIT
acceptance. SOURCE_INTEGRITY.md in the owner's plugin pins the source hashes.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import hashlib
import json
import math
import re
from core.scoring.math import piecewise_score

VERSION = "S1_S14_CANONICAL_V1.0_RECOVERED_RESEARCH_V1"
SOURCE_SHA256 = "53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794"
INTERPOLATION_SHA256 = "75d192891c0d67dccad5c5e004b07769998718effe189fe6af668ae435d3109c"
SOURCE = "S1_S2_S14_CANONICAL_SOURCE.md"
CONTRACTS = {
    "B_Q": {"lines": [1015, 1176, 1851, 1866], "missing": ["BENEISH_SEVEN_COMPONENT_RISKS", "EVIDENCED_INTERACTION_RISK"]},
    "S6": {"lines": [1180, 1277], "missing": ["RSST_COMPONENTS", "THREE_PERIOD_CASH_SALES_ROA", "ISSUANCE_EVIDENCE", "PEER_OR_UNAMBIGUOUS_FALLBACK"]},
    "S7": {"lines": [1281, 1321], "missing": []},
    "S11": {"lines": [1550, 1623], "missing": ["INDUSTRY_YEAR_JONES_REGRESSION", "EVIDENCED_DISCRETIONARY_ACCRUAL"]},
    "S12": {"lines": [1627, 1703], "missing": []},
    "S13": {"lines": [1707, 1833], "missing": ["AUD", "RPT", "REC", "DIL", "REV", "ACQ", "GOV", "INDEPENDENT_SERIOUS_FLAG_COUNT"]},
}


def _time(value):
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return d if d.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def _valid(row, at):
    try:
        available = _time(row.get("available_at"))
        end = date.fromisoformat(row["period_end"])
        return bool(
            available and available <= at and end <= at.date()
            and (not row.get("filing_date") or date.fromisoformat(row["filing_date"]) <= at.date())
            and row.get("source") in {"SEC_EDGAR", "SEC_EDGAR_LOCAL_ARCHIVE_ACCEPTED_UNVERIFIED"}
            and row.get("form_type") in {"10-K", "10-Q"}
            and row.get("unit") == "USD"
            and row.get("source_ref") and row.get("accession")
            and re.fullmatch(r"[0-9a-fA-F]{64}", str(row.get("evidence_hash", "")))
            and math.isfinite(float(row["value"]))
        )
    except (ValueError, TypeError, KeyError, OverflowError):
        return False


def _one(rows, metric, kind, end=None, start=None):
    keys = {"TOTAL_ASSETS", "ASSETS"} if metric == "TOTAL_ASSETS" else {metric}
    found = [r for r in rows if r.get("metric") in keys and r.get("period_kind") == kind
             and (end is None or r["period_end"] == end)
             and (start is None or r.get("period_start") == start)]
    if not found:
        return None
    key = lambda r: (r["period_end"], _time(r["available_at"]))
    newest = max(key(r) for r in found)
    tied = [r for r in found if key(r) == newest]
    if len({float(r["value"]) for r in tied}) != 1:
        return None  # Same-time contradictory values are not silently selected.
    return max(tied, key=lambda r: r["accession"])


def _annual(row):
    if row is None:
        return False
    try:
        span = (date.fromisoformat(row["period_end"]) - date.fromisoformat(row["period_start"])).days + 1
        return 330 <= span <= 400
    except (ValueError, TypeError, KeyError):
        return False


def _result(model, at, *, score=None, missing=(), inputs=(), components=None,
            period=None, status=None):
    refs = [{k: r.get(k) for k in (
        "metric", "value", "unit", "period_start", "period_end", "period_kind",
        "source", "source_ref", "accession", "form_type", "filing_date", "accepted_at",
        "available_at", "evidence_hash")} for r in inputs if r]
    evidence = {"contract": SOURCE, "contract_sha256": SOURCE_SHA256,
                "contract_lines": CONTRACTS[model]["lines"],
                "interpolation_contract": "Meridyen_S15.3_Canonical_Final_Spec_v1.0.md:68-84",
                "interpolation_sha256": INTERPOLATION_SHA256,
                "inputs": refs, "historical_pit_accepted": False,
                "time_semantics": "ARCHIVE_AVAILABLE_AT_IS_NOT_VERIFIED_PUBLIC_DISSEMINATION"}
    payload = {"model": model, "as_of": at.isoformat(), "score": score,
               "version": VERSION, "evidence": evidence, "components": components or {}}
    return {"score": score, "status": status or ("VERIFIED_DONE" if score is not None else "DATA_MISSING"),
            "scope": "RESEARCH_ONLY_NOT_CANONICAL_PIT", "version": VERSION,
            "missing": list(missing), "components": components or {},
            "period": period, "as_of": at.isoformat(), "evidence": evidence,
            "evidence_hash": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
            "canonical_accepted": False}


def _s7(rows, at):
    ni = _one(rows, "NET_INCOME", "ANNUAL")
    if not _annual(ni):
        return _result("S7", at, missing=["NET_INCOME_VALID_ANNUAL_PERIOD"])
    start, end = ni["period_start"], ni["period_end"]
    prior = (date.fromisoformat(start) - timedelta(days=1)).isoformat()
    cfo = _one(rows, "OPERATING_CASH_FLOW", "ANNUAL", end, start)
    a1 = _one(rows, "TOTAL_ASSETS", "INSTANT", end)
    a0 = _one(rows, "TOTAL_ASSETS", "INSTANT", prior)
    fields = {"OPERATING_CASH_FLOW_SAME_FY": cfo, "TOTAL_ASSETS_FY_END": a1,
              "TOTAL_ASSETS_FY_START_MINUS_ONE_DAY": a0}
    missing = [k for k, v in fields.items() if v is None]
    inputs = [ni, cfo, a1, a0]
    if missing:
        return _result("S7", at, missing=missing, inputs=inputs, period=end)
    if float(a1["value"]) <= 0 or float(a0["value"]) <= 0:
        return _result("S7", at, missing=["POSITIVE_TOTAL_ASSETS"], inputs=inputs, period=end)
    average = (float(a1["value"]) + float(a0["value"])) / 2
    accrual = (float(ni["value"]) - float(cfo["value"])) / average
    score = piecewise_score(accrual, [(0, 100), (.05, 75), (.10, 50), (.15, 25), (.20, 0)])
    return _result("S7", at, score=score, inputs=inputs, period=end,
                   components={"average_total_assets": average, "sloan_accrual": accrual,
                               "normalization": "EXPLICIT_ABSOLUTE_FALLBACK_NO_PEER_COHORT",
                               "warning": "Negative accrual requires separate S13 write-down/restructuring review."})


def _s12(rows, at):
    rev = _one(rows, "REVENUE", "ANNUAL")
    if not _annual(rev):
        return _result("S12", at, missing=["REVENUE_VALID_ANNUAL_PERIOD"])
    start, end = rev["period_start"], rev["period_end"]
    other = {m: _one(rows, m, "ANNUAL", end, start)
             for m in ("NET_INCOME", "OPERATING_CASH_FLOW", "CAPEX")}
    inputs = [rev, *other.values()]
    missing = [m + "_SAME_FY" for m, r in other.items() if r is None]
    if missing:
        return _result("S12", at, missing=missing, inputs=inputs, period=end)
    ni, cfo, capex = [float(other[m]["value"]) for m in ("NET_INCOME", "OPERATING_CASH_FLOW", "CAPEX")]
    revenue = float(rev["value"])
    if revenue <= 0:
        return _result("S12", at, missing=["POSITIVE_REVENUE"], inputs=inputs, period=end)
    fcf = cfo - abs(capex)
    ocfm, fcfm = cfo / revenue, fcf / revenue
    q_ocfm = piecewise_score(ocfm, [(0, 0), (.05, 40), (.10, 60), (.20, 85), (.30, 100)])
    q_fcfm = piecewise_score(fcfm, [(0, 0), (.05, 45), (.10, 65), (.15, 80), (.25, 100)])
    components = {"fcf": fcf, "ocf_margin": ocfm, "fcf_margin": fcfm,
                  "Q_OCFM": q_ocfm, "Q_FCFM": q_fcfm,
                  "normalization": "EXPLICIT_ABSOLUTE_FALLBACK_NO_PEER_COHORT"}
    if ni <= 0:
        # Source permits N/A reweighting. Keep this a partial diagnostic, never a full model.
        components["partial_diagnostic_score"] = (.20 * q_ocfm + .15 * q_fcfm) / .35
        return _result("S12", at, missing=["CCR_POSITIVE_NET_INCOME", "FCFCR_POSITIVE_NET_INCOME"],
                       inputs=inputs, period=end, components=components, status="PARTIAL")
    ccr, fcfcr = cfo / ni, fcf / ni
    q_ccr = piecewise_score(ccr, [(0, 0), (.5, 40), (.8, 70), (1, 90), (1.2, 100)])
    q_fcfcr = piecewise_score(fcfcr, [(0, 0), (.4, 35), (.7, 65), (1, 90), (1.2, 100)])
    components.update({"ccr": ccr, "fcfcr": fcfcr, "Q_CCR": q_ccr, "Q_FCFCR": q_fcfcr})
    score = .35 * q_ccr + .30 * q_fcfcr + .20 * q_ocfm + .15 * q_fcfm
    return _result("S12", at, score=score, inputs=inputs, period=end, components=components)


def compute_quality(facts, at):
    """Return the six recovered S14 legs; only complete S7/S12 score numerically.

    Facts must describe one issuer. No cached score, guessed peer set, missing
    evidence or synthetic defaults can satisfy the four other model contracts.
    """
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("Offset-aware research as_of is required")
    facts = list(facts)
    for key in ("security_id", "ticker"):
        identities = {r[key] for r in facts if r.get(key)}
        if len(identities) > 1:
            raise ValueError("Mixed issuer facts are not allowed")
    rows = [r for r in facts if _valid(r, at)]
    results = {model: _result(model, at, missing=meta["missing"])
               for model, meta in CONTRACTS.items()}
    results["S7"] = _s7(rows, at)
    results["S12"] = _s12(rows, at)
    return results
