"""B_Q source-assessed Beneish research with individually usable risk legs.

No missing accounting fact, debt proxy or combined D&A tag is imputed.  A
complete numeric score is delegated to the source-pinned recovered formula;
even that score is research-only and never constitutes canonical PIT acceptance.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
import hashlib
import json
import math
import re
from urllib.parse import urlsplit

from app import recovered_beneish
from app.recovered_quality import SOURCE_SHA256


METHOD_VERSION = "PERSONAL_RESEARCH_BENEISH_AI_ASSESSED_V1.0"
RISK_LEGS = ("DSRI", "GMI", "AQI", "DEPI", "SGAI", "LVGI", "TATA")
_ALL_ALIASES = frozenset(name for group in recovered_beneish.ALIAS.values() for name in group)
_ALLOWED_SOURCES = {"SEC_EDGAR", "SEC_EDGAR_LOCAL_ARCHIVE_ACCEPTED_UNVERIFIED"}
_COMBINED_DEPRECIATION = {
    "DEPRECIATION_AND_AMORTIZATION", "DEPRECIATION_DEPLETION_AND_AMORTIZATION",
    "DEPRECIATIONDEPLETIONANDAMORTIZATION", "DEPRECIATIONAMORTIZATIONANDACCRETIONNET",
    "DEPRECIATION_AMORTIZATION", "D_AND_A", "D&A",
}
_REQUIRES = {
    "DSRI": (("AR", "t"), ("SALES", "t"), ("AR", "prev"), ("SALES", "prev")),
    "GMI": (("SALES", "t"), ("COGS", "t"), ("SALES", "prev"), ("COGS", "prev")),
    "AQI": (("CA", "t"), ("PPE", "t"), ("TA", "t"),
            ("CA", "prev"), ("PPE", "prev"), ("TA", "prev")),
    "DEPI": (("DEP", "t"), ("PPE", "t"), ("DEP", "prev"), ("PPE", "prev")),
    "SGAI": (("SGA", "t"), ("SALES", "t"), ("SGA", "prev"), ("SALES", "prev")),
    "LVGI": (("DEBT", "t"), ("TA", "t"), ("DEBT", "prev"), ("TA", "prev")),
    "TATA": (("NI", "t"), ("CFO", "t"), ("TA", "t")),
}
_RISK_PARAMETERS = {
    "DSRI": (1, .50), "GMI": (1, .30), "AQI": (1, .50),
    "DEPI": (1, .75), "SGAI": (1, .40), "LVGI": (1, .60),
}
_WEIGHTS = {"DSRI": 2, "GMI": 1.5, "AQI": 2, "DEPI": 1,
            "SGAI": 1, "LVGI": 1.5, "TATA": 3}
_EVIDENCE_FIELDS = (
    "metric", "value", "unit", "period_kind", "period_start", "period_end",
    "source", "source_ref", "accession", "evidence_hash", "form_type",
    "filing_date", "available_at", "scenario_provenance",
)


class _InvalidRatio(ArithmeticError):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _divide(numerator, denominator):
    """Same positive-denominator convention as recovered_beneish._safe_ratio."""
    if denominator <= 0:
        if numerator == 0 and denominator == 0:
            raise _InvalidRatio("SPEC_EDGE_CASE_ZERO_OVER_ZERO")
        raise _InvalidRatio("VALID_POSITIVE_BENEISH_DENOMINATORS")
    result = numerator / denominator
    if not math.isfinite(result):
        raise _InvalidRatio("FINITE_BENEISH_RATIO")
    return result


def _date(value):
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def _scenario_ok(scenario):
    return (isinstance(scenario, dict) and
            isinstance(scenario.get("id"), str) and bool(scenario["id"].strip()) and
            isinstance(scenario.get("basis"), str) and bool(scenario["basis"].strip()))


def _check_row(row):
    """Validate facts before passing them to the unchanged frozen calculator."""
    if not isinstance(row, dict):
        return "INVALID_FACT"
    metric = row.get("metric")
    if metric not in _ALL_ALIASES:
        return "UNSUPPORTED_METRIC_CLASSIFICATION"
    original = row.get("original_metric", row.get("raw_metric", metric))
    if original in _COMBINED_DEPRECIATION and metric in recovered_beneish.ALIAS["DEP"]:
        return "COMBINED_D_AND_A_IS_NOT_PURE_DEPRECIATION"
    if original != metric and not _scenario_ok(row.get("scenario_provenance")):
        return "ALTERNATE_CLASSIFICATION_REQUIRES_SCENARIO_PROVENANCE"
    source = row.get("source")
    if source not in _ALLOWED_SOURCES:
        return "OFFICIAL_SEC_SOURCE_REQUIRED"
    if source != "SEC_EDGAR" and not _scenario_ok(row.get("scenario_provenance")):
        return "ALTERNATE_SOURCE_REQUIRES_SCENARIO_PROVENANCE"
    uri = row.get("source_ref")
    if not isinstance(uri, str) or not uri.strip():
        return "SOURCE_REF_REQUIRED"
    if source == "SEC_EDGAR":
        url = urlsplit(uri)
        if url.scheme != "https" or url.hostname not in {"sec.gov", "www.sec.gov", "data.sec.gov"}:
            return "OFFICIAL_SEC_SOURCE_REF_REQUIRED"
    if not isinstance(row.get("accession"), str) or not row["accession"].strip():
        return "SEC_ACCESSION_REQUIRED"
    if not re.fullmatch(r"[0-9a-fA-F]{64}", str(row.get("evidence_hash", ""))):
        return "SHA256_EVIDENCE_REQUIRED"
    if row.get("unit") != "USD" or row.get("form_type") != "10-K":
        return "USD_TEN_K_SOURCE_REQUIRED"
    kind = row.get("period_kind")
    end = _date(row.get("period_end"))
    start = _date(row.get("period_start"))
    if kind not in {"ANNUAL", "INSTANT"} or end is None:
        return "VALID_PERIOD_REQUIRED"
    if kind == "ANNUAL" and (start is None or not 330 <= (end - start).days + 1 <= 400):
        return "EXACT_ANNUAL_FISCAL_SPAN_REQUIRED"
    if kind == "INSTANT" and start is not None:
        return "INSTANT_PERIOD_START_MUST_BE_EMPTY"
    filing = _date(row.get("filing_date"))
    try:
        available = datetime.fromisoformat(str(row.get("available_at", "")).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return "OFFSET_AWARE_AVAILABLE_AT_REQUIRED"
    if filing is None or available.tzinfo is None or available.utcoffset() is None:
        return "DATED_SEC_AVAILABILITY_REQUIRED"
    if filing < end or available.date() < filing:
        return "CONSISTENT_SOURCE_DATES_REQUIRED"
    value = row.get("value")
    if isinstance(value, bool):
        return "FINITE_NUMERIC_VALUE_REQUIRED"
    try:
        if not math.isfinite(float(value)):
            return "FINITE_NUMERIC_VALUE_REQUIRED"
    except (ValueError, TypeError, OverflowError):
        return "FINITE_NUMERIC_VALUE_REQUIRED"
    return None


def _source(row):
    return {key: row.get(key) for key in _EVIDENCE_FIELDS if row.get(key) is not None}


def _pick(rows, key, when, period_end, period_start):
    kind = "ANNUAL" if key in recovered_beneish.FLOWS else "INSTANT"
    candidates = [r for r in rows if r["metric"] in recovered_beneish.ALIAS[key]
                  and r["period_kind"] == kind and r["period_end"] == period_end
                  and (kind == "INSTANT" or r["period_start"] == period_start)]
    if not candidates:
        return None, f"{key}_{when.upper()}_EXACT_FY"
    # Reproduce the recovered helper's ordering and same-snapshot conflict rule.
    latest = max(r["available_at"] for r in candidates)
    ties = [r for r in candidates if r["available_at"] == latest]
    if len({float(r["value"]) for r in ties}) != 1:
        return None, f"{key}_{when.upper()}_CONFLICTING_EVIDENCE"
    return max(ties, key=lambda r: (r["metric"], r["accession"])), None


def _calculate_leg(name, facts):
    v = lambda key, when: float(facts[(key, when)]["value"])
    if name == "DSRI":
        return _divide(_divide(v("AR", "t"), v("SALES", "t")),
                       _divide(v("AR", "prev"), v("SALES", "prev")))
    if name == "GMI":
        return _divide(_divide(v("SALES", "prev") - v("COGS", "prev"), v("SALES", "prev")),
                       _divide(v("SALES", "t") - v("COGS", "t"), v("SALES", "t")))
    if name == "AQI":
        if min(v("TA", "t"), v("TA", "prev")) <= 0:
            raise _InvalidRatio("POSITIVE_TOTAL_ASSETS_REQUIRED")
        return _divide(1 - (v("CA", "t") + v("PPE", "t")) / v("TA", "t"),
                       1 - (v("CA", "prev") + v("PPE", "prev")) / v("TA", "prev"))
    if name == "DEPI":
        if min(v("DEP", "t"), v("DEP", "prev"), v("PPE", "t"), v("PPE", "prev")) <= 0:
            raise _InvalidRatio("PURE_POSITIVE_DEPRECIATION_AND_PPE_REQUIRED")
        return _divide(_divide(v("DEP", "prev"), v("DEP", "prev") + v("PPE", "prev")),
                       _divide(v("DEP", "t"), v("DEP", "t") + v("PPE", "t")))
    if name == "SGAI":
        return _divide(_divide(v("SGA", "t"), v("SALES", "t")),
                       _divide(v("SGA", "prev"), v("SALES", "prev")))
    if name == "LVGI":
        if min(v("TA", "t"), v("TA", "prev")) <= 0:
            raise _InvalidRatio("POSITIVE_TOTAL_ASSETS_REQUIRED")
        return _divide(_divide(v("DEBT", "t"), v("TA", "t")),
                       _divide(v("DEBT", "prev"), v("TA", "prev")))
    if name == "TATA":
        return _divide(v("NI", "t") - v("CFO", "t"), v("TA", "t"))
    raise ValueError(name)


def _risk(name, ratio):
    if name == "TATA":
        return min(1.0, max(0.0, ratio / .10))
    midpoint, width = _RISK_PARAMETERS[name]
    return recovered_beneish._risk(ratio, midpoint, width)


def _sourced_forensic_review(review):
    """Do not pass malformed evidence receipts through looser frozen checks."""
    if not isinstance(review, dict) or review.get("review_complete") is not True:
        return False
    flags = review.get("serious_flags")
    if not isinstance(flags, list):
        return False
    ids = []
    for flag in flags:
        if (not isinstance(flag, dict) or not isinstance(flag.get("id"), str)
                or not flag["id"].strip() or not isinstance(flag.get("source_ref"), str)
                or not flag["source_ref"].strip()
                or not re.fullmatch(r"[0-9a-fA-F]{64}", str(flag.get("evidence_hash", "")))):
            return False
        ids.append(flag["id"])
    return len(ids) == len(set(ids))


def analyze_beneish(rows, period_end, period_start, forensic_review=None):
    """Assess seven Beneish legs; compute B_Q only through the frozen formula.

    Args:
        rows: SEC-backed normalized annual/instant facts for a single issuer.
        period_end/period_start: exact current fiscal-year boundaries (ISO dates).
        forensic_review: sourced independent review packet for original B_Q.

    Returns a deterministic research-only dict. `risks` never assigns zero for
    an unresolved risk; `score` remains None until all frozen gates pass.
    """
    end, start = _date(period_end), _date(period_start)
    if end is None or start is None or end < start:
        raise ValueError("Valid ISO fiscal period_end and period_start are required")
    if isinstance(rows, (str, bytes)):
        raise TypeError("rows must be normalized SEC evidence mappings")
    facts = list(rows)
    identity = {(key, str(r[key])) for r in facts if isinstance(r, dict)
                for key in ("security_id", "ticker") if r.get(key)}
    for key in ("security_id", "ticker"):
        if len({value for field, value in identity if field == key}) > 1:
            raise ValueError("Mixed-issuer SEC evidence cannot be combined")

    clean, rejected = [], []
    for row in facts:
        reason = _check_row(row)
        if reason:
            if not isinstance(row, dict) or row.get("metric") in _ALL_ALIASES or row.get("metric") in _COMBINED_DEPRECIATION:
                rejected.append({"metric": row.get("metric") if isinstance(row, dict) else None,
                                 "period_end": row.get("period_end") if isinstance(row, dict) else None,
                                 "reason": reason})
        else:
            clean.append(row)

    previous_end = (date(end.year - 1, 2, 28) if end.month == 2 and end.day == 29
                    else end.replace(year=end.year - 1))
    contiguous = start - timedelta(days=1) == previous_end
    previous_revenue = [r for r in clean if r["metric"] in recovered_beneish.ALIAS["SALES"]
                        and r["period_kind"] == "ANNUAL" and r["period_end"] == previous_end.isoformat()]
    previous_starts = {r["period_start"] for r in previous_revenue}
    previous_start = next(iter(previous_starts)) if len(previous_starts) == 1 else None

    selected, lookup_errors = {}, {}
    if contiguous:
        for when, fy_end, fy_start in (("t", period_end, period_start),
                                       ("prev", previous_end.isoformat(), previous_start)):
            for field in recovered_beneish.ALIAS:
                if when == "prev" and field in {"NI", "CFO"}:
                    continue
                if field in recovered_beneish.FLOWS and fy_start is None:
                    lookup_errors[(field, when)] = f"{field}_{when.upper()}_EXACT_FY"
                    continue
                picked, reason = _pick(clean, field, when, fy_end, fy_start)
                if picked is None:
                    lookup_errors[(field, when)] = reason
                else:
                    selected[(field, when)] = picked

    ratios = {name: None for name in RISK_LEGS}
    risks = {name: None for name in RISK_LEGS}
    results, missing = {}, []
    used = set()
    for leg in RISK_LEGS:
        dependencies = _REQUIRES[leg]
        errors = (["CONTIGUOUS_PRIOR_FISCAL_YEAR"] if not contiguous else
                  [lookup_errors[dep] for dep in dependencies if dep in lookup_errors])
        selected_rows = [selected[dep] for dep in dependencies if dep in selected]
        evidence = [_source(r) for r in selected_rows]
        used.update(dep for dep in dependencies if dep in selected)
        ratio = risk = None
        if not errors:
            try:
                ratio = _calculate_leg(leg, selected)
                if not math.isfinite(ratio):
                    raise _InvalidRatio("FINITE_BENEISH_RATIO")
                risk = _risk(leg, ratio)
            except (_InvalidRatio, ZeroDivisionError, OverflowError) as exc:
                errors.append(exc.reason if isinstance(exc, _InvalidRatio)
                              else "VALID_POSITIVE_BENEISH_DENOMINATORS")
        ratios[leg], risks[leg] = ratio, risk
        results[leg] = {"status": "CALCULATED" if risk is not None else "UNRESOLVED",
                        "ratio": ratio, "risk": risk, "weight": _WEIGHTS[leg],
                        "weighted_risk": risk * _WEIGHTS[leg] if risk is not None else None,
                        "missing": list(dict.fromkeys(errors)), "source_evidence": evidence}
        missing.extend(errors)

    sg_ratio, sg_error = None, None
    if ("SALES", "t") in selected and ("SALES", "prev") in selected:
        try:
            sg_ratio = _divide(float(selected[("SALES", "t")]["value"]),
                               float(selected[("SALES", "prev")]["value"]))
        except _InvalidRatio as exc:
            sg_error = exc.reason
    if sg_error:
        missing.append(sg_error)

    # Always query the frozen source on the complete, screened evidence set;
    # this is the sole authority for the full original score and interaction.
    verified_review = forensic_review if _sourced_forensic_review(forensic_review) else None
    original_score, original_components, original_inputs, original_missing = (
        recovered_beneish.calculate_beneish(clean, period_end, period_start, verified_review))
    missing.extend(original_missing)
    if original_score is not None:
        for leg in RISK_LEGS:
            frozen_ratio = original_components["ratios"][leg]
            frozen_risk = original_components["risks"][leg]
            if (ratios[leg] is None or risks[leg] is None or
                    not math.isclose(ratios[leg], frozen_ratio, rel_tol=1e-12, abs_tol=1e-12) or
                    not math.isclose(risks[leg], frozen_risk, rel_tol=1e-12, abs_tol=1e-12)):
                raise AssertionError(f"{leg} differs from frozen Beneish source")
    else:
        if verified_review is None:
            missing.append("INDEPENDENT_SERIOUS_FLAGS_REVIEW_COMPLETE")

    # Scenario records remain expressly identifiable even if the full frozen
    # formula can be executed on their screened SEC archive facts.
    evidence_used = {(_source(row)["metric"], _source(row)["period_end"],
                      _source(row)["evidence_hash"]): _source(row)
                     for row in original_inputs}
    for dep in used:
        row = selected[dep]
        evidence_used[(row["metric"], row["period_end"], row["evidence_hash"])] = _source(row)
    scenarios = [evidence["scenario_provenance"] for evidence in evidence_used.values()
                 if _scenario_ok(evidence.get("scenario_provenance"))]
    valid_risk_count = sum(value is not None for value in risks.values())
    if original_score is not None:
        status, result_type, original_status = (
            ("SCENARIO_COMPLETE", "FROZEN_FORMULA_ON_SOURCE_SCENARIO", "CALCULATED_ON_SCENARIO")
            if scenarios else ("COMPLETE", "FROZEN_EXACT", "CALCULATED"))
        missing = []
    else:
        status = "PARTIAL" if valid_risk_count else "UNRESOLVED"
        result_type, original_status = ("COMPONENT_RISKS_ONLY" if valid_risk_count else "UNAVAILABLE",
                                        "UNRESOLVED")
    result = {
        "model": "B_Q", "method_version": METHOD_VERSION,
        "status": status, "score": original_score,
        "numeric_result_type": result_type, "original_status": original_status,
        "canonical_accepted": False, "scope": "PERSONAL_RESEARCH_ONLY_NOT_CANONICAL_PIT",
        "period_end": period_end, "period_start": period_start,
        "previous_period_end": previous_end.isoformat(), "previous_period_start": previous_start,
        "ratios": ratios, "risks": risks, "results": results, "components": results,
        "calculated_risks": valid_risk_count, "required_risks": len(RISK_LEGS),
        "weighted_component_risk_partial": (
            sum(results[leg]["weighted_risk"] for leg in RISK_LEGS if risks[leg] is not None)
            if valid_risk_count else None),
        "sales_growth_index": sg_ratio,
        "interaction_risk": original_components.get("interaction_risk") if original_score is not None else None,
        "original_components": original_components if original_score is not None else None,
        "missing": list(dict.fromkeys(missing)),
        "source_evidence": {
            "contract": "recovered_beneish.calculate_beneish",
            "recovered_quality_contract_sha256": SOURCE_SHA256,
            "source_rows": [evidence_used[key] for key in sorted(evidence_used)],
            "rejected_rows": rejected,
            "scenarios": scenarios,
            "available_at_is_not_historical_pit_proof": True,
            "independent_forensic_review_supplied": forensic_review is not None,
            "forensic_review_evidence_valid": verified_review is not None,
        },
    }
    # Stable offline receipt identifying the exact source facts and disposition;
    # hash is reproducible and is intentionally not a digital signature.
    result["receipt_sha256"] = hashlib.sha256(json.dumps(
        result, sort_keys=True, separators=(",", ":"), default=str,
        allow_nan=False).encode("utf-8")).hexdigest()
    return result
