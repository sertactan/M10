"""CRMD FY2025 frozen V7 Piotroski S9: official 10-K statement reconciliation.

Offline and research-only.  All raw SEC sources must match independently pinned
hashes.  A full score requires nine original V7 gates, two annual SEC filings,
the audited cost-of-sales bridge and nonoverlapping debt statement evidence.
"""
from __future__ import annotations

from decimal import Decimal, localcontext
from hashlib import sha256
from html.parser import HTMLParser
import json
import re

from app.scoring_v7_piotroski import _independent_reference, MODEL_SOURCE_SHA256
from app.scoring_v8_s9_audit import audit_company, PILOTS, SOURCE_PINS

TICKER = "CRMD"
CURRENT_10K_URL = ("https://www.sec.gov/Archives/edgar/data/1410098/"
                   "000121390026023889/ea0278169-10k_cormedix.htm")
PRIOR_10K_URL = ("https://www.sec.gov/Archives/edgar/data/1410098/"
                 "000101376225001852/ea0234537-10k_cormedix.htm")
PRIOR_BODY_SHA256 = "0e81486909c550385c08553e5c37bf7de2bbff77c5ce3fdb8f6a1a276772a52a"
SCORE_VERSION = "M10_V9_CRMD_S9_ORIGINAL_V7_FROZEN_RESEARCH"


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, value: str) -> None:
        if value.strip():
            self.parts.append(value)


def _plain(raw: bytes) -> str:
    parser = _Text()
    parser.feed(raw.decode("utf-8", errors="replace"))
    return " ".join(" ".join(parser.parts).split())


def _require_pattern(text: str, expression: str, issue: str) -> re.Match:
    match = re.search(expression, text, re.I | re.S)
    if match is None:
        raise ValueError(issue)
    return match


def _ix_values(raw: bytes, *, label: str, concept: str,
               expected: tuple[tuple[str, str], ...]) -> dict[str, dict]:
    """Check actual displayed <tr> cells AND inline original USD scale=3."""
    html = raw.decode("utf-8", errors="replace")
    rows = re.findall(r"<tr\b[^>]*>.*?</tr>", html, flags=re.I | re.S)
    selected = [row for row in rows if
                re.search(r"<td\b[^>]*>\s*" + re.escape(label) + r"\s*</td>", row, re.I)]
    if len(selected) != 1:
        raise ValueError(f"CRMD_EXACT_AUDITED_ROW_AMBIGUOUS:{label}:{len(selected)}")
    items = []
    for props, shown in re.findall(
        r"<ix:nonFraction\b([^>]*)>([^<]+)</ix:nonFraction>", selected[0], flags=re.I
    ):
        def prop(key: str) -> str | None:
            m = re.search(r'\b' + key + r'="([^"]+)"', props, re.I)
            return m.group(1) if m else None
        if prop("name") != concept or prop("scale") != "3" or prop("unitRef").lower() != "usd":
            raise ValueError(f"CRMD_IX_TAG_SCALE_OR_UNIT_MISMATCH:{label}")
        raw_num = re.sub(r"[^0-9.-]", "", shown)
        if not raw_num:
            raise ValueError(f"CRMD_IX_NUMBER_MISSING:{label}")
        items.append({"context": prop("contextRef"), "shown": shown.strip(),
                      "USD": str(Decimal(raw_num) * 1000),
                      "concept": concept, "scale": 3})
    if [(i["context"], i["shown"]) for i in items] != list(expected):
        raise ValueError(f"CRMD_IX_YEAR_OR_AMOUNT_MISMATCH:{label}")
    return {year: items[ix] for ix, year in enumerate(("2025", "2024"))}


