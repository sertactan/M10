"""Source-reconciled INOD FY2025 S8 extension; diagnostic, offline and fail-closed.

The issuer's original 10-K statement rows below were inspected against its SEC
filing. This is an *annotated transcription*, not a cryptographic copy of the
SEC HTML. All material amounts are also cross-checked against the pinned,
original-accession SEC Companyfacts source and V10 offline verifier.
"""
from __future__ import annotations

from decimal import Decimal, localcontext
from hashlib import sha256
from pathlib import Path
import json

from app.scoring_v10_s8 import check_seal, verify_private_receipt
from app.scoring_v9_s8_s10 import FROZEN_SOURCE_SHA256

SCHEMA_V1 = "M10_SCORING_V10_EXTENSION_S8_INOD_FY2025_BRIDGES_V1"
SCHEMA = "M10_SCORING_V10_EXTENSION_S8_INOD_FY2025_BRIDGES_V2"
PARENT = Path("E:/M10/.scoring_v10_private/extension_s8")
V10 = Path("E:/M10/.scoring_v10_private/s8/research_v10_1.json")
SEC_10K = "https://www.sec.gov/Archives/edgar/data/903651/000110465926020655/inod-20251231x10k.htm"
SEC_INDEX = "https://www.sec.gov/Archives/edgar/data/903651/000110465926020655/0001104659-26-020655-index.htm"
ACCESSION = "0001104659-26-020655"
SOURCE_STATUS = "SEC_FILING_STATEMENT_ROWS_TRANSCRIBED_NO_RAW_HTML_SHA"

# Dollar *thousands*, original FY2025 Form 10-K (F-4 through F-7 and F-33).
# Separate source sections independently reconcile; do not equate any figure
# here with the still-unmapped original Ohlson 1980 funds from operations.
SEC_FY2025_KUSD = {
    "assets": 168593, "liabilities": 61531, "current_assets": 135394,
    "current_liabilities": 50532, "retained_earnings": 51158,
    "retained_earnings_2024": 18977, "parent_equity": 107145,
    "noncontrolling_equity": -83, "consolidated_equity": 107062,
    "revenue": 251663, "direct_operating_costs": 152184,
    "selling_admin_costs": 59606, "operating_profit": 39873,
    "net_interest_income": 1552, "pretax_income": 41425,
    "tax_provision": 9244, "net_income": 32181,
    "depreciation_amortization": 6889, "stock_compensation": 11144,
    "deferred_income_taxes": 4101, "provision_credit_losses": 108,
    "pension_cost": 1343, "net_working_capital_cash_change": -9014,
    "operating_cash_flow": 46752, "cash_interest_paid": 229,
    "agility_interest_expense": 1,
}
LINE_PROVENANCE = {
    "F-4": "Consolidated Balance Sheets, FY2025, 10-K F-4",
    "F-5": "Consolidated Statements of Operations, FY2025, 10-K F-5",
    "F-6": "Consolidated Statements of Stockholders' Equity, FY2025, 10-K F-6",
    "F-7": "Consolidated Statements of Cash Flows, FY2025, 10-K F-7",
    "F-33": "Segment operating profit/net interest note, FY2025",
}
FFO_ALTERNATE_SOURCES = {
    "ohlson_original": "https://doi.org/10.2307/2490395",
    "compustat_variant_pi_plus_dp": "https://faculty.ucr.edu/~abarinov/Data%20Appendix%20Distress.pdf",
    "tradingview_non_gaap_variant": "https://www.tradingview.com/support/solutions/43000563886/",
}


def D(value: object) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError("MISSING_OR_INVALID_AMOUNT")
    out = Decimal(str(value))
    if not out.is_finite():
        raise ValueError("NONFINITE_AMOUNT")
    return out


