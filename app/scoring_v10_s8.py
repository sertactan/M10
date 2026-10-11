"""Original-contract S8 research evidence, Decimal audited, offline fail-closed.

Historical market equity, Ohlson-era FFO and standalone EBIT are mandatory
evidence. Neither modern CFO, a cash-flow D&A tag, an operating-income proxy
nor filing-cover public float may silently fill those model variables.
"""
from __future__ import annotations

from decimal import Decimal, localcontext
from hashlib import sha256
from pathlib import Path
import json
import math
import os
import zipfile

from app.scoring_v8_s8_s10 import TARGETS, audit_payload, _record_key
from app.scoring_v9_s8_s10 import (
    FROZEN_SOURCE_SHA256, SOURCE_LOCATION, verify_frozen_source,
    _exact_gaap_value, gnp_size,
)

SCHEMA = "M10_SCORING_V10_S8_RESEARCH_ACCOUNTING_EVIDENCE_V1"
V9_REPORT = Path("E:/M10/.scoring_v9_private/s8_s10/v9_evidence_v2.json")
V6_ROOT = Path("E:/M10/.scoring_v6_private")
DEFAULT_BULK = (Path(os.environ.get("LOCALAPPDATA", "C:/Users/serta/AppData/Local")) /
                "S153ResearchTerminal/runtime/bulk/sec/companyfacts.zip")
FY2025_HEADERS = {"TMDX": "3845", "CRMD": "2834", "PENG": "3674", "ETON": "2834"}
FROZEN_S8_SOURCE_LINES = "1325-1442"
ORIGINAL_OHLSON_PAPER = "https://doi.org/10.2307/2490395"
ORIGINAL_ALTAMAN_Z = "PUBLIC_MANUFACTURING"


def sha_file(path: Path) -> str:
    h = sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check_seal(path: Path) -> str:
    path = Path(path)
    side = Path(str(path) + ".sha256")
    if any(not x.is_file() or x.is_symlink() for x in (path, side)):
        raise ValueError("MISSING_OR_SYMLINKED_IMMUTABLE_SOURCE")
    expected = side.read_text(encoding="ascii").strip()
    observed = sha_file(path)
    if expected != observed:
        raise ValueError("SOURCE_SHA256_SEAL_CHANGED")
    return observed