def gross_cost_proof(body_2025: bytes, body_2024: bytes, base: dict) -> dict:
    """Reconcile 2025 filing comparative operations to original 2024 10-K."""
    current = _plain(body_2025)
    prior = _plain(body_2024)
    _require_pattern(current,
        r"CONSOLIDATED STATEMENTS OF OPERATIONS AND COMPREHENSIVE\s+"
        r"INCOME \(LOSS\) \(In Thousands, Except Per Share Data\)\s+"
        r"December 31, 2025 2024.*?Total Revenues 311,709 43,472",
        "CRMD_FY2025_CONSOLIDATED_OPERATIONS_HEADER_MISSING")
    _require_pattern(current,
        r"Cost of sales \(exclusive of amortization of intangibles\)"
        r"\s+22,089\s+3,034\s+Amortization of intangibles"
        r"\s+13,872\s+156\s+Gross profit\s+275,748\s+40,282",
        "CRMD_FY2025_TWO_COMPONENT_COST_OF_SALES_NOT_EVIDENCED")
    _require_pattern(prior,
        r"CONSOLIDATED STATEMENTS OF OPERATIONS AND COMPREHENSIVE\s+"
        r"INCOME \(LOSS\).*?Net sales\s+\$?\s*43,472,170.*?"
        r"Cost of sales \(\s*3,190,534\s*\).*?"
        r"Gross profit\s+40,281,636",
        "CRMD_ORIGINAL_FY2024_SALES_COST_GROSS_NOT_EVIDENCED")
    cost = _ix_values(body_2025, label="Cost of sales (exclusive of amortization of intangibles)",
                      concept="us-gaap:CostOfRevenue",
                      expected=(("c0", "22,089"), ("c9", "3,034")))
    amort = _ix_values(body_2025, label="Amortization of intangibles",
                       concept="crmd:AmortizationOfIntangibles",
                       expected=(("c0", "13,872"), ("c9", "156")))
    reconciliation = {}
    inputs = base["inputs"]
    for year in ("2025", "2024"):
        sale = Decimal(inputs["revenue_" + year]["value"])
        gross = Decimal(inputs["gross_profit_" + year]["value"])
        reported_cost = Decimal(cost[year]["USD"])
        amort_cost = Decimal(amort[year]["USD"])
        total_cost = reported_cost + amort_cost
        if sale - total_cost != gross:
            raise ValueError("CRMD_FY" + year + "_COGS_GROSS_PROFIT_FAILED")
        reconciliation[year] = {
            "reported_cost_of_sales_excluding_intangible_USD": str(reported_cost),
            "custom_ix_intangible_amortization_USD": str(amort_cost),
            "total_original_v7_cogs_USD": str(total_cost),
            "gross_profit_USD": str(gross),
            "revenue_USD": str(sale),
            "original_2025_filing_ix": {"cost": cost[year], "amortization": amort[year]},
            "source": "FY2025_AUDITED_CONSOLIDATED_OPERATIONS_COMPARATIVE",
        }
    # FY2024 original 10-K reports full-dollar historical values, and corroborates
    # the FY2025 comparative thousand-dollar presentation, with rounding.
    if (Decimal("43472170") - Decimal("3190534") != Decimal("40281636")
            or abs(Decimal(reconciliation["2024"]["total_original_v7_cogs_USD"])
                   - Decimal("3190534")) > Decimal("1000")):
        raise ValueError("CRMD_ORIGINAL_2024_10K_RECONCILIATION_FAILED")
    return {"years": reconciliation,
            "prior_original_10k_USD": {"revenue": "43472170", "total_cogs": "3190534",
                                        "gross_profit": "40281636"},
            "contract_mapping": "V7_GROSS_MARGIN_EQUALS_REVENUE_MINUS_TOTAL_COGS_OVER_REVENUE"}


