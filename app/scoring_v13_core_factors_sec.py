"""Original-source raw F52/F53 growth for INOD; no unversioned score mapping."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, localcontext
from hashlib import sha256
import json
from pathlib import Path

from app.scoring_v7_piotroski import _entry
from app.scoring_v8_s9_audit import SOURCE_PINS
from app.scoring_v9_s8_s10 import verify_frozen_source


ACCESSION = "0001104659-26-020655"
CIK = "0000903651"
PERIODS = {"current": "2025-12-31", "prior": "2024-12-31"}
TAGS = {
    "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "USD"),
    "diluted_shares": ("WeightedAverageNumberOfDilutedSharesOutstanding", "shares"),
    "operating_cash": ("NetCashProvidedByUsedInOperatingActivities", "USD"),
    "capital_expenditure": ("PaymentsToAcquirePropertyPlantAndEquipment", "USD"),
}


def _select(facts: dict, tag: str, end: str, unit: str) -> dict:
    rows = facts[tag]["units"].get(unit, [])
    matches = [r for r in rows if r.get("accn") == ACCESSION and r.get("end") == end
               and r.get("form") == "10-K" and r.get("start") and
               330 <= (date.fromisoformat(end) - date.fromisoformat(r["start"])).days + 1 <= 400]
    if len(matches) != 1:
        raise ValueError(f"missing or ambiguous exact source: {tag} {end}")
    row = matches[0]
    independent = _entry(facts, tag, ACCESSION, end, flow=True)
    if independent is None or independent["unit"] != unit or independent["value"] != str(row["val"]):
        raise ValueError(f"independent selector disagrees: {tag} {end}")
    return independent


def calculate_raw_factors(companyfacts_path: Path, submissions_path: Path) -> dict:
    raw = companyfacts_path.read_bytes()
    subs_raw = submissions_path.read_bytes()
    pins = SOURCE_PINS["INOD"]
    if sha256(raw).hexdigest() != pins["companyfacts"] or sha256(subs_raw).hexdigest() != pins["submissions"]:
        raise ValueError("pinned SEC source SHA mismatch")
    payload = json.loads(raw)
    subs = json.loads(subs_raw)
    if str(payload["cik"]).zfill(10) != CIK or str(subs["cik"]).zfill(10) != CIK:
        raise ValueError("issuer CIK mismatch")
    recent = subs["filings"]["recent"]
    accession_rows = [i for i, value in enumerate(recent["accessionNumber"]) if value == ACCESSION]
    if len(accession_rows) != 1 or recent["form"][accession_rows[0]] != "10-K":
        raise ValueError("original accession absent or ambiguous")
    accepted_at = recent["acceptanceDateTime"][accession_rows[0]]
    if datetime.fromisoformat(accepted_at.replace("Z", "+00:00")).tzinfo is None:
        raise ValueError("SEC acceptance time lacks timezone")
    facts = payload["facts"]["us-gaap"]
    source_rows = {period: {key: _select(facts, tag, end, unit)
                            for key, (tag, unit) in TAGS.items()}
                   for period, end in PERIODS.items()}
    with localcontext() as ctx:
        ctx.prec = 60
        D = lambda period, key: Decimal(source_rows[period][key]["value"])
        if any(D(p, "diluted_shares") <= 0 or D(p, "revenue") <= 0 for p in PERIODS):
            raise ValueError("nonpositive revenue or diluted shares")
        revps = {p: D(p, "revenue") / D(p, "diluted_shares") for p in PERIODS}
        fcf = {p: D(p, "operating_cash") - D(p, "capital_expenditure") for p in PERIODS}
        if any(value <= 0 for value in fcf.values()):
            raise ValueError("FCF-per-share growth undefined for nonpositive base")
        fcfps = {p: fcf[p] / D(p, "diluted_shares") for p in PERIODS}
        rps_growth = revps["current"] / revps["prior"] - 1
        fps_growth = fcfps["current"] / fcfps["prior"] - 1
        # Algebraically independent ratio-of-products references.
        rps_ref = (D("current", "revenue") * D("prior", "diluted_shares") /
                   (D("prior", "revenue") * D("current", "diluted_shares"))) - 1
        fps_ref = (fcf["current"] * D("prior", "diluted_shares") /
                   (fcf["prior"] * D("current", "diluted_shares"))) - 1
        if abs(rps_growth-rps_ref) > Decimal("1e-50") or abs(fps_growth-fps_ref) > Decimal("1e-50"):
            raise ValueError("independent Decimal reference mismatch")
        calculations = {
            "F52_RPSGrowth_1Y": str(rps_growth), "F53_FPSGrowth_1Y": str(fps_growth),
            "FY2025_FCF_USD": str(fcf["current"]), "FY2024_FCF_USD": str(fcf["prior"]),
            "F52_reference": str(rps_ref), "F53_reference": str(fps_ref),
        }
    return {"issuer": "INOD", "as_of_filing_accession": ACCESSION,
            "accepted_at": accepted_at, "current_fiscal_end": PERIODS["current"],
            "prior_fiscal_end": PERIODS["prior"],
            "frozen_contract_sha256": verify_frozen_source(),
            "companyfacts_sha256": sha256(raw).hexdigest(),
            "submissions_sha256": sha256(subs_raw).hexdigest(),
            "source_rows": source_rows, "calculations": calculations,
            "raw_factor_formulas_verified": ["F52_RPSGrowth_1Y", "F53_FPSGrowth_1Y"],
            "normalized_quality_scores": {"F52_RPS": None, "F53_FPS": None},
            "normalization_blocker": "Frozen contract gives raw growth formulas but no numeric 0-100 mapping for F52/F53",
            "historical_pit_accepted": False, "complete_s1_s2_s3_scores": 0}
