"""ETON frozen S6 original-SEC accounting candidate; full acceptance fail closed.

No invented current/long-term investments or preferred issuance amounts.  The
independent aggregate RSST cancellation is usable as a mathematical diagnostic
but cannot establish the WC, NCO and FIN decomposition-review hard gate.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, localcontext
from hashlib import sha256
import json

from app.scoring_v7_piotroski import TARGETS
from app.scoring_v9_s8_s10 import verify_frozen_source

TICKER = "ETON"
CIK = TARGETS[TICKER]["cik"]
SOURCE_SHA = TARGETS[TICKER]["companyfacts_sha256"]
FROZEN_SHA = "53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794"
FILING_URLS = {
    "0001437749-25-008136": "https://www.sec.gov/Archives/edgar/data/1710340/000143774925008136/eton20241231_10k.htm",
    "0001437749-26-009059": "https://www.sec.gov/Archives/edgar/data/1710340/000143774926009059/eton20251231_10k.htm",
}
INSTANT = {
    "A": "Assets", "CA": "AssetsCurrent", "C": "CashAndCashEquivalentsAtCarryingValue",
    "CL": "LiabilitiesCurrent", "TL": "Liabilities", "AR": "AccountsReceivableNetCurrent",
    "INV": "InventoryNet", "PPE": "PropertyPlantAndEquipmentNet",
}
ANNUAL = {"REV": "RevenueFromContractWithCustomerExcludingAssessedTax",
          "NI": "NetIncomeLoss", "ISSUE_CASH": "ProceedsFromStockOptionsExercised"}
DEBT_CURRENT = "LongTermDebtCurrent"
DEBT_NONCURRENT = {2023: "LongTermDebt", 2024: "LongTermDebtNoncurrent", 2025: "LongTermDebtNoncurrent"}


def _fact(taxonomy: dict, tag: str, year: int, accession: str, *, instant: bool) -> dict:
    end = f"{year}-12-31"
    matches = []
    for row in taxonomy.get(tag, {}).get("units", {}).get("USD", []):
        if row.get("accn") != accession or row.get("form") != "10-K" or row.get("end") != end:
            continue
        if type(row.get("val")) not in (int, float) or row.get("filed") is None:
            continue
        start = row.get("start")
        if instant and start is not None:
            continue
        if not instant:
            if not start or not 330 <= (date.fromisoformat(end)-date.fromisoformat(start)).days+1 <= 400:
                continue
        matches.append(row)
    if not matches or len({(r["val"], r.get("start")) for r in matches}) != 1:
        raise ValueError("ORIGINAL_10K_UNIQUE_ACCOUNTING_FACT_REQUIRED:" + tag + ":" + str(year))
    row = matches[0]
    return {"value": str(row["val"]), "unit": "USD", "tag": "us-gaap:" + tag,
            "accession": accession, "fiscal_end": end, "period_start": row.get("start"),
            "filed": row["filed"], "form": row["form"],
            "record_sha256": sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()}


def candidate_from_pinned_sec(raw: bytes) -> dict:
    if sha256(raw).hexdigest() != SOURCE_SHA:
        raise ValueError("ETON_OFFICIAL_COMPANYFACTS_SHA_CHANGED")
    if verify_frozen_source() != FROZEN_SHA:
        raise ValueError("FROZEN_S6_CONTRACT_CHANGED")
    data = json.loads(raw)
    if str(data.get("cik", "")).zfill(10) != CIK:
        raise ValueError("WRONG_SEC_CIK")
    gaap = data["facts"]["us-gaap"]
    rows: dict[int, dict] = {}
    for year in (2023, 2024, 2025):
        accn = TARGETS[TICKER]["prior_accession"] if year == 2023 else TARGETS[TICKER]["current_accession"]
        facts = {k: _fact(gaap, tag, year, accn, instant=True) for k, tag in INSTANT.items()}
        facts.update({k: _fact(gaap, tag, year, accn, instant=False) for k, tag in ANNUAL.items()})
        facts["DLC"] = _fact(gaap, DEBT_CURRENT, year, accn, instant=True)
        facts["DLTT"] = _fact(gaap, DEBT_NONCURRENT[year], year, accn, instant=True)
        rows[year] = facts
    D = lambda y, name: Decimal(rows[y][name]["value"])
    with localcontext() as context:
        context.prec = 65
        old, prior, current = 2023, 2024, 2025
        avg = (D(current, "A")+D(prior, "A"))/2
        prevavg = (D(prior, "A")+D(old, "A"))/2
        if min(avg,prevavg,*(D(y, "A") for y in rows),D(prior,"REV"),D(current,"REV")) <= 0:
            raise ValueError("S6_FROZEN_POSITIVE_ASSETS_AND_REVENUE_GATE")
        aggregate = lambda y: D(y,"A")-D(y,"C")-D(y,"TL")
        prior_cash_sales = D(prior,"REV")-(D(prior,"AR")-D(old,"AR"))
        current_cash_sales = D(current,"REV")-(D(current,"AR")-D(prior,"AR"))
        if prior_cash_sales == 0:
            raise ValueError("S6_OLD_CASH_SALES_ZERO")
        components = {
            "RSST_aggregate_unreviewed": (aggregate(current)-aggregate(prior))/avg,
            "delta_REC": (D(current,"AR")-D(prior,"AR"))/avg,
            "delta_INV": (D(current,"INV")-D(prior,"INV"))/avg,
            "SOFT": (D(current,"A")-D(current,"PPE")-D(current,"C"))/D(current,"A"),
            "delta_CASHSALES": (current_cash_sales-prior_cash_sales)/abs(prior_cash_sales),
            "delta_ROA": D(current,"NI")/avg-D(prior,"NI")/prevavg,
            "ISSUE_evidence_indicator": Decimal(int(D(current,"ISSUE_CASH")>0)),
        }
        # Independent full-precision reference for the algebraic RSST sum.
        other = ((D(current,"CA")-D(current,"C")-D(current,"CL"))
                 + (D(current,"A")-D(current,"CA")-D(current,"TL")+D(current,"CL")))
        prior_other = ((D(prior,"CA")-D(prior,"C")-D(prior,"CL"))
                 + (D(prior,"A")-D(prior,"CA")-D(prior,"TL")+D(prior,"CL")))
        if (other-prior_other)/avg != components["RSST_aggregate_unreviewed"]:
            raise ValueError("INDEPENDENT_RSST_CROSSFOOT_MISMATCH")
        c = components
        L = (Decimal("-7.893")+Decimal(".790")*c["RSST_aggregate_unreviewed"]
             +Decimal("2.518")*c["delta_REC"]+Decimal("1.191")*c["delta_INV"]
             +Decimal("1.979")*c["SOFT"]+Decimal(".171")*c["delta_CASHSALES"]
             -Decimal(".932")*c["delta_ROA"]+Decimal("1.029")*c["ISSUE_evidence_indicator"])
        from decimal import getcontext
        diagnostic_f = (Decimal(1)/(Decimal(1)+(-L).exp()))/Decimal(".0037")
        if Decimal(1)<diagnostic_f<Decimal("1.85"):
            candidate_bin = "ORIGINAL_70_BIN_CANDIDATE_ONLY"
        else:
            candidate_bin = "FROZEN_BIN_UNVERIFIED_OR_DIFFERENT"
        values = {name: str(value) for name,value in c.items()}
    missing = [
        "STI_FY2023_2024_2025_AUDITED_CLASSIFICATION",
        "LTI_FY2023_2024_2025_AUDITED_CLASSIFICATION",
        "PREFERRED_EQUITY_FY2023_2024_2025_AUDITED_CLASSIFICATION",
        "INDEPENDENT_WC_NCO_FIN_REVIEW_AND_ORIGINAL_PRIMARY_FILING_HASHES",
        "ISSUE_AUDITED_STOCKHOLDERS_EQUITY_STATEMENT_CORROBORATION",
    ]
    return {"schema":"V10_ETON_S6_RESEARCH_COMPONENT_CANDIDATE_V1",
            "ticker":TICKER,"source_hash": SOURCE_SHA,"frozen_source_hash": FROZEN_SHA,
            "original_10K_urls":FILING_URLS,"years":{str(k):v for k,v in rows.items()},
            "fy2024_fy2025_full_balance_sheet_presentation_sec_web_reviewed":True,
            "components": values,"logistic_L_conditional":str(L),
            "F_D_conditional":str(diagnostic_f),"candidate_bin":candidate_bin,
            "S6_score":None,"accepted_full_research":False,"historical_pit":False,
            "missing":missing,"source_content_hashed":True,"primary_filing_raw_bytes_sealed":False,
            "reason":"RSST algebraic aggregate does not certify individual WC/NCO/FIN or investment/preferred-stock classification"}
