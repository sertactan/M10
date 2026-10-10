"""Source-pinned Beneish component quality, with strict source and review gates.

The seven risk equations and 13-point normalization come from the recovered
S1–S14 specification, lines 1015–1176 and 1851–1866. This module neither
infers an absent XBRL concept nor assumes no independently serious flags exist.
"""
from __future__ import annotations

from datetime import date, timedelta
import math


ALIAS = {
    "AR": ("ACCOUNTS_RECEIVABLE_NET", "RECEIVABLES_NET"),
    "SALES": ("REVENUE",),
    "COGS": ("COST_OF_REVENUE", "COGS"),
    "CA": ("CURRENT_ASSETS",),
    "PPE": ("PPE_NET", "PROPERTY_PLANT_EQUIPMENT_NET"),
    "TA": ("ASSETS", "TOTAL_ASSETS"),
    "DEP": ("DEPRECIATION", "DEPRECIATION_EXPENSE"),
    "SGA": ("SG_AND_A", "SGA"),
    "DEBT": ("TOTAL_DEBT",),
    "NI": ("NET_INCOME",),
    "CFO": ("OPERATING_CASH_FLOW",),
}
FLOWS = frozenset(("SALES", "COGS", "DEP", "SGA", "NI", "CFO"))


def _pick(rows, names, kind, end, start=None):
    matches = [r for r in rows if r.get("metric") in names
               and r.get("period_kind") == kind and r.get("period_end") == end
               and (kind == "INSTANT" or r.get("period_start") == start)]
    if not matches:
        return None
    latest = max(r["available_at"] for r in matches)
    tied = [r for r in matches if r["available_at"] == latest]
    # Aliases in one snapshot must have identical reported amounts.
    if len({float(r["value"]) for r in tied}) != 1:
        return None
    return max(tied, key=lambda r: (r["metric"], r["accession"]))


def _safe_ratio(numerator, denominator):
    if denominator <= 0:
        raise ArithmeticError("Beneish denominator must be positive")
    return numerator / denominator


def _risk(value, midpoint, width):
    return min(1.0, max(0.0, (value - midpoint) / width))