def debt_proof(body_2025: bytes, body_2024: bytes) -> dict:
    """Check actual debt, parent-child overlap and FY2024 filing evidence."""
    current = _plain(body_2025)
    prior = _plain(body_2024)
    _require_pattern(current,
        r"CONSOLIDATED BALANCE SHEETS \(In Thousands, Except Share Data\)"
        r".*?Convertible senior notes, net of deferred financing costs\s+144,626\s+-",
        "CRMD_2025_BALANCE_SHEET_CONVERTIBLE_2024_DASH_NOT_FOUND")
    _require_pattern(current,
        r"Convertible senior note payable\s+\$?\s*150,000\s+Less debt discounts"
        r"\s*\(\s*5,374\s*\)\s+Convertible senior note payable, net"
        r"\s*\$?\s*144,626",
        "CRMD_2025_NOTE_2030_PRINCIPAL_DISCOUNT_NET_NOT_RECONCILED")
    _require_pattern(current,
        r"Notes were issued on August 12, 2025",
        "CRMD_CONVERTIBLE_ISSUANCE_AFTER_FY2024_NOT_EVIDENCED")
    _require_pattern(current, r"convertible senior notes\s+due 2030",
                     "CRMD_CONVERTIBLE_NONCURRENT_MATURITY_NOT_EVIDENCED")
    # The FY2024 original financial statements carry all liabilities and show
    # that current liabilities PLUS the one non-current operating lease balance
    # equal TOTAL liabilities. No residual unidentified financial borrowing.
    m = _require_pattern(prior,
        r"CONSOLIDATED BALANCE SHEETS December 31, 2024 and 2023"
        r".*?Current liabilities Accounts payable\s+\$?\s*1,720,177"
        r".*?Total current liabilities\s+33,839,632\s+11,400,515"
        r"\s+Operating lease liabilities, net of current portion\s+349,091"
        r"\s+517,013\s+TOTAL LIABILITIES\s+34,188,723\s+11,917,528",
        "CRMD_FY2024_ORIGINAL_EXHAUSTIVE_BALANCE_SHEET_NOT_EVIDENCED")
    if Decimal(33839632) + Decimal(349091) != Decimal(34188723):
        raise ValueError("CRMD_FY2024_TOTAL_LIABILITIES_ARITHMETIC_FAILED")
    # The 2025 balance sheet's 144,626 is THOUSANDS and has scale=3,
    # while the notes-to-accounts inline ConvertibleDebtNoncurrent tag is
    # incorrectly scale=0. Source-verified displayed accounting prevails.
    html = body_2025.decode("utf8", errors="replace")
    balance = _require_pattern(html,
        r"Convertible senior notes, net of deferred financing costs</td>.*?"
        r"<ix:nonFraction\b([^>]*)>144,626</ix:nonFraction>",
        "CRMD_CONVERTIBLE_BALANCE_IX_NOT_FOUND")
    if not all(x in balance.group(1) for x in (
        'name="us-gaap:DeferredTaxLiabilitiesOther"', 'scale="3"', 'unitRef="usd"'
    )):
        raise ValueError("CRMD_CONVERTIBLE_BALANCE_SCALE_3_NOT_PROVEN")
    note = _require_pattern(html,
        r"Convertible senior note payable, net</td>.*?"
        r"<ix:nonFraction\b([^>]*)>144,626</ix:nonFraction>",
        "CRMD_CONVERTIBLE_NOTE_IX_NOT_FOUND")
    if not all(x in note.group(1) for x in (
        'name="us-gaap:ConvertibleDebtNoncurrent"', 'scale="0"', 'unitRef="usd"'
    )):
        raise ValueError("CRMD_CONVERTIBLE_NOTE_IX_SCALE_ANOMALY_CHANGED")
    return {
        "fy2025_frozen_long_term_debt_USD": "144626000",
        "fy2024_frozen_long_term_debt_USD": "0",
        "fy2025_note_principal_USD": "150000000",
        "fy2025_unamortized_discount_USD": "5374000",
        "fy2024_original_current_liabilities_USD": "33839632",
        "fy2024_original_noncurrent_operating_lease_USD": "349091",
        "fy2024_original_total_liabilities_USD": "34188723",
        "classification": "FY2025_CONVERTIBLE_NONCURRENT;FY2024_NO_INTEREST_BEARING_NOTES",
        "nonoverlap_policy": "CONVERTIBLE_NET_CARRYING_VALUE_ONCE_NO_PRINCIPAL_DOUBLE_COUNT",
        "lease_scope": "OPERATING_LEASE_EXCLUDED_AS_IN_V7_LONG_TERM_DEBT_CONTRACT",
        "critical_sec_companyfacts_tag_anomaly": {
            "balance_sheet_inline_tag": "us-gaap:DeferredTaxLiabilitiesOther",
            "balance_sheet_scale": 3,
            "note_inline_tag": "us-gaap:ConvertibleDebtNoncurrent",
            "note_scale": 0,
            "companyfacts_note_tag_value_is_1000x_too_small": True,
        },
    }


