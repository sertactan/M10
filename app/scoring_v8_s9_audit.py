"""Evidence-first FY2025 S9 diagnostic for INOD and CRMD.

This reuses V7's exact-accession Companyfacts selector and frozen 9-signal
semantics, but refuses a full score until long-term debt is proven for both
years. The original V7 three-company score implementation is unchanged.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, localcontext
from hashlib import sha256
import json

from app.scoring_v7_piotroski import _entry

PILOTS = {
    "INOD": dict(cik="0000903651", fy="2025-12-31", prior="2024-12-31",
                 begin="2023-12-31", current="0001104659-26-020655",
                 previous="0001410578-25-000194",
                 revenue="RevenueFromContractWithCustomerExcludingAssessedTax"),
    "CRMD": dict(cik="0001410098", fy="2025-12-31", prior="2024-12-31",
                 begin="2023-12-31", current="0001213900-26-023889",
                 previous="0001013762-25-001852", revenue="Revenues"),
}

# Pins from previously accepted SEC bulk/filing caches, cross-checked on V8.
# They prevent changing source facts and simply re-sealing an invented audit.
SOURCE_PINS = {
    "INOD": {"companyfacts":"6ccc9dcc93b9c303cee51c166f345350fb16258408c884e2ed5d1231f2741b38",
        "submissions":"070461656ae36691ad952bd53e529dd48fbb74b8f7191637d3c6bb79e27910f3",
        "body":"2d5dd7f964d0239ea18a982f24e077d1b8e0f08baa73fd28dd66f539d9befba2",
        "issuer":"innodata"},
    "CRMD": {"companyfacts":"b75757faacc84388fbe591a3ec2593969ffefe3c9ea86056a188a6fcb0c2f8bb",
        "submissions":"3a7214421e9ce0addd9b96cb1e6e554ed92f5e6d6b6d5f669bb6cf4177ca143f",
        "body":"8c0d3d8e015ca200773b6612cb3d3e773cbedd9cc03b2bb7b58b02e56128b500",
        "issuer":"cormedix"},
}

COMPONENTS = {
    "net_income_2025": ("NetIncomeLoss", "current", "fy", True),
    "net_income_2024": ("NetIncomeLoss", "current", "prior", True),
    "cash_operations_2025": ("NetCashProvidedByUsedInOperatingActivities", "current", "fy", True),
    "assets_2025": ("Assets", "current", "fy", False),
    "assets_2024": ("Assets", "current", "prior", False),
    "assets_2023": ("Assets", "previous", "begin", False),
    "current_assets_2025": ("AssetsCurrent", "current", "fy", False),
    "current_assets_2024": ("AssetsCurrent", "current", "prior", False),
    "current_liabilities_2025": ("LiabilitiesCurrent", "current", "fy", False),
    "current_liabilities_2024": ("LiabilitiesCurrent", "current", "prior", False),
    "gross_profit_2025": ("GrossProfit", "current", "fy", True),
    "gross_profit_2024": ("GrossProfit", "current", "prior", True),
}


def _filing_meta(submissions_raw: bytes, cfg: dict, accession: str, end: str) -> dict:
    """SEC's filed dates/acceptance, separate from provider as-of availability."""
    payload = json.loads(submissions_raw)
    if str(payload.get("cik", "")).zfill(10) != cfg["cik"]:
        raise ValueError("SUBMISSIONS_CIK_MISMATCH")
    recent = payload["filings"]["recent"]
    required = ("accessionNumber", "form", "reportDate", "filingDate",
                "acceptanceDateTime", "primaryDocument")
    if len({len(recent[k]) for k in required}) != 1:
        raise ValueError("SUBMISSIONS_PARALLEL_ARRAY_MISMATCH")
    matches = [i for i, v in enumerate(recent["accessionNumber"]) if v == accession]
    if len(matches) != 1:
        raise ValueError("SEC_ACCESSION_MISSING_OR_DUPLICATE:" + accession)
    i = matches[0]
    if recent["form"][i] != "10-K" or recent["reportDate"][i] != end:
        raise ValueError("FISCAL_FORM_OR_PERIOD_MISMATCH:" + accession)
    accepted = datetime.fromisoformat(recent["acceptanceDateTime"][i].replace("Z", "+00:00"))
    filed = date.fromisoformat(recent["filingDate"][i])
    if (accepted.tzinfo is None or accepted.astimezone(timezone.utc).date() < filed
            or filed <= date.fromisoformat(end)):
        raise ValueError("SEC_ACCEPTANCE_OR_FILED_DATE_INVALID")
    return {"accession": accession, "period_end": end, "form": "10-K",
            "filed_on": recent["filingDate"][i],
            "sec_accepted_at": recent["acceptanceDateTime"][i],
            "primary_document": recent["primaryDocument"][i]}


def _row(facts: dict, tag: str, acc: str, end: str, flow: bool):
    row = _entry(facts, tag, acc, end, flow=flow)
    if row is None:
        return None
    if row["unit"] != "USD":
        raise ValueError("S9_EXPECTED_USD_UNIT:" + tag)
    if flow and row["start"] != str(int(end[:4])) + "-01-01":
        raise ValueError("S9_NON_CALENDAR_FISCAL_FLOW:" + tag)
    return row