def d(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError("missing financial input")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("non-finite financial input")
    return result


def decimal_ohlson_non_ffo(assets: object, liabilities: object, ca: object,
                           cl: object, ni: object, ni_prior: object,
                           gnp_prior: object, gnp1968: object) -> dict:
    """Independent frozen Ohlson numeric terms excluding unavailable FUTL.

    This is a *partial logit contribution*, not a model score or probability.
    """
    with localcontext() as ctx:
        ctx.prec = 60
        a, l, current_a, current_l = (d(v) for v in (assets, liabilities, ca, cl))
        income, previous, gnp, base = (d(v) for v in (ni, ni_prior, gnp_prior, gnp1968))
        if min(a, l, current_a, gnp, base) <= 0:
            raise ValueError("non-positive Ohlson required denominator")
        denom = abs(income) + abs(previous)
        if denom == 0:
            raise ValueError("OHLSON_CHIN_ZERO_DENOMINATOR")
        size = (a / (Decimal(100)*gnp/base)).ln()
        terms = {
            "INTERCEPT": Decimal("-1.32"),
            "SIZE": Decimal("-0.407") * size,
            "TLTA": Decimal("6.03") * l/a,
            "WCTA": Decimal("-1.43") * (current_a-current_l)/a,
            "CLCA": Decimal("0.0757") * current_l/current_a,
            "OENEG": Decimal("-1.72") * Decimal(int(l>a)),
            "NITA": Decimal("-2.37") * income/a,
            "INTWO": Decimal("0.285") * Decimal(int(income<0 and previous<0)),
            "CHIN": Decimal("-0.521") * (income-previous)/denom,
        }
        return {
            "status": "NON_FFO_LOGIT_COMPONENTS_NOT_A_SCORE",
            "SIZE_decimal": str(+size),
            "partial_logit_excluding_FUTL": str(+sum(terms.values())),
            "weighted_terms": {key: str(+value) for key, value in terms.items()},
            "FUTL": None, "logit": None, "O_Q": None, "S8": None,
        }


def decimal_altman_parts(*, assets: object, ca: object, cl: object,
                         retained_earnings: object, liabilities: object,
                         equity: object | None, revenue: object | None,
                         variant: str) -> dict:
    """Compute evidenced Altman x1/x2 and variant-specific x4/x5 only.

    Real EBIT is not inferred from OperatingIncomeLoss; FY-end MVE is not
    inferred from the filing-cover public-float amount.
    """
    with localcontext() as ctx:
        ctx.prec = 60
        a, cur_a, cur_l, retained, debt = map(
            d, (assets, ca, cl, retained_earnings, liabilities))
        if a <= 0 or debt <= 0:
            raise ValueError("invalid Altman assets/liabilities")
        factor = {"X1_WC_A": (cur_a-cur_l)/a, "X2_RE_A": retained/a}
        if variant == "NONMANUFACTURING_Z_DOUBLE_PRIME":
            if equity is not None:
                factor["X4_BOOK_EQUITY_TL"] = d(equity)/debt
            weighted = {"X1": Decimal("6.56")*factor["X1_WC_A"],
                        "X2": Decimal("3.26")*factor["X2_RE_A"]}
            if "X4_BOOK_EQUITY_TL" in factor:
                weighted["X4"] = Decimal("1.05")*factor["X4_BOOK_EQUITY_TL"]
            missing = ["INDEPENDENT_EBIT_TO_TOTAL_ASSETS"]
            if "X4_BOOK_EQUITY_TL" not in factor:
                missing.append("BOOK_COMMON_EQUITY_CLASSIFICATION")
        elif variant == "PUBLIC_MANUFACTURING_Z":
            weighted = {"X1": Decimal("1.2")*factor["X1_WC_A"],
                        "X2": Decimal("1.4")*factor["X2_RE_A"]}
            if revenue is not None:
                factor["X5_REVENUE_A"] = d(revenue)/a
                weighted["X5"] = factor["X5_REVENUE_A"]
            missing = ["INDEPENDENT_EBIT_TO_TOTAL_ASSETS",
                       "EXACT_FY_END_DATED_MARKET_EQUITY"]
            if "X5_REVENUE_A" not in factor:
                missing.append("REVENUE_FROM_ORIGINAL_STATEMENT")
        else:
            raise ValueError("FROZEN_ALTMAN_VARIANT_UNVERIFIED")
        return {"status": "PARTIAL_ALTMAN_FACTORS_NOT_A_SCORE", "variant": variant,
                "factors": {k: str(+v) for k, v in factor.items()},
                "weighted_terms": {k: str(+v) for k, v in weighted.items()},
                "missing": missing, "Z": None, "Z_Q": None, "S8": None}


def _gaap_fact(gaap: dict, tag: str, *, ticker: str, flow: bool) -> dict:
    cfg = TARGETS[ticker]
    return _exact_gaap_value(gaap, tag, 2025, cfg["fy_end"], flow,
                             cfg["accession"])


def _one_of(gaap: dict, ticker: str, names: tuple[str, ...], flow: bool) -> dict:
    candidates = [_gaap_fact(gaap, tag, ticker=ticker, flow=flow) for tag in names]
    found = [x for x in candidates if x.get("status") == "EXACT_ORIGINAL_10K_FACT_RESEARCH"]
    if len(found) == 1:
        return {**found[0], "candidate_tags_evaluated": list(names)}
    if len(found) > 1:
        # Multiple tags occasionally coexist and map to inconsistent GAAP
        # concepts. The fiscal year needs a filing presentation crosswalk.
        return {"status": "MULTIPLE_CONCEPTS_REQUIRES_FILING_CROSSWALK",
                "candidates": found, "candidate_tags_evaluated": list(names)}
    return {"status": "EXACT_10K_FY_ACCOUNTING_CONCEPT_NOT_EVIDENCED",
            "candidate_tags_evaluated": list(names)}


def _public_float(dei: dict, ticker: str) -> dict:
    cfg = TARGETS[ticker]
    items = [row for units in (dei.get("EntityPublicFloat", {}).get("units") or {}).values()
             for row in units if row.get("accn") == cfg["accession"] and row.get("form") == "10-K"]
    unique = {json.dumps(row, sort_keys=True): row for row in items}
    if len(unique) != 1:
        return {"status": "NOT_EVIDENCED"}
    item = next(iter(unique.values()))
    return {"status": "COVER_PAGE_OTHER_DATE_NOT_FY_END_MVE", "value": item["val"],
            "date": item.get("end"), "record_sha256": _record_key(item),
            "accession": item.get("accn"), "eligible_as_FY_end_market_equity": False}


def _sic_evidence(ticker: str) -> dict:
    if ticker == "INOD":
        return {"sic": "7374", "variant": "NONMANUFACTURING_Z_DOUBLE_PRIME",
                "historical_header_verified_in_this_run": False,
                "source": "PRIOR_V4_INOD_SIC7374_RESEARCH_SNAPSHOT"}
    path = V6_ROOT / ("jones_" + ticker.lower()) / "report.json"
    digest = check_seal(path)
    old = json.loads(path.read_text(encoding="utf-8"))
    target = old.get("target") or {}
    if (old.get("ticker") != ticker or target.get("historical_sic") != FY2025_HEADERS[ticker]
            or target.get("form_accession") != TARGETS[ticker]["accession"]
            or target.get("companyfacts_sha256") != TARGETS[ticker]["sha256"]
            or target.get("status") != "VALID_8_FINANCIALS_AND_HISTORICAL_HEADER"
            or not target.get("header_sha256")):
        raise ValueError(f"PRESERVED_V6_SIC_ACCEPTANCE_CHANGED:{ticker}")
    return {"sic": target["historical_sic"], "variant": "PUBLIC_MANUFACTURING_Z",
            "historical_header_verified_in_this_run": False,
            "prior_official_header_sha256": target["header_sha256"],
            "original_header_url": target["header_url"],
            "V6_receipt_sha256": digest,
            "V6_verified_header_receipt_reused": True}


def _stock(ticker: str, raw: bytes, v9_stock: dict) -> dict:
    assert ticker in TARGETS
    v8 = audit_payload(ticker, raw)  # enforces exact immutable SEC source SHA/issuer
    payload = json.loads(raw)
    gaap = payload["facts"]["us-gaap"]
    dei = payload["facts"].get("dei", {})
    cfg = TARGETS[ticker]
    if v9_stock["companyfacts_sha256"] != cfg["sha256"]:
        raise ValueError("PINNED_V9_SEC_SOURCE_CHANGED")
    fields = {
        "assets": ("Assets", False), "liabilities": ("Liabilities", False),
        "current_assets": ("AssetsCurrent", False),
        "current_liabilities": ("LiabilitiesCurrent", False),
        "equity": ("StockholdersEquity", False),
        "retained_earnings": ("RetainedEarningsAccumulatedDeficit", False),
        "net_income": ("NetIncomeLoss", True),
        "operating_income": ("OperatingIncomeLoss", True),
    }
    facts = {key: _gaap_fact(gaap, tag, ticker=ticker, flow=flow)
             for key, (tag, flow) in fields.items()}
    facts["revenue"] = _one_of(gaap, ticker,
        ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"), True)
    facts["cashflow_depreciation_amortization"] = _one_of(gaap, ticker,
        ("DepreciationDepletionAndAmortization", "DepreciationAndAmortization"), True)
    facts["standalone_depreciation"] = _gaap_fact(gaap, "Depreciation", ticker=ticker, flow=True)
    facts["intangible_amortization"] = _gaap_fact(gaap, "AmortizationOfIntangibleAssets",
                                                  ticker=ticker, flow=True)
    facts["pretax_income_not_income_before_extraordinary"] = _gaap_fact(
        gaap, "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        ticker=ticker, flow=True)
    sic = _sic_evidence(ticker)
    required = ("assets", "liabilities", "current_assets", "current_liabilities",
                "net_income")
    missing = [k for k in required if "value" not in facts[k]]
    matched_v9 = (v9_stock.get("S8") or {}).get("years", {}).get("2025", {})
    v9_o = matched_v9.get("ohlson") or {}
    gnp_v9 = v9_o.get("size") or {}
    if gnp_v9.get("historical_as_of_vintage_verified") is not False:
        raise ValueError("V9_GNP_PIT_PROVENANCE_CHANGED")
    decimal_o = None
    if not missing:
        prev = (matched_v9.get("source_facts") or {}).get("prior_ni") or {}
        if "value" not in prev:
            missing.append("prior_net_income")
        else:
            check_fields = {"assets": "assets", "liabilities": "liabilities",
                            "current_assets": "ca", "current_liabilities": "cl",
                            "net_income": "ni"}
            for name, old_name in check_fields.items():
                original = (matched_v9.get("source_facts") or {}).get(old_name) or {}
                if (original.get("record_sha256") != facts[name].get("record_sha256")
                        or original.get("value") != facts[name].get("value")):
                    raise ValueError(f"V9_TO_V10_SOURCE_FIELD_CHANGED:{ticker}:{name}")
            decimal_o = decimal_ohlson_non_ffo(
                facts["assets"]["value"], facts["liabilities"]["value"],
                facts["current_assets"]["value"], facts["current_liabilities"]["value"],
                facts["net_income"]["value"], prev["value"],
                gnp_v9["gnp_2017_base"], gnp_v9["gnp_1968_2017_base"])
            size = gnp_size(facts["assets"]["value"], 2025)
            if abs(float(decimal_o["SIZE_decimal"]) - gnp_v9["SIZE"]) > 1e-12 or \
                    abs(float(decimal_o["SIZE_decimal"]) - size["SIZE"]) > 1e-12:
                raise ValueError("INDEPENDENT_DECIMAL_V9_SIZE_REPLAY_FAILED")
    else:
        missing.append("source_evidenced_complete_Ohlson_inputs")
    altman = None
    needed = ("assets", "current_assets", "current_liabilities", "retained_earnings",
              "liabilities")
    if all("value" in facts[k] for k in needed):
        altman = decimal_altman_parts(
            assets=facts["assets"]["value"], ca=facts["current_assets"]["value"],
            cl=facts["current_liabilities"]["value"],
            retained_earnings=facts["retained_earnings"]["value"],
            liabilities=facts["liabilities"]["value"],
            equity=facts["equity"].get("value"),
            revenue=facts["revenue"].get("value"), variant=sic["variant"])
    ffo = {"status": "ORIGINAL_OHLSON_1980_FFO_EQUIVALENCE_NOT_PROVEN",
           "exact_original_frozen_text": "FundsFromOperations / TotalLiabilities",
           "paper_terminology": "funds provided by operations",
           "reported_CFO_substitution_accepted": False,
           "reported_NI_plus_DA_substitution_accepted": False,
           "independent_income_before_extraordinary_verified": False,
           "cashflow_depreciation_candidate": facts["cashflow_depreciation_amortization"],
           "separate_depreciation_candidate": facts["standalone_depreciation"],
           "amortization_candidate": facts["intangible_amortization"],
           "income_candidate": facts["net_income"],
           "income_before_tax_is_not_IB": facts["pretax_income_not_income_before_extraordinary"],
           "FFO": None, "FUTL": None}
    if "value" in facts["net_income"] and "value" in facts["cashflow_depreciation_amortization"]:
        x = d(facts["net_income"]["value"]) + d(facts["cashflow_depreciation_amortization"]["value"])
        ffo["UNVERIFIED_NI_PLUS_DA_CANDIDATE"] = str(x)
    return {"ticker": ticker, "fy_end": cfg["fy_end"], "accession": cfg["accession"],
            "companyfacts_sha256": cfg["sha256"], "frozen_source_sha256": FROZEN_SOURCE_SHA256,
            "V8_source_member_passed": bool(v8["companyfacts_sha256"] == cfg["sha256"]),
            "v9_revised_GNP_and_SIZE": gnp_v9,
            "sic_and_Altman_variant": sic,
            "fy_end_market_equity": None,
            "SEC_cover_non_FY_end_public_float": _public_float(dei, ticker),
            "facts": facts, "FFO_and_FUTL": ffo,
            "Ohlson_non_FFO_decimal": decimal_o, "Altman_decimal": altman,
            "S8": None, "O_Q": None, "Z_Q": None,
            "status": "DATA_MISSING_ORIGINAL_FFO_AND_ALTMAN_INPUTS",
            "required_to_accept": sorted(set(missing + [
                "ORIGINAL_FFO_ORIGINAL_AUTHORITATIVE_MAPPING",
                "RESEARCHED_1980_FFO_ACCOUNTING_EQUIVALENCE",
                "INDEPENDENT_FILING_EBIT_NOT_OPERATING_INCOME_PROXY",
                "ALTMAN_COMPLETE_FROZEN_VARIANT_DATA",
                "HISTORICAL_GNP_VINTAGE_FOR_CANONICAL_PIT",
                *( ["FISCAL_END_MARKET_VALUE_EQUITY"]
                   if sic["variant"] == "PUBLIC_MANUFACTURING_Z" else []),
            ])),
            "canonical_accepted": False, "historical_PIT_accepted": False}


def audit_sources(*, bulk: Path = DEFAULT_BULK, v9_path: Path = V9_REPORT,
                  frozen_source: Path = SOURCE_LOCATION) -> dict:
    frozen_digest = verify_frozen_source(frozen_source)
    v9_digest = check_seal(v9_path)
    v9 = json.loads(v9_path.read_text(encoding="utf-8"))
    if (v9.get("schema") != "M10_SCORING_V9_S8_S10_FROZEN_IMPLEMENTATION_V1"
            or v9.get("frozen_source_sha256") != FROZEN_SOURCE_SHA256
            or v9.get("gnp_historical_vintage_verified") is not False
            or set(v9.get("stocks", {})) != set(TARGETS)):
        raise ValueError("PRESERVED_V9_MODEL_INPUT_CHANGED")
    if bulk.is_symlink() or not bulk.is_file():
        raise ValueError("PINNED_SEC_OFFLINE_ZIP_MISSING")
    stocks = {}
    with zipfile.ZipFile(bulk) as z:
        for ticker, config in TARGETS.items():
            info = z.getinfo("CIK" + config["cik"] + ".json")
            if info.file_size > 40_000_000:
                raise ValueError("SEC_MEMBER_ABOVE_FILE_BOUND")
            raw = z.read(info)
            if sha256(raw).hexdigest() != config["sha256"]:
                raise ValueError("IMMUTABLE_SEC_SHA_CHANGED")
            stocks[ticker] = _stock(ticker, raw, v9["stocks"][ticker])
    if any(s["S8"] is not None for s in stocks.values()):
        raise ValueError("UNPROVEN_FULL_S8_PROMOTION")
    return {"schema": SCHEMA, "source_v9_sha256": v9_digest,
            "original_contract_sha256": frozen_digest,
            "original_contract_line_range": FROZEN_S8_SOURCE_LINES,
            "scope": "CURRENT_RESEARCH_ONLY_NO_CANONICAL_PIT",
            "network_requests": 0,
            "original_ohlson_paper_url": ORIGINAL_OHLSON_PAPER,
            "new_complete_S8_scores": 0, "canonical_securities": 0,
            "stocks": stocks}


def verify_private_receipt(path: Path, *, bulk: Path = DEFAULT_BULK,
                           v9_path: Path = V9_REPORT,
                           frozen_source: Path = SOURCE_LOCATION) -> dict:
    """Seal verification PLUS re-performance of SEC XBRL, V9 and Decimal math."""
    check_seal(path)
    packet = json.loads(Path(path).read_text(encoding="utf-8"))
    current = audit_sources(bulk=bulk, v9_path=v9_path, frozen_source=frozen_source)
    if packet != current:
        raise ValueError("V10_SEC_DECIMAL_OFFLINE_REPLAY_MISMATCH")
    return packet
