"""Source-bound RSST partition audit; unknown classifications stay symbolic."""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
import json

from app.scoring_v4_dechow import (
    COMPANYFACTS_SHA256, _fact, audit_rsst,
)


def audit_partitions(companyfacts: bytes, model_source: bytes,
                     filing_bodies: dict[int, bytes]) -> dict:
    """Resolve reported partition bases without treating absent tags as zero.

    WC = (CA-CASH-CL)-STI+DLC.
    NCO = (TA-CA-TL+CL)-LTI+DLTT.
    FIN = STI+LTI-DLTT-DLC-PREF.
    The four unproved classifications cancel in the aggregate, but are still
    required to attest the three individual frozen inputs.
    """
    if sha256(companyfacts).hexdigest() != COMPANYFACTS_SHA256:
        raise ValueError("COMPANYFACTS_SOURCE_CHANGED")
    aggregate = audit_rsst(companyfacts, model_source, filing_bodies)
    data = json.loads(companyfacts)
    years = {}
    for year in (2023, 2024, 2025):
        ca = _fact(data, "AssetsCurrent", year, "USD")
        cl = _fact(data, "LiabilitiesCurrent", year, "USD")
        prior = aggregate["years"][str(year)]["facts"]
        v = lambda fact: Decimal(fact["value"])
        wc_base = v(ca) - v(prior["cash"]) - v(cl)
        nco_base = v(prior["assets"]) - v(ca) - v(prior["liabilities"]) + v(cl)
        if wc_base + nco_base != Decimal(aggregate["years"][str(year)]["aggregate_usd"]):
            raise ValueError("PARTITION_BASE_CROSSFOOT_FAILED")
        years[str(year)] = {
            "current_assets": ca, "current_liabilities": cl,
            "WC_base_usd": str(wc_base), "NCO_base_usd": str(nco_base),
            "WC_expression": "WC_base - STI + DLC",
            "NCO_expression": "NCO_base - LTI + DLTT",
            "FIN_expression": "STI + LTI - DLTT - DLC - PREF",
            "unresolved_classifications": ["STI", "LTI", "DLC", "DLTT"],
            "WC_accepted": None, "NCO_accepted": None, "FIN_accepted": None,
        }
    return {
        "schema": "M10_V5_RSST_PARTITION_BOUNDARY_V1", "issuer": "INOD",
        "companyfacts_sha256": COMPANYFACTS_SHA256,
        "filing_bodies_sha256": aggregate["filing_bodies_sha256"],
        "model_source_sha256": aggregate["model_source_sha256"],
        "years": years, "RSST_aggregate_ratio": aggregate["RSST_decimal"],
        "RSST_frozen_accepted": False, "S6": None,
        "status": "DATA_MISSING",
        "missing": ["STI_LTI_DLC_DLTT_PERIOD_CLASSIFICATION",
                    "REVIEWED_INDIVIDUAL_WC_NCO_FIN_PARTITIONS",
                    "INVENTORY_2024_2025"],
        "scope": "CURRENT_RESEARCH_ONLY", "canonical_accepted": False,
    }