def audit_company(ticker: str, companyfacts_raw: bytes, submissions_raw: bytes,
                  *, filing_body: bytes | None = None) -> dict:
    """Reperform genuinely evidenced factors; no speculative complete score."""
    cfg = PILOTS[ticker]
    current_meta = _filing_meta(submissions_raw, cfg, cfg["current"], cfg["fy"])
    prior_meta = _filing_meta(submissions_raw, cfg, cfg["previous"], cfg["prior"])
    payload = json.loads(companyfacts_raw)
    if str(payload.get("cik", "")).zfill(10) != cfg["cik"]:
        raise ValueError("COMPANYFACTS_CIK_MISMATCH")
    pins = SOURCE_PINS[ticker]
    if sha256(companyfacts_raw).hexdigest() != pins["companyfacts"]:
        raise ValueError("COMPANYFACTS_PINNED_SHA256_CHANGED")
    if sha256(submissions_raw).hexdigest() != pins["submissions"]:
        raise ValueError("SEC_SUBMISSIONS_PINNED_SHA256_CHANGED")
    if filing_body is not None:
        lower = filing_body.decode("utf8", errors="replace").lower()
        if (sha256(filing_body).hexdigest() != pins["body"]
                or pins["issuer"] not in lower or "form 10-k" not in lower):
            raise ValueError("OFFICIAL_FILING_BODY_SOURCE_IDENTITY_OR_SHA_CHANGED")
    facts = (payload.get("facts") or {}).get("us-gaap", {})
    inputs, missing = {}, []
    requirements = dict(COMPONENTS)
    requirements.update({
        "revenue_2025": (cfg["revenue"], "current", "fy", True),
        "revenue_2024": (cfg["revenue"], "current", "prior", True),
    })
    for name, (tag, accession_ref, end_ref, flow) in requirements.items():
        row = _row(facts, tag, cfg[accession_ref], cfg[end_ref], flow)
        if row is None:
            missing.append("SEC_EXACT_TAG_MISSING:" + name + ":" + tag)
        else:
            metadata = current_meta if accession_ref == "current" else prior_meta
            if row["filed"] != metadata["filed_on"]:
                raise ValueError("SEC_XBRL_FILED_DATE_MISMATCH:" + tag)
            inputs[name] = row
    # Positive stock-option exercises and capital issuance prove that the
    # Piotroski no-equity-offering test fails, including option exercises.
    issuance_tags = ("ProceedsFromIssuanceOfCommonStock", "StockIssuedDuringPeriodValueNewIssues",
                     "ProceedsFromStockOptionsExercised")
    issue_evidence = [r for tag in issuance_tags if
                      (r := _row(facts, tag, cfg["current"], cfg["fy"], True)) is not None
                      and Decimal(r["value"]) > 0]
    if not issue_evidence:
        missing.append("COMMON_EQUITY_ISSUANCE_NOT_DETERMINED")
    if any(row["filed"] != current_meta["filed_on"] for row in issue_evidence):
        raise ValueError("SEC_ISSUANCE_FILED_DATE_MISMATCH")
    # Frozen F-score leverage is long-term interest-bearing debt / average
    # total assets. Unreported debt taxonomy must not be silently zeroed.
    # Existing INOD/CRMD balance sheets lack proved, comparable FY2024/FY2025
    # debt classifications; these remain explicit accounting blockers.
    debt_tags = ("LongTermDebt", "LongTermDebtNoncurrent", "ConvertibleDebtNoncurrent",
                 "OtherLongTermDebtNoncurrent", "LongTermDebtCurrent")
    debt_evidence = {}
    for year in ("2025", "2024"):
        selected = {tag: row for tag in debt_tags if
                    (row := _row(facts, tag, cfg["current"], cfg["fy" if year == "2025" else "prior"], False))}
        debt_evidence[year] = selected
        if any(row["filed"] != current_meta["filed_on"] for row in selected.values()):
            raise ValueError("SEC_DEBT_FILED_DATE_MISMATCH")
        if not selected:
            missing.append("LONG_TERM_DEBT_ACCOUNTING_CLASS_NOT_PROVEN:" + year)
    # Multiple debt concepts can overlap (parent + child), so having some
    # facts does not establish an exhaustive, non-overlapping debt total.
    missing.append("LONG_TERM_DEBT_COMPLETE_NONOVERLAPPING_MAPPING_NOT_VERIFIED")
    signals = {name: None for name in (
        "F_ROA", "F_CFO", "F_DELTA_ROA", "F_ACCRUAL", "F_DELTA_LEVERAGE",
        "F_DELTA_LIQUIDITY", "F_NO_COMMON_EQUITY_ISSUANCE",
        "F_DELTA_GROSS_MARGIN", "F_DELTA_ASSET_TURNOVER")}
    if issue_evidence:
        signals["F_NO_COMMON_EQUITY_ISSUANCE"] = 0
    needed = [name for name in requirements if name in inputs]
    if len(needed) == len(requirements):
        with localcontext() as ctx:
            ctx.prec = 60
            D = lambda name: Decimal(inputs[name]["value"])
            a0, a1, a2 = D("assets_2025"), D("assets_2024"), D("assets_2023")
            r0, r1 = D("revenue_2025"), D("revenue_2024")
            cl0, cl1 = D("current_liabilities_2025"), D("current_liabilities_2024")
            if min(a0,a1,a2,r0,r1,cl0,cl1) <= 0:
                missing.append("S9_REQUIRED_POSITIVE_DENOMINATOR_FAILED")
            else:
                n0, n1 = D("net_income_2025"), D("net_income_2024")
                cf = D("cash_operations_2025")
                signals.update({
                    "F_ROA": int(n0 / a1 > 0),
                    "F_CFO": int(cf > 0),
                    "F_DELTA_ROA": int(n0 / a1 > n1 / a2),
                    "F_ACCRUAL": int(cf > n0),
                    "F_DELTA_LIQUIDITY": int(D("current_assets_2025")/cl0 > D("current_assets_2024")/cl1),
                    "F_DELTA_GROSS_MARGIN": int(D("gross_profit_2025")/r0 > D("gross_profit_2024")/r1),
                    "F_DELTA_ASSET_TURNOVER": int(r0 / ((a0+a1)/2) > r1 / ((a1+a2)/2)),
                })
    # GrossProfit is the filed numerator of Piotroski gross margin. CostOfRevenue
    # can be a component instead of total costs, particularly for CRMD.
    cost_reconciliation = {}
    for year, end_ref in (("2025", "fy"), ("2024", "prior")):
        cost_tag = "DirectOperatingCosts" if ticker == "INOD" else "CostOfRevenue"
        cost = _row(facts, cost_tag, cfg["current"], cfg[end_ref], True)
        if not cost or "revenue_"+year not in inputs or "gross_profit_"+year not in inputs:
            missing.append("S9_ORIGINAL_GROSS_MARGIN_COST_PROOF_MISSING:" + year)
            continue
        if cost["filed"] != current_meta["filed_on"]:
            raise ValueError("SEC_GROSS_MARGIN_FILED_DATE_MISMATCH")
        residual = Decimal(inputs["revenue_"+year]["value"]) - Decimal(inputs["gross_profit_"+year]["value"]) - Decimal(cost["value"])
        cost_reconciliation[year] = {"residual_USD": str(residual), "cost_fact": cost,
            "classification": "COST_TAG_INCOMPLETE_FOR_GROSS_MARGIN" if residual else "RECONCILED"}
        if residual:
            missing.append("S9_ORIGINAL_GROSS_MARGIN_COST_RECONCILIATION_FAILED:" + year)
    # V7 frozen implementation uses (revenue - COGS) / revenue. A filed
    # GrossProfit fact alone cannot substitute where the tagged cost does not
    # reconcile. INOD's two DirectOperatingCosts observations reconcile;
    # CRMD's CostOfRevenue leaves an unexplained residual in each year.
    if set(cost_reconciliation) == {"2025", "2024"} and all(
            item["residual_USD"] == "0" for item in cost_reconciliation.values()):
        with localcontext() as ctx:
            ctx.prec = 60
            r0, r1 = (Decimal(inputs["revenue_"+year]["value"]) for year in ("2025","2024"))
            c0, c1 = (Decimal(cost_reconciliation[year]["cost_fact"]["value"]) for year in ("2025","2024"))
            if min(r0, r1) > 0:
                signals["F_DELTA_GROSS_MARGIN"] = int((r0-c0)/r0 > (r1-c1)/r1)
            else:
                signals["F_DELTA_GROSS_MARGIN"] = None
    else:
        signals["F_DELTA_GROSS_MARGIN"] = None
    # Partial factor counts are diagnostic, never a scaled score.
    result = {"ticker": ticker, "cik": cfg["cik"], "period_end": cfg["fy"],
              "status": "DATA_MISSING", "model": "S9", "score": None,
              "signal_count": None, "scope": "CURRENT_RESEARCH_ONLY",
              "canonical_accepted": False, "historical_pit_accepted": False,
              "source_companyfacts_sha256": sha256(companyfacts_raw).hexdigest(),
              "source_submissions_sha256": sha256(submissions_raw).hexdigest(),
              "current_filing": current_meta, "prior_filing": prior_meta,
              "inputs": inputs, "positive_issuance_evidence": issue_evidence,
              "debt_evidence": debt_evidence, "signals_partial": signals,
              "signals_verified": sum(s is not None for s in signals.values()),
              "gross_margin_cost_reconciliation": cost_reconciliation,
              "missing": sorted(set(missing)),
              "note": "Do not assign a Piotroski 9-signal score from eight known signals"}
    if filing_body is not None:
        result["source_official_10k_body_sha256"] = sha256(filing_body).hexdigest()
    else:
        result["missing"].append("OFFICIAL_10K_CURRENT_BODY_MISSING")
    return result
