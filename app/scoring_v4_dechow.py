"""INOD S6 RSST source audit; aggregate evidence never bypasses frozen gates."""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
import json
import re
from pathlib import Path
import zipfile

from app.scoring_v3_sec_filing_evidence import _extract_text


MODEL_SOURCE_SHA256 = "53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794"
COMPANYFACTS_SHA256 = "6ccc9dcc93b9c303cee51c166f345350fb16258408c884e2ed5d1231f2741b38"
ACCESSION = {2023: "0001410578-25-000194", 2024: "0001104659-26-020655", 2025: "0001104659-26-020655"}
FILINGS = {
    2024: "a2c0241be84173898a65f43480a16346704f6d61786e3ab4feff61886d973031",
    2025: "2d5dd7f964d0239ea18a982f24e077d1b8e0f08baa73fd28dd66f539d9befba2",
}
TAGS = {"assets": "Assets", "liabilities": "Liabilities", "cash": "CashAndCashEquivalentsAtCarryingValue",
        "equity": "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "preferred_shares": "PreferredStockSharesOutstanding"}


def rsst_identity():
    """Original WC+NCO+FIN coefficients, retaining all canceled terms."""
    parts = {
        "WC": {"CA": 1, "CASH": -1, "STI": -1, "CL": -1, "DLC": 1},
        "NCO": {"TA": 1, "CA": -1, "LTI": -1, "TL": -1, "CL": 1, "DLTT": 1},
        "FIN": {"STI": 1, "LTI": 1, "DLTT": -1, "DLC": -1, "PREF": -1},
    }
    total = {}
    for terms in parts.values():
        for name, coefficient in terms.items():
            total[name] = total.get(name, 0) + coefficient
    return parts, {name: value for name, value in total.items() if value}


def _fact(data, tag, year, unit):
    annual = data["facts"]["us-gaap"][tag]["units"][unit]
    # FY2023 consolidated equity is carried as a comparative instant in the
    # FY2025 filing; its FY2024 accession has only parent-equity taxonomy.
    accession = (ACCESSION[2025] if year == 2023 and tag ==
                 "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"
                 else ACCESSION[year])
    chosen = [row for row in annual if row.get("end") == f"{year}-12-31"
              and row.get("accn") == accession and row.get("form") == "10-K"
              and row.get("start") is None and type(row.get("val")) is int]
    if not chosen or len({row["val"] for row in chosen}) != 1:
        raise ValueError(f"EXACT_ANNUAL_INSTANT_MISSING:{tag}:{year}")
    record = chosen[0]
    return {"value": record["val"], "unit": unit, "period_end": record["end"],
            "accession": record["accn"], "filed": record["filed"], "tag": "us-gaap:" + tag,
            "record_sha256": sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()}


def audit_rsst(companyfacts: bytes, model_source: bytes, bodies: dict[int, bytes]) -> dict:
    """Exact SEC periods and independent equity crossfoot; S6 remains N/A."""
    if sha256(companyfacts).hexdigest() != COMPANYFACTS_SHA256:
        raise ValueError("COMPANYFACTS_SOURCE_CHANGED")
    if sha256(model_source).hexdigest() != MODEL_SOURCE_SHA256:
        raise ValueError("FROZEN_MODEL_SOURCE_CHANGED")
    parts, total = rsst_identity()
    if total != {"CASH": -1, "TA": 1, "TL": -1, "PREF": -1}:
        raise ValueError("RSST_SCOPE_CHANGED")
    data = json.loads(companyfacts)
    if data.get("cik") != 903651:
        raise ValueError("ISSUER_MISMATCH")
    for filing_year, expected_hash in FILINGS.items():
        if filing_year not in bodies or sha256(bodies[filing_year]).hexdigest() != expected_hash:
            raise ValueError("ORIGINAL_10K_SOURCE_CHANGED")
        text = _extract_text(bodies[filing_year])
        if not re.search(r"Serial preferred stock;.{0,100}none issued and outstanding", text, re.I | re.S):
            raise ValueError("PREFERRED_ZERO_FILING_ASSERTION_MISSING")
    years = {}
    for year in (2023, 2024, 2025):
        facts = {name: _fact(data, tag, year, "shares" if name == "preferred_shares" else "USD")
                 for name, tag in TAGS.items()}
        values = {name: Decimal(row["value"]) for name, row in facts.items()}
        if values["preferred_shares"] != 0:
            raise ValueError("PREFERRED_VALUE_REVIEW_REQUIRED")
        if values["assets"] != values["liabilities"] + values["equity"]:
            raise ValueError("BALANCE_SHEET_CROSSFOOT_FAILED")
        # The audited preferred-share absence supports zero issued preference.
        # The amount is not taken from a missing/nil PreferredStockValue tag.
        aggregate = values["assets"] - values["cash"] - values["liabilities"]
        independent = values["equity"] - values["cash"]
        if aggregate != independent:
            raise ValueError("INDEPENDENT_RSST_CROSSFOOT_FAILED")
        years[str(year)] = {"facts": facts, "aggregate_usd": str(aggregate),
                            "independent_equity_less_cash_usd": str(independent),
                            "WC": None, "NCO": None, "FIN": None}
    current = Decimal(years["2025"]["aggregate_usd"])
    prior = Decimal(years["2024"]["aggregate_usd"])
    current_assets = Decimal(years["2025"]["facts"]["assets"]["value"])
    prior_assets = Decimal(years["2024"]["facts"]["assets"]["value"])
    avg = (current_assets + prior_assets) / 2
    if avg <= 0:
        raise ValueError("NONPOSITIVE_AVERAGE_ASSETS")
    delta = current - prior
    ratio = delta / avg
    reference = (Decimal(years["2025"]["independent_equity_less_cash_usd"])
                 - Decimal(years["2024"]["independent_equity_less_cash_usd"])) * 2 / (current_assets + prior_assets)
    if ratio != reference:
        raise ValueError("INDEPENDENT_DECIMAL_REFERENCE_FAILED")
    return {"schema": "M10_V4_S6_RSST_AGGREGATE_V1", "issuer": "INOD", "years": years,
            "companyfacts_sha256": COMPANYFACTS_SHA256, "model_source_sha256": MODEL_SOURCE_SHA256,
            "filing_bodies_sha256": FILINGS,
            "parts": parts, "aggregate_identity": total, "delta_usd": str(delta),
            "average_assets_usd": str(avg), "RSST_decimal": str(ratio),
            "reference_decimal": str(reference), "RSST_research_candidate": float(ratio),
            "RSST_frozen_accepted": False, "S6": None, "S14": None,
            "missing": ["REVIEWED_INDIVIDUAL_WC_NCO_FIN_PARTITIONS", "INVENTORY_2024_2025",
                        "S6_NORMALIZATION_WITH_COMPLETE_INPUTS"],
            "scope": "CURRENT_RESEARCH_ONLY", "canonical_accepted": False}


def verify_private_receipt(receipt_path, companyfacts_zip, model_source_path, filing_cache):
    """Recompute a private RSST receipt from original cached source bytes."""
    receipt_path = Path(receipt_path)
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise ValueError('PRIVATE_RSST_RECEIPT_MISSING')
    raw = receipt_path.read_bytes()
    seal = Path(str(receipt_path)+'.sha256')
    if not seal.is_file() or seal.read_text(encoding='ascii').strip() != sha256(raw).hexdigest():
        raise ValueError('PRIVATE_RSST_RECEIPT_SEAL_CHANGED')
    with zipfile.ZipFile(companyfacts_zip) as archive:
        companyfacts = archive.read('CIK0000903651.json')
    filenames = {2024:'000141057825000194_inod-20241231x10k.htm',
                 2025:'000110465926020655_inod-20251231x10k.htm'}
    bodies = {year:(Path(filing_cache)/name).read_bytes() for year,name in filenames.items()}
    expected = audit_rsst(companyfacts, Path(model_source_path).read_bytes(), bodies)
    if json.loads(raw) != json.loads(json.dumps(expected, allow_nan=False)):
        raise ValueError('PRIVATE_RSST_RECEIPT_REPLAY_CHANGED')
    return expected
