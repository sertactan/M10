"""Official SEC Companyfacts FY extraction for recovered forensic research.

Semantically exact US-GAAP tags only. Companyfacts does not report every
required Beneish or Dechow input, and missing tags never become zero. Source
fetch/retrieval time is research availability, not historical PIT publication.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import json
import math

from app.recovered_beneish import ALIAS


# Exact standard field meaning: no liabilities-as-debt, inventory-as-zero,
# cash-flow D&A-as-pure-depreciation, or gross-profit-as-COGS substitution.
US_GAAP = {
    "ACCOUNTS_RECEIVABLE_NET": ("AccountsReceivableNetCurrent",),
    "REVENUE": ("RevenueFromContractWithCustomerExcludingAssessedTax",),
    "COST_OF_REVENUE": ("CostOfRevenue", "CostOfGoodsAndServicesSold"),
    "CURRENT_ASSETS": ("AssetsCurrent",),
    "PPE_NET": ("PropertyPlantAndEquipmentNet",),
    "ASSETS": ("Assets",),
    "DEPRECIATION": ("Depreciation",),
    "SG_AND_A": ("SellingGeneralAndAdministrativeExpense",),
    # Total interest-bearing debt requires a reviewed reconciliation of
    # current + noncurrent borrowing and leases. A lone long-term-debt tag
    # cannot be silently relabeled TOTAL_DEBT for Beneish LVGI.
    "TOTAL_DEBT": (),
    "NET_INCOME": ("NetIncomeLoss",),
    "OPERATING_CASH_FLOW": ("NetCashProvidedByUsedInOperatingActivities",),
    "INVENTORY": ("InventoryNet",),
}
INSTANT_METRICS = frozenset(("ACCOUNTS_RECEIVABLE_NET", "CURRENT_ASSETS",
    "PPE_NET", "ASSETS", "TOTAL_DEBT", "INVENTORY"))


def _record_matches(obj, accession, period, instant):
    matches = []
    for item in obj.get("units", {}).get("USD", []):
        if (item.get("accn") != accession or item.get("form") != "10-K"
                or item.get("end") != period):
            continue
        if (type(item.get("val")) not in (int, float)
                or not math.isfinite(item["val"])):
            continue
        if instant and item.get("start") is not None:
            continue
        if not instant:
            start = item.get("start")
            if not start:
                continue
            try:
                days = (date.fromisoformat(period) - date.fromisoformat(start)).days + 1
            except ValueError:
                continue
            if not 330 <= days <= 400:
                continue
        matches.append(item)
    # Aliases/duplicate XBRL units can be repeated; inconsistent values block.
    if matches and len({float(r["val"]) for r in matches}) == 1 and len({r.get("start") for r in matches}) == 1:
        return matches[0]
    return None


def extract_exact_companyfacts(raw: bytes, *, ticker: str, cik: str,
                               accession: str, retrieved_at: str,
                               fiscal_years: tuple[int, ...]) -> dict:
    at = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
    if not at.tzinfo:
        raise ValueError("SEC capture time must be offset-aware")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or int(payload.get("cik", -1)) != int(cik):
        raise ValueError("SEC issuer identity mismatch")
    taxonomy = payload.get("facts", {}).get("us-gaap", {})
    digest = sha256(raw).hexdigest()
    source_ref = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json"
    rows, missing, selected = [], [], {}
    for year in fiscal_years:
        end = f"{year}-12-31"
        for metric, tags in US_GAAP.items():
            matching = []
            for tag in tags:
                xbrl = taxonomy.get(tag)
                if not isinstance(xbrl, dict):
                    continue
                record = _record_matches(xbrl, accession, end, metric in INSTANT_METRICS)
                if record is not None:
                    matching.append((tag, record))
            if not matching or len({float(r["val"]) for _, r in matching}) != 1:
                missing.append(f"{metric}_FY_{year}_EXACT_TAG")
                continue
            tag, r = matching[0]
            if not isinstance(r.get("val"), (int, float)) or not math.isfinite(r["val"]):
                missing.append(f"{metric}_FY_{year}_FINITE_VALUE")
                continue
            if date.fromisoformat(r["filed"]) > at.date():
                missing.append(f"{metric}_FY_{year}_FUTURE_FILED")
                continue
            row = {
                "metric": metric, "value": r["val"], "unit": "USD",
                "ticker": ticker, "cik": cik,
                "period_start": r.get("start"), "period_end": end,
                "period_kind": "INSTANT" if metric in INSTANT_METRICS else "ANNUAL",
                "form_type": "10-K", "accession": accession,
                "source": "SEC_EDGAR", "source_ref": source_ref,
                "filing_date": r["filed"],
                "accepted_at": None,
                "available_at": at.astimezone(timezone.utc).isoformat(),
                "source_tag": f"us-gaap:{tag}", "raw_companyfacts_sha256": digest,
                "historical_pit_accepted": False,
            }
            row["evidence_hash"] = sha256(json.dumps(
                {"raw_sha256":digest,"tag":tag,"unit":"USD","record":r},
                sort_keys=True).encode("utf-8")).hexdigest()
            rows.append(row)
            selected[f"{metric}:{year}"] = {"tag":tag,"value":r["val"],
                "period_end":end,"period_start":r.get("start"),
                "filed":r["filed"],"evidence_hash":row["evidence_hash"]}
    return {"ticker": ticker, "cik": cik,
            "source_sha256": digest, "accession": accession,
            "retrieved_at": at.isoformat(),
            "scope": "CURRENT_RESEARCH_ONLY_NOT_HISTORICAL_PIT",
            "selected": selected, "rows":rows, "missing": sorted(set(missing))}


def partial_beneish_diagnostics(rows: list[dict], fiscal_year: int) -> dict:
    """Only raw ratios that are mathematically identifiable; NEVER a B_Q score."""
    by_key = {(r["metric"],r["period_end"]):float(r["value"]) for r in rows}
    y0,y1=f"{fiscal_year-1}-12-31",f"{fiscal_year}-12-31"
    def get(metric, year):
        return by_key.get((metric,year))
    def ratio(n,d):
        return n/d if d and d>0 else None
    diagnostic = {}
    for key in ("AR", "SALES", "CA", "PPE", "TA", "SGA", "NI", "CFO"):
        metric=ALIAS[key][0]
        diagnostic[key]=(get(metric,y0),get(metric,y1))
    ar0,ar1=diagnostic["AR"]; rev0,rev1=diagnostic["SALES"]
    ca0,ca1=diagnostic["CA"]; ppe0,ppe1=diagnostic["PPE"]
    a0,a1=diagnostic["TA"]; sga0,sga1=diagnostic["SGA"]
    _,ni=diagnostic["NI"]; _,cfo=diagnostic["CFO"]
    def safe(n, d):
        if n is None or d is None:
            return None
        return ratio(n,d)
    def safe_aqi():
        if any(x is None for x in (ca0,ca1,ppe0,ppe1,a0,a1)):
            return None
        return safe(1-safe(ca1+ppe1,a1),1-safe(ca0+ppe0,a0)) if safe(ca1+ppe1,a1) is not None and safe(ca0+ppe0,a0) is not None else None
    values={
        "DSRI":safe(safe(ar1,rev1),safe(ar0,rev0)),
        "AQI":safe_aqi(),
        "SGAI":safe(safe(sga1,rev1),safe(sga0,rev0)),
        "SGI":safe(rev1,rev0),
        "TATA":safe(ni-cfo,a1) if ni is not None and cfo is not None else None,
    }
    return {"fiscal_year":fiscal_year,
            "ratios": {k:(v if v is not None and math.isfinite(v) else None)
                       for k,v in values.items()},
            "B_Q_score":None,"full_S14_score":None,
            "not_computed": ["GMI_COGS","DEPI_PURE_DEPRECIATION","LVGI_TOTAL_INTEREST_BEARING_DEBT",
                             "INDEPENDENT_SERIOUS_FLAG_REVIEW"],
            "scope":"CURRENT_RESEARCH_PARTIAL_RATIOS_ONLY"}
