"""Broad iXBRL name census with explicit non-promotion of missing quality inputs."""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from html.parser import HTMLParser

from app.scoring_v13_quality_ixbrl import PINS


class _Names(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.names: Counter[str] = Counter()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "ix:nonfraction":
            name = dict(attrs).get("name")
            if name:
                self.names[name] += 1


def audit_quality_sources(filings: list[tuple[bytes, dict]], v12: dict) -> dict:
    if len(filings) != 2 or {f[1].get("accession") for f in filings} != set(PINS):
        raise ValueError("ORIGINAL_TWO_FILINGS_REQUIRED")
    if (v12.get("schema") != "M10_V12_QUALITY_ACCEPTANCE_AUDIT_V1" or
            v12.get("task9") != "PARTIAL" or v12.get("task10") != "BLOCKED" or
            v12.get("new_full_research_scores") != 0):
        raise ValueError("V12_QUALITY_BASELINE_CHANGED")
    s13 = v12["S13"]
    s14 = v12["INOD_S14"]
    if (s13.get("issuer") != "INOD" or s13.get("source_findings") != 27 or
            s13.get("required_blocks") != 7 or s13.get("signed_blocks") != 0 or
            any(block.get("signed") for block in s13["blocks"].values()) or
            s14.get("accepted_legs") != 3 or s14.get("legs", {}).get("S11") != 0 or
            s14.get("S14") is not None or s14["gate"].get("S6_verified_inputs") != 5 or
            s14["gate"].get("B_Q_DEPI") is not None or s14["gate"].get("B_Q_LVGI") is not None):
        raise ValueError("V12_S13_S14_ACCEPTANCE_STATE_CHANGED")

    rows = []
    for body, prior in sorted(filings, key=lambda item: item[1]["accession"]):
        accession = prior["accession"]
        digest = sha256(body).hexdigest()
        if (digest != PINS[accession][0] or prior.get("body_sha256") != digest or
                prior.get("source_ref") != PINS[accession][1] or
                prior.get("accounting_classification_accepted") is not False):
            raise ValueError("ORIGINAL_FILING_OR_PRIOR_RECEIPT_CHANGED")
        parser = _Names()
        parser.feed(body.decode("utf-8"))
        names = parser.names
        inventory = sorted(name for name in names if "inventor" in name.lower())
        pure_depreciation = sorted(name for name in names if name == "us-gaap:Depreciation")
        long_investment = sorted(name for name in names if "longterminvestment" in name.lower())
        short_balance = sorted(name for name in names if name == "us-gaap:OtherShortTermInvestments")
        combined_depreciation = sorted(name for name in names
                                       if name == "us-gaap:DepreciationDepletionAndAmortization")
        obligations = sorted(name for name in names if name.startswith("inod:") and "obligation" in name.lower())
        prior_short = prior.get("short_term_investment_monetary_candidates", [])
        if bool(short_balance) != bool(prior_short) or bool(inventory) != (not prior["inventory_tag_absent"]):
            raise ValueError("V13_IXBRL_CENSUS_CONFLICT")
        rows.append({
            "accession": accession, "body_sha256": digest,
            "ix_nonfraction_rows": sum(names.values()), "unique_ix_nonfraction_names": len(names),
            "inventory_names": inventory, "pure_depreciation_names": pure_depreciation,
            "combined_depreciation_names": combined_depreciation,
            "long_term_investment_names": long_investment,
            "short_term_investment_balance_names": short_balance,
            "short_term_investment_candidates": prior_short,
            "inod_obligation_names": obligations,
            "preferred_value_nil_rows": sum(r["name"] == "us-gaap:PreferredStockValue" and
                                            r["nil"] == "true" for r in prior["watched_fact_rows"]),
            "missing_tag_inferred_zero": False,
        })
    return {
        "schema": "V14_INOD_QUALITY_BROAD_IXBRL_CENSUS_V1", "ticker": "INOD",
        "filings": rows, "S6_verified_inputs": 5, "B_Q_verified_risks": 5,
        "S13_signed_blocks": 0, "S14_accepted_legs": 3,
        "STI_LTI_PREF_and_WC_NCO_FIN_classification_accepted": False,
        "inventory_delta_accepted": False,
        "pure_depreciation_accepted": False,
        "TOTAL_DEBT_LVGI_accepted": False,
        "S6": None, "B_Q": None, "S13": None, "S14": None,
        "task9": "PARTIAL", "task10": "BLOCKED", "new_full_research_scores": 0,
    }
