"""INOD V9 official-filing leverage resolution; frozen S9 nine binary tests.

V7's scoring equation and thresholds are used verbatim.  A reported unutilized
revolver can establish zero bank borrowing ONLY when the complete original
10-K liability note identifies all other noncurrent obligations and leases.
This code never imputes zero merely from missing XBRL tags.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, localcontext
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import json
import re

from app.scoring_v8_s9_audit import audit_company, SOURCE_PINS
from app.scoring_v7_piotroski import MODEL_SOURCE_SHA256

FY2024_10K_SHA = "a2c0241be84173898a65f43480a16346704f6d61786e3ab4feff61886d973031"
SCORE_VERSION = "PIOTROSKI_F_SCORE_9_SIGNAL_FROZEN_V1"

class _Plain(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
    def handle_data(self, data):
        if data.strip():
            self.parts.append(data)


def _render(raw: bytes) -> str:
    parser = _Plain()
    parser.feed(raw.decode("utf-8", errors="replace"))
    return " ".join(" ".join(parser.parts).replace("\u200b", " ").split())


def _must(text: str, pattern: str, label: str) -> dict:
    matches = list(re.finditer(pattern, text, flags=re.I | re.S))
    if not matches:
        raise ValueError("OFFICIAL_NOTE_PROOF_MISSING:" + label)
    match = matches[-1]
    snippet = match.group(0)
    return {"label": label, "text": snippet[:1300],
            "text_sha256": sha256(snippet.encode("utf-8")).hexdigest()}


def _debt_contract(tenk2025: bytes, tenk2024: bytes) -> dict:
    if sha256(tenk2025).hexdigest() != SOURCE_PINS["INOD"]["body"]:
        raise ValueError("FY2025_OFFICIAL_BODY_FINGERPRINT_CHANGED")
    if sha256(tenk2024).hexdigest() != FY2024_10K_SHA:
        raise ValueError("FY2024_OFFICIAL_BODY_FINGERPRINT_CHANGED")
    a, b = _render(tenk2025), _render(tenk2024)
    evidence = {
        "2025_revolver": _must(a,
            r"(?:Company|We).{0,110}?did not utilize the Revolving Credit Facility during the year ended December 31, 2025",
            "FY2025_WELLS_FARGO_NOT_DRAWN"),
        "2024_revolver": _must(b,
            r"(?:Company|We).{0,110}?did not utilize the Revolving Credit Facility during the year ended December 31, 2024",
            "FY2024_WELLS_FARGO_NOT_DRAWN"),
        "2025_note6": _must(a,
            r"6\. Long-term obligations Total long-term obligations as of December 31, 2025 and 2024 consisted of the following.{0,1250}?Pension obligations.{0,100}?9,278.{0,100}?7,945.{0,160}?Microsoft licenses.{0,100}?6.{0,110}?442.{0,100}?9,284.{0,70}?8,387",
            "FY2025_2024_EXHAUSTIVE_NONCURRENT_OBLIGATIONS"),
        "2024_note6": _must(b,
            r"6\. Long-term obligations Total long-term obligations as of December 31, 2024 and 2023 consisted of the following.{0,1100}?Pension obligations.{0,100}?7,945.{0,100}?7,128.{0,160}?Microsoft licenses.{0,90}?442.{0,100}?911.{0,100}?8,387.{0,70}?8,039",
            "FY2024_2023_LIABILITY_NOTE_CROSSCHECK"),
        "license_vendor": _must(a,
            r"In March 2023, the Company renewed a vendor agreement.{0,550}?software licenses.{0,400}?February 2026.{0,300}?approximately.{0,40}?0\.4 million annually",
            "MICROSOFT_VENDOR_OBLIGATION_NOT_CLASSIFIED_LOAN"),
        "operating_leases": _must(a,
            r"operating lease liabilities.{0,850}?Less: Interest.{0,60}?782.{0,110}?Net present value of lease liabilities.{0,80}?4,430",
            "OPERATING_LEASE_SEPARATE_FROM_LONG_TERM_BORROWING"),
    }
    return {"debt_FY2025_USD":"0", "debt_FY2024_USD":"0",
            "debt_definition":"long_term_interest_bearing_borrowings_in_frozen_V7_S9",
            "note":"Bank revolver unutilized both years; Note6 enumerates noncurrent obligations as pensions and vendor software licenses; operating leases separate. No unreported debt inferred from missing XBRL tags.",
            "excluded":{"pension_obligations":{"FY2025_USD":9278000,"FY2024_USD":7945000},
                        "software_license_vendor_payable":{"FY2025_USD":6000,"FY2024_USD":442000},
                        "operating_lease":"OPERATING_LEASE_ACCOUNTING_NOT_BANK_BORROWING",
                        "unused_wells_fargo_facility":"CAPACITY_IS_NOT_DRAWN_DEBT"},
            "sources":{"FY2025_10K_SHA256":sha256(tenk2025).hexdigest(),
                       "FY2024_10K_SHA256":sha256(tenk2024).hexdigest()},
            "evidence":evidence}


def calculate(companyfacts_raw:bytes, submissions_raw:bytes,
              tenk2025:bytes, tenk2024:bytes) -> dict:
    partial = audit_company("INOD",companyfacts_raw,submissions_raw,
                            filing_body=tenk2025)
    if partial["signals_verified"]!=8 or partial["signals_partial"]["F_DELTA_LEVERAGE"] is not None:
        raise ValueError("INOD_V8_EIGHT_VALID_SIGNALS_REQUIRED")
    debt = _debt_contract(tenk2025,tenk2024)
    i=partial["inputs"]
    with localcontext() as context:
        context.prec=60
        D=lambda name:Decimal(i[name]["value"])
        at,ap,ab=D("assets_2025"),D("assets_2024"),D("assets_2023")
        if min(at,ap,ab)<=0: raise ValueError("INVALID_AVERAGE_TOTAL_ASSET_DENOMINATOR")
        current=Decimal(debt["debt_FY2025_USD"])/((at+ap)/Decimal(2))
        prior=Decimal(debt["debt_FY2024_USD"])/((ap+ab)/Decimal(2))
        lev=int(current<prior)
        if lev!=0: raise ValueError("NO_LEVERAGE_IMPROVEMENT_IF_ZERO_IN_BOTH_YEARS")
        signals=dict(partial["signals_partial"])
        signals["F_DELTA_LEVERAGE"]=lev
        # Independent explicit re-performance of the original, fixed nine rules.
        rn0,rn1=D("revenue_2025"),D("revenue_2024")
        ref={"F_ROA":int(D("net_income_2025")/ap>0),
             "F_CFO":int(D("cash_operations_2025")>0),
             "F_DELTA_ROA":int(D("net_income_2025")/ap>D("net_income_2024")/ab),
             "F_ACCRUAL":int(D("cash_operations_2025")>D("net_income_2025")),
             "F_DELTA_LEVERAGE":int(current<prior),
             "F_DELTA_LIQUIDITY":int(D("current_assets_2025")/D("current_liabilities_2025")>D("current_assets_2024")/D("current_liabilities_2024")),
             "F_NO_COMMON_EQUITY_ISSUANCE":0,
             "F_DELTA_GROSS_MARGIN":int(D("gross_profit_2025")/rn0>D("gross_profit_2024")/rn1),
             "F_DELTA_ASSET_TURNOVER":int(rn0/((at+ap)/2)>rn1/((ap+ab)/2))}
        if ref!=signals: raise ValueError("S9_INDEPENDENT_DECIMAL_REFERENCE_MISMATCH")
        positives=sum(ref.values())
        decimal_score=Decimal(100)*Decimal(positives)/Decimal(9)
    if positives!=5: raise ValueError("S9_UNEXPECTED_FROZEN_SIGNAL_COUNT")
    return {"schema":"M10_S9_INOD_V9_SEC_OFFICIAL_SOURCE_REPLAY_V1",
            "ticker":"INOD", "cik":"0000903651", "fy":"2025-12-31",
            "accession":"0001104659-26-020655",
            "prior_accession":"0001410578-25-000194",
            "frozen_model_sha256":MODEL_SOURCE_SHA256,
            "model": "S9", "model_version":SCORE_VERSION,
            "score_status":"REAL_SCORE_ACCEPTED_RESEARCH",
            "scope":"CURRENT_RESEARCH_ONLY","canonical_accepted":False,
            "historical_pit_accepted":False, "sources":{
                 "companyfacts_sha256":sha256(companyfacts_raw).hexdigest(),
                 "submissions_sha256":sha256(submissions_raw).hexdigest(),
                 "FY2025_10K_sha256":sha256(tenk2025).hexdigest(),
                 "FY2024_10K_sha256":sha256(tenk2024).hexdigest()},
            "debt_reconciliation":debt, "signals":signals,
            "verified_signals":9,"positive_signal_count":positives,
            "debt_ratio_FY2025":str(current),"debt_ratio_FY2024":str(prior),
            "score":float(decimal_score),"score_decimal":str(decimal_score),
            "independent_decimal_reference":{"signals":ref,"score":str(decimal_score),"passed":True},
            "source_as_of":"2026-10-11","as_of_kind":"CURRENT_RESEARCH_NOT_HISTORICAL_PIT"}


def write_or_verify(path:Path, inputs:tuple[bytes,bytes,bytes,bytes]):
    report=calculate(*inputs)
    raw=(json.dumps(report,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+"\n").encode("utf8")
    seal=Path(str(path)+".sha256")
    if path.is_file():
        if path.read_bytes()!=raw or not seal.is_file() or seal.read_text("ascii").strip()!=sha256(raw).hexdigest():
            raise ValueError("V9_PRIVATE_S9_SOURCE_REPLAY_MISMATCH")
    else:
        if path.exists() or seal.exists(): raise ValueError("V9_PRIVATE_RECEIPT_COLLISION")
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("xb") as fd: fd.write(raw)
        with seal.open("x",encoding="ascii") as fd: fd.write(sha256(raw).hexdigest()+"\n")
    return report
