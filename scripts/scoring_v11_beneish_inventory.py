"""Inventory exact original-10-K Beneish inputs without producing a model score."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v10_quality import _cfg, depreciation_component
from app.scoring_v7_piotroski import _entry
from app.scoring_v9_s8_s10 import verify_frozen_source

EXPECTED_CONTRACT_SHA = "53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794"
TICKERS = ("CRMD", "ETON", "PENG")
# These are exact US-GAAP concept candidates, not a claim that every candidate
# has the issuer-specific scope required by the original Beneish definition.
CONCEPTS = {
    "AR": ("AccountsReceivableNetCurrent", False),
    "SALES": ("RevenueFromContractWithCustomerExcludingAssessedTax", True),
    "COGS": ("CostOfRevenue", True),
    "CA": ("AssetsCurrent", False),
    "PPE": ("PropertyPlantAndEquipmentNet", False),
    "TA": ("Assets", False),
    "DEPRECIATION": ("Depreciation", True),
    "SGA": ("SellingGeneralAndAdministrativeExpense", True),
    "NET_INCOME": ("NetIncomeLoss", True),
    "CFO": ("NetCashProvidedByUsedInOperatingActivities", True),
    "CURRENT_DEBT_CANDIDATE": ("LongTermDebtCurrent", False),
    "NONCURRENT_DEBT_CANDIDATE": ("LongTermDebtNoncurrent", False),
}


def audit_one(ticker: str, raw: bytes) -> dict:
    cfg = _cfg(ticker)
    dep = depreciation_component(ticker, raw)  # existing exact-source SHA, CIK, accession check
    if dep["status"] != "VERIFIED_COMPONENT_RESEARCH_ONLY":
        raise ValueError("ORIGINAL_PURE_DEPI_COMPONENT_REQUIRED")
    gaap = json.loads(raw)["facts"]["us-gaap"]
    periods = {}
    for name, end in (("current", cfg["end"]), ("prior", cfg["prior"])):
        rows = {}
        for key, (tag, flow) in CONCEPTS.items():
            row = _entry(gaap, tag, cfg["accn"], end, flow=flow)
            rows[key] = row if row and row["unit"] == "USD" and row["form"] == "10-K" else None
        periods[name] = rows
    missing = sorted(f"{year}.{key}" for year, rows in periods.items()
                     for key, row in rows.items() if row is None)
    return {
        "ticker": ticker, "cik": cfg["cik"], "original_accession": cfg["accn"],
        "original_companyfacts_sha256": sha256(raw).hexdigest(),
        "periods": periods, "missing_exact_candidate_tags": missing,
        "DEPI_ratio": dep["depi_ratio_decimal"],
        "DEPI_original_receipt_status": dep["status"],
        "TOTAL_DEBT_scope_accepted": False,
        "serious_flags_reviewed": False,
        "full_B_Q_score": None, "full_S5_score": None,
        "reason": "Exact tags alone do not resolve original TOTAL_DEBT, comparability and forensic review",
    }


def main() -> None:
    if verify_frozen_source() != EXPECTED_CONTRACT_SHA:
        raise ValueError("ORIGINAL_FROZEN_CONTRACT_CHANGED")
    archive = Path(os.environ["LOCALAPPDATA"]) / "S153ResearchTerminal/runtime/bulk/sec/companyfacts.zip"
    with zipfile.ZipFile(archive) as z:
        report = {ticker: audit_one(ticker, z.read(f"CIK{_cfg(ticker)['cik']}.json"))
                  for ticker in TICKERS}
    print(json.dumps({ticker: {
        "accession": row["original_accession"],
        "missing_exact_candidate_tags": row["missing_exact_candidate_tags"],
        "full_B_Q_score": row["full_B_Q_score"],
    } for ticker, row in report.items()}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