def calculate_beneish(rows, period_end, period_start, forensic_review=None):
    """Return score, sub-ratios, verified inputs and explicit missing fields.

    `rows` must already pass the issuer/SEC/source-time checks in recovered_quality.
    `forensic_review` is a documented independent finding, including a complete
    review of zero flags if none were found. Source references cannot be replaced
    with a simple unsubstantiated serious-flag count.
    """
    end = date.fromisoformat(period_end)
    prior_end = (end.replace(year=end.year - 1) if not (end.month == 2 and end.day == 29)
                 else date(end.year - 1, 2, 28)).isoformat()
    if date.fromisoformat(period_start) - timedelta(days=1) != date.fromisoformat(prior_end):
        return None, {"period_end": period_end}, [], ["CONTIGUOUS_PRIOR_FISCAL_YEAR"]
    periods = {"t": (period_end, period_start),
               "prev": (prior_end, None)}
    # The previous year's actual starting date comes from its annual revenue;
    # never assume a leap-year or 52/53-week fiscal-year duration.
    candidates = [r for r in rows if r.get("metric") in ALIAS["SALES"]
                  and r.get("period_kind") == "ANNUAL" and r.get("period_end") == prior_end]
    starts = {r.get("period_start") for r in candidates}
    if len(starts) == 1:
        periods["prev"] = (prior_end, next(iter(starts)))
    else:
        periods["prev"] = (prior_end, None)
    inputs, missing = {}, []
    for when, (fy_end, fy_start) in periods.items():
        for field, names in ALIAS.items():
            if when == "prev" and field in ("NI", "CFO"):
                continue
            row = (_pick(rows, names, "ANNUAL", fy_end, fy_start)
                   if field in FLOWS and fy_start else
                   _pick(rows, names, "INSTANT", fy_end)
                   if field not in FLOWS else None)
            if row is None:
                missing.append(f"{field}_{when.upper()}_EXACT_FY")
            else:
                inputs[(field, when)] = row
    ordered = [r for _, r in sorted(inputs.items())]
    if missing:
        return None, {"period_end": period_end}, ordered, missing
    get = lambda field, when: float(inputs[(field, when)]["value"])
    try:
        sales, old_sales = get("SALES", "t"), get("SALES", "prev")
        ar, old_ar = get("AR", "t"), get("AR", "prev")
        assets, old_assets = get("TA", "t"), get("TA", "prev")
        ppe, old_ppe = get("PPE", "t"), get("PPE", "prev")
        ca, old_ca = get("CA", "t"), get("CA", "prev")
        debt, old_debt = get("DEBT", "t"), get("DEBT", "prev")
        dep, old_dep = get("DEP", "t"), get("DEP", "prev")
        sga, old_sga = get("SGA", "t"), get("SGA", "prev")
        cogs, old_cogs = get("COGS", "t"), get("COGS", "prev")
        ratios = {
            "DSRI": _safe_ratio(_safe_ratio(ar, sales), _safe_ratio(old_ar, old_sales)),
            "GMI": _safe_ratio(_safe_ratio(old_sales - old_cogs, old_sales),
                               _safe_ratio(sales - cogs, sales)),
            "AQI": _safe_ratio(1 - (ca + ppe) / _safe_ratio(assets, 1),
                               1 - (old_ca + old_ppe) / _safe_ratio(old_assets, 1)),
            "DEPI": _safe_ratio(_safe_ratio(old_dep, old_dep + old_ppe),
                                _safe_ratio(dep, dep + ppe)),
            "SGAI": _safe_ratio(_safe_ratio(sga, sales), _safe_ratio(old_sga, old_sales)),
            "LVGI": _safe_ratio(_safe_ratio(debt, assets), _safe_ratio(old_debt, old_assets)),
            "TATA": (get("NI", "t") - get("CFO", "t")) / _safe_ratio(assets, 1),
            "SGI": _safe_ratio(sales, old_sales),
        }
        if min(assets, old_assets, old_ar, old_debt, old_dep, old_ppe,
               dep, ppe, old_sales, sales) <= 0:
            raise ArithmeticError("Nonpositive annual denominator or asset")
        if not all(math.isfinite(v) for v in ratios.values()):
            raise ArithmeticError("Nonfinite Beneish component")
    except (ArithmeticError, OverflowError, ZeroDivisionError):
        return None, {"period_end": period_end}, ordered, ["VALID_POSITIVE_BENEISH_DENOMINATORS"]
    risk = {"DSRI": _risk(ratios["DSRI"], 1, .50),
            "GMI": _risk(ratios["GMI"], 1, .30),
            "AQI": _risk(ratios["AQI"], 1, .50),
            "DEPI": _risk(ratios["DEPI"], 1, .75),
            "SGAI": _risk(ratios["SGAI"], 1, .40),
            "LVGI": _risk(ratios["LVGI"], 1, .60),
            "TATA": min(1.0, max(0.0, ratios["TATA"] / .10))}
    base = sum(risk[k] * weight for k, weight in
               (("DSRI", 2), ("GMI", 1.5), ("AQI", 2), ("DEPI", 1),
                ("SGAI", 1), ("LVGI", 1.5), ("TATA", 3)))
    components = {"ratios": ratios, "risks": risk, "weighted_component_risk": base,
                  "period_end": period_end}
    review = forensic_review if isinstance(forensic_review, dict) else {}
    flags = review.get("serious_flags")
    if review.get("review_complete") is not True or not isinstance(flags, list) or any(
        not isinstance(f, dict) or not f.get("id") or not f.get("source_ref")
        or not isinstance(f.get("evidence_hash"), str) or len(f["evidence_hash"]) != 64
        for f in flags
    ) or (isinstance(flags, list) and len({f["id"] for f in flags if isinstance(f, dict)}) != len(flags)):
        return None, components, ordered, ["INDEPENDENT_SERIOUS_FLAGS_REVIEW_COMPLETE"]
    interaction = (1.0 if len(flags) >= 3 else .5 if
                   ratios["SGI"] > 1.5 and sum(v > .6 for v in risk.values()) >= 2 else 0.0)
    total = base + interaction
    score = max(0.0, min(100.0, 100 * (1 - total / 13)))
    components.update(interaction_risk=interaction, component_risk=total,
                      independent_serious_flags=flags, forensic_review_scope=review.get("scope"),
                      normalization="SOURCE_CR_DIVIDED_BY_13")
    return score, components, ordered, []