def source_bridges(rows: dict[str, int] | None = None) -> dict:
    """Independently check audited statement totals, in filed kUSD."""
    r = dict(SEC_FY2025_KUSD if rows is None else rows)
    with localcontext() as ctx:
        ctx.prec = 60
        x = {k: D(v) for k, v in r.items()}
        def insist(name: str, observed: Decimal, target: str) -> None:
            if observed != x[target]:
                raise ValueError("FILED_10K_BRIDGE_MISMATCH:" + name)

        insist("assets_equals_liabilities_plus_all_equity",
               x["assets"] - x["liabilities"], "consolidated_equity")
        insist("consolidated_equity_includes_NCI",
               x["parent_equity"] + x["noncontrolling_equity"], "consolidated_equity")
        insist("retained_earnings_rollforward",
               x["retained_earnings_2024"] + x["net_income"], "retained_earnings")
        insist("revenue_less_issuer_operating_costs",
               x["revenue"] - x["direct_operating_costs"] - x["selling_admin_costs"],
               "operating_profit")
        insist("operating_profit_plus_net_interest_income",
               x["operating_profit"] + x["net_interest_income"], "pretax_income")
        insist("pretax_less_tax", x["pretax_income"] - x["tax_provision"], "net_income")

        other_non_cash = sum((x[k] for k in (
            "depreciation_amortization", "stock_compensation",
            "deferred_income_taxes", "provision_credit_losses", "pension_cost")), Decimal(0))
        before_working_capital = x["net_income"] + other_non_cash
        insist("cashflow_statement_pre_wc_plus_wc_equals_CFO",
               before_working_capital + x["net_working_capital_cash_change"],
               "operating_cash_flow")
        if x["cash_interest_paid"] < 0 or x["agility_interest_expense"] < 0:
            raise ValueError("NEGATIVE_INTEREST_EVIDENCE")
        return {
            "status": "FINANCIAL_STATEMENTS_ARITHMETIC_CROSSCHECKED",
            "units": "USD",
            "retained_earnings": str(x["retained_earnings"]*1000),
            "parent_equity": str(x["parent_equity"]*1000),
            "consolidated_equity": str(x["consolidated_equity"]*1000),
            "noncontrolling_equity": str(x["noncontrolling_equity"]*1000),
            "operating_profit_before_net_interest": str(x["operating_profit"]*1000),
            "profit_before_tax": str(x["pretax_income"]*1000),
            "net_interest_income": str(x["net_interest_income"]*1000),
            "cash_interest_paid_NOT_accrued_interest_expense": str(x["cash_interest_paid"]*1000),
            "non_cash_cashflow_adjustments": str(other_non_cash*1000),
            "cashflow_pre_working_capital": str(before_working_capital*1000),
            "cashflow_working_capital_changes": str(x["net_working_capital_cash_change"]*1000),
            "CFO_NOT_OHLSON_FFO": str(x["operating_cash_flow"]*1000),
        }


def conditional_altman_z_double_prime(rows: dict[str, int] | None = None) -> dict:
    """Research scenario using filed operating profit as proposed X3.

    Scenario != frozen accepted EBIT, Z_Q, original historical Altman score,
    or a complete S8.
    """
    r = dict(SEC_FY2025_KUSD if rows is None else rows)
    source_bridges(r)
    with localcontext() as ctx:
        ctx.prec = 60
        a, tl = D(r["assets"]), D(r["liabilities"])
        if min(a, tl) <= 0:
            raise ValueError("INVALID_ALTMAN_DENOMINATOR")
        one = D("6.56")*(D(r["current_assets"])-D(r["current_liabilities"]))/a
        two = D("3.26")*D(r["retained_earnings"])/a
        three = D("6.72")*D(r["operating_profit"])/a
        consolidated = one+two+three+D("1.05")*D(r["consolidated_equity"])/tl
        parent = one+two+three+D("1.05")*D(r["parent_equity"])/tl
        return {
            "status": "CONDITIONAL_NONMANUFACTURER_ALTMAN_NOT_ACCEPTED_FULL_SCORE",
            "source_variant": "frozen Z'' 6.56,3.26,6.72,1.05; no +3.25 intercept",
            "X1_weighted": str(+one), "X2_weighted": str(+two),
            "X3_weighted_operating_profit_conditional": str(+three),
            "Z_double_prime_if_X3_is_operating_profit_and_X4_all_equity": str(+consolidated),
            "Z_double_prime_if_X3_is_operating_profit_and_X4_parent_equity": str(+parent),
            "Z_double_prime_equity_classification_range": [str(+consolidated), str(+parent)],
            "gross_interest_expense_as_accrual": None,
            "verified_original_S8_EBIT_variable": None,
            "accepted_Z": None, "accepted_Z_Q": None, "S8": None,
            "variant_specific_Z_Q_verified": False,
        }


def ffo_equivalence_gaps(rows: dict[str, int] | None = None) -> dict:
    r = dict(SEC_FY2025_KUSD if rows is None else rows)
    bridges = source_bridges(r)
    with localcontext() as ctx:
        ctx.prec = 60
        ni = D(r["net_income"]); da = D(r["depreciation_amortization"])
        alternatives = {
            "NI_plus_DA_UNVERIFIED": ni+da,
            "PRETAX_income_plus_DA_UNVERIFIED": D(r["pretax_income"])+da,
            "NI_plus_all_non_cash_before_WC_UNVERIFIED":
                D(bridges["cashflow_pre_working_capital"])/1000,
            "reported_modern_CFO_NOT_FFO": D(r["operating_cash_flow"]),
        }
        return {
            "status": "NO_ORIGINAL_1980_FFO_EQUIVALENCE",
            "all_alternatives_are_unaccepted": True,
            "units": "USD",
            "separate_non_interchangeable_definitions": {
                k: {"amount_usd": str(+v*1000),
                    "FUTL_if_definition_authorized": str(+(v/D(r["liabilities"])))}
                for k, v in alternatives.items()
            },
            "source_literature": FFO_ALTERNATE_SOURCES,
            "frozen_FFO": None, "frozen_FUTL": None, "accepted_O": None,
            "accepted_O_Q": None, "S8": None,
        }