def calculate(companyfacts_raw: bytes, submissions_raw: bytes,
              body_2025: bytes, body_2024: bytes) -> dict:
    """Public V9 interface. Accept a score only with all nine replayed signals."""
    if sha256(body_2024).hexdigest() != PRIOR_BODY_SHA256:
        raise ValueError("CRMD_FY2024_OFFICIAL_BODY_SHA256_CHANGED")
    prior_lower = body_2024.decode("utf8", errors="replace").lower()
    if "cormedix" not in prior_lower or "form 10-k" not in prior_lower:
        raise ValueError("CRMD_PRIOR_10K_ISSUER_OR_FORM_MISSING")
    v8 = audit_company(TICKER, companyfacts_raw, submissions_raw, filing_body=body_2025)
    if (v8["prior_filing"]["primary_document"] != "ea0234537-10k_cormedix.htm"
            or v8["current_filing"]["primary_document"] != "ea0278169-10k_cormedix.htm"):
        raise ValueError("CRMD_PRIOR_CURRENT_PRIMARY_DOCUMENT_IDENTITY_CHANGED")
    costs = gross_cost_proof(body_2025, body_2024, v8)
    debts = debt_proof(body_2025, body_2024)
    baseline = dict(v8["signals_partial"])
    known = [k for k, val in baseline.items() if k not in
             ("F_DELTA_LEVERAGE", "F_DELTA_GROSS_MARGIN") and val is None]
    if known:
        return {"ticker": TICKER, "score_status": "DATA_MISSING", "score": None,
                "signals": baseline, "missing": ["V8_SEVEN_SIGNALS_MISSING:" + ",".join(known)],
                "canonical_accepted": False, "historical_pit_accepted": False}
    inputs = v8["inputs"]
    ref_args = (
        inputs["net_income_2025"], inputs["net_income_2024"],
        inputs["cash_operations_2025"], inputs["assets_2025"],
        inputs["assets_2024"], inputs["assets_2023"],
        inputs["revenue_2025"], inputs["revenue_2024"],
        {"value": costs["years"]["2025"]["total_original_v7_cogs_USD"]},
        {"value": costs["years"]["2024"]["total_original_v7_cogs_USD"]},
        inputs["current_assets_2025"], inputs["current_assets_2024"],
        inputs["current_liabilities_2025"], inputs["current_liabilities_2024"],
        {"value": debts["fy2025_frozen_long_term_debt_USD"]},
        {"value": debts["fy2024_frozen_long_term_debt_USD"]},
        {"issued": True, "basis": v8["positive_issuance_evidence"]},
    )
    independent = _independent_reference(*ref_args)
    with localcontext() as ctx:
        ctx.prec = 60
        D = Decimal
        n0, n1, cf = (D(inputs[k]["value"]) for k in (
            "net_income_2025", "net_income_2024", "cash_operations_2025"
        ))
        a0, a1, a2 = (D(inputs[k]["value"]) for k in (
            "assets_2025", "assets_2024", "assets_2023"
        ))
        sale0, sale1 = (D(inputs[k]["value"]) for k in (
            "revenue_2025", "revenue_2024"
        ))
        cost0 = D(costs["years"]["2025"]["total_original_v7_cogs_USD"])
        cost1 = D(costs["years"]["2024"]["total_original_v7_cogs_USD"])
        leverage_current = D(debts["fy2025_frozen_long_term_debt_USD"]) / ((a0+a1)/2)
        leverage_prior = D(debts["fy2024_frozen_long_term_debt_USD"]) / ((a1+a2)/2)
        if min(a0,a1,a2,sale0,sale1,
               D(inputs["current_liabilities_2025"]["value"]),
               D(inputs["current_liabilities_2024"]["value"])) <= 0:
            raise ValueError("CRMD_FROZEN_S9_POSITIVE_DENOMINATOR_FAILED")
        flags = dict(baseline)
        flags["F_DELTA_LEVERAGE"] = int(leverage_current < leverage_prior)
        flags["F_DELTA_GROSS_MARGIN"] = int((sale0-cost0)/sale0 > (sale1-cost1)/sale1)
        if any(type(v) is not int or v not in (0,1) for v in flags.values()) or len(flags) != 9:
            raise ValueError("CRMD_FROZEN_S9_ALL_NINE_BINARY_REQUIRED")
        count = sum(flags.values())
        score_dec = D(100)*D(count)/D(9)
        if (independent["signals"] != flags or independent["signal_count"] != count
                or D(independent["score"]) != score_dec):
            raise ValueError("CRMD_FROZEN_V7_INDEPENDENT_DECIMAL_MISMATCH")
    return {
        "ticker": TICKER, "model": "S9", "score_status": "REAL_SCORE_ACCEPTED_RESEARCH",
        "score": float(score_dec), "score_decimal": str(score_dec), "signal_count": count,
        "positive_signal_count": count, "signals": flags,
        "signals_verified": 9, "verified_signals": 9,
        "independent_reference": independent,
        "gross_cost_proof": costs, "debt_proof": debts,
        "original_v8_partial": {"signals": v8["signals_partial"],
                                "missing": v8["missing"]},
        "selected_annual_facts": inputs,
        "equity_issuance_evidence": v8["positive_issuance_evidence"],
        "current_filing": v8["current_filing"], "prior_filing": v8["prior_filing"],
        "source_refs": {"current": CURRENT_10K_URL, "prior": PRIOR_10K_URL},
        "source_sha256": {
            "companyfacts": sha256(companyfacts_raw).hexdigest(),
            "submissions": sha256(submissions_raw).hexdigest(),
            "fy2025_10k": sha256(body_2025).hexdigest(),
            "fy2024_10k": sha256(body_2024).hexdigest(),
        },
        "frozen_model_source_sha256": MODEL_SOURCE_SHA256,
        "score_version": SCORE_VERSION,
        "research_only": True, "canonical_accepted": False,
        "historical_pit_accepted": False, "network_requests_for_replay": 0,
        "missing": [],
    }
