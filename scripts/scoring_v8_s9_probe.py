"""Offline diagnostics for two outstanding FY2025 Piotroski S9 candidates.

Reads SEC bulk archive and private metadata only; never makes requests or
infers an accounting zero from an absent taxonomy fact.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from collections import Counter
import re
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PILOTS = {"INOD": "0000903651", "CRMD": "0001410098"}
TAGS = (
    "NetIncomeLoss", "ProfitLoss", "NetCashProvidedByUsedInOperatingActivities",
    "Assets", "AssetsCurrent", "LiabilitiesCurrent", "GrossProfit",
    "DirectOperatingCosts", "Revenues", "ConvertibleDebtNoncurrent",
    "CommonStockSharesIssued", "StockIssuedDuringPeriodSharesStockOptionsExercised",
    "RevenueFromContractWithCustomerExcludingAssessedTax", "CostOfRevenue",
    "CostOfGoodsAndServicesSold", "CostOfServices", "LongTermDebt",
    "LongTermDebtCurrent", "LongTermDebtNoncurrent", "OtherLongTermDebtNoncurrent",
    "LongTermDebtAndCapitalLeaseObligations", "ConvertibleDebtNoncurrent",
    "ShortTermBorrowings", "LongTermLineOfCreditFacilityAmountOutstanding",
    "StockIssuedDuringPeriodValueNewIssues", "ProceedsFromIssuanceOfCommonStock",
    "ProceedsFromStockOptionsExercised", "CommonStockSharesOutstanding",
    "CommonStockSharesIssued", "CommonStockSharesAuthorized",
)


def extract(facts: dict, end: str, accession: str) -> dict:
    result = {}
    for tag in TAGS:
        values = facts.get("us-gaap", {}).get(tag, {}).get("units", {})
        matched = []
        for unit, rows in values.items():
            for row in rows:
                if row.get("end") == end and row.get("accn") == accession and row.get("form") == "10-K":
                    matched.append({k: row.get(k) for k in ("start", "end", "val", "accn", "filed", "fy", "fp")}|{"unit": unit})
        if matched:
            result[tag] = matched[:6]
    return result


def probe(archive: Path) -> dict:
    out = {}
    with zipfile.ZipFile(archive) as z:
        for ticker, cik in PILOTS.items():
            payload = json.loads(z.read("CIK" + cik + ".json"))
            facts = payload["facts"]
            assets = facts["us-gaap"]["Assets"]["units"]
            annual = Counter()
            for unit, rows in assets.items():
                for r in rows:
                    if r.get("form") == "10-K" and r.get("end", "")[:4] in ("2023", "2024", "2025"):
                        annual[(r["end"],r["accn"])] += 1
            report = {"issuer": payload.get("entityName"), "cik": payload["cik"], "annual_accessions": [], "concepts": {}}
            for (end, acc), count in sorted(annual.items(), reverse=True):
                if not acc or len(report["annual_accessions"]) >= 12:
                    break
                report["annual_accessions"].append({"end":end,"accession":acc})
                if end[:4] in ("2024","2025"):
                    report["concepts"][end+"@"+acc]=extract(facts,end,acc)
            search=re.compile(r"cost|debt|credit|borrow|loan|stock|share|issu|sales|revenue|gross|inventor",re.I)
            report["candidate_tags"]={}
            for taxonomy, concepts in facts.items():
                names=[]
                for tag, record in concepts.items():
                    if not search.search(tag):
                        continue
                    for units in record.get("units", {}).values():
                        if any(r.get("accn") == report["annual_accessions"][0]["accession"]
                               and r.get("end") in ("2025-12-31","2024-12-31")
                               for r in units):
                            names.append(tag)
                            break
                report["candidate_tags"][taxonomy]=sorted(set(names))
            out[ticker] = report
    return out


def main():
    archive=Path(os.environ["LOCALAPPDATA"])/"S153ResearchTerminal"/"runtime"/"bulk"/"sec"/"companyfacts.zip"
    result=probe(archive)
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__=="__main__":
    main()