def audit_extension(*, v10: Path = V10) -> dict:
    """Replays existing issuer SEC source AND independent real 10-K line sums."""
    # The original frozen contract, Companyfacts ZIP and preserved V9/V10
    # receipts are checked by the existing V10 verifier (read-only).
    base = verify_private_receipt(v10)
    if base["original_contract_sha256"] != FROZEN_SOURCE_SHA256:
        raise ValueError("FROZEN_SOURCE_CHANGED")
    inod = base["stocks"]["INOD"]
    if inod["accession"] != ACCESSION or inod["fy_end"] != "2025-12-31":
        raise ValueError("FY2025_ORIGINAL_ACCESSION_CHANGED")
    fields = {
        "assets": "assets", "liabilities": "liabilities",
        "current_assets": "current_assets", "current_liabilities": "current_liabilities",
        "retained_earnings": "retained_earnings", "parent_equity": "equity",
        "net_income": "net_income", "operating_profit": "operating_income",
    }
    source_receipts = {}
    for transcribed, tag in fields.items():
        actual = inod["facts"][tag]
        expected = SEC_FY2025_KUSD[transcribed]*1000
        if actual.get("value") != expected or not actual.get("record_sha256"):
            raise ValueError("SEC_ORIGINAL_COMPANYFACTS_MISMATCH:" + transcribed)
        source_receipts[transcribed] = {
            "us_gaap_concept": actual.get("tag") or actual.get("candidate_tag") or tag,
            "value_usd": expected,
            "source_record_sha256": actual["record_sha256"],
        }
    bridge = source_bridges()
    altman = conditional_altman_z_double_prime()
    ffo = ffo_equivalence_gaps()
    return {
        "schema": SCHEMA, "ticker": "INOD", "fiscal_year": 2025,
        "source_original_SEC_10K": SEC_10K, "source_accession": ACCESSION,
        "official_SEC_index": SEC_INDEX,
        "official_SEC_index_observed": {
            "reported_FY": "2025-12-31", "filed": "2026-02-26",
            "acceptance_timestamp": "2026-02-26 17:22:13",
            "CIK": "0000903651",
            "SIC": "7374",
            "source_status": "OFFICIAL_SEC_INDEX_LIVE_VISIBLE_NOT_OFFLINE_SHA_REPLAY",
            "original_index_body_sha256": None,
        },
        "source_sections": LINE_PROVENANCE,
        "source_status": SOURCE_STATUS,
        "source_original_HTML_sha256": None,
        "frozen_source_sha256": FROZEN_SOURCE_SHA256,
        "existing_V10_receipt_sha256": check_seal(v10),
        "existing_original_companyfacts_sha256": inod["companyfacts_sha256"],
        "crosschecked_companyfacts_rows": source_receipts,
        "retained_and_operating_profit_10K_bridges": bridge,
        "conditional_Altman": altman, "FFO_equivalence": ffo,
        "historic_original_10K_header_SIC_verification":
            "2026-02-26 original 10-K SEC filing index displays SIC 7374",
        "prior_research_sic": inod["sic_and_Altman_variant"]["sic"],
        "GNP_1968_revised_diagnostic_only": True,
        "original_S8": None, "new_real_FULL_S8_scores": 0,
        "canonical_acceptance": False,
        "open_gates": [
            "Original 1980 Ohlson FFO definition and 2025 statement mapping",
            "SEC FY2025 10-K index body SHA for offline SIC replay",
            "Frozen EBIT equivalence acceptance: operating profit vs gross interest",
            "Non-manufacturer X4: consolidated vs parent equity binding",
            "Variant-specific Altman Z_Q calibration (frozen generic safety knots)",
            "Historical as-of GNP price-index vintage for PIT promotion",
        ],
    }


def seal_bytes(content: bytes) -> str:
    return sha256(content).hexdigest()


def verify_extension_receipt(path: Path) -> dict:
    expected = check_seal(path)
    payload = json.loads(path.read_text(encoding="utf8"))
    current = audit_extension()
    if payload.get("schema") == SCHEMA_V1:
        # A pre-index-verification receipt was SHA-sealed before the official
        # 10-K metadata was located. Preserve its original evidence semantics.
        current["schema"] = SCHEMA_V1
        current.pop("official_SEC_index", None)
        current.pop("official_SEC_index_observed", None)
        current["historic_original_10K_header_SIC_verification"] = None
        current["open_gates"] = [
            "Original header FY2025 SIC replay instead of prior research SIC"
            if gate == "SEC FY2025 10-K index body SHA for offline SIC replay"
            else gate for gate in current["open_gates"]
        ]
    if payload != current:
        raise ValueError("SOURCE_BACKED_EXTENSION_REPLAY_MISMATCH")
    if seal_bytes(path.read_bytes()) != expected:
        raise ValueError("BAD_EXTENSION_SEAL")
    return payload
