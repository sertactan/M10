"""Fail-closed V12 quality acceptance audit. No model score is inferred."""
from __future__ import annotations

from hashlib import sha256
from decimal import Decimal, localcontext
import json
import re

from app.scoring_v10_quality import depreciation_component, inod_quality_gate
from app.scoring_v10_extension_s6 import candidate_from_pinned_sec
from app.scoring_v7_piotroski import _entry
from app.scoring_v9_s8_s10 import verify_frozen_source
from scripts.scoring_v11_beneish_inventory import audit_one, CONCEPTS

CONTRACT_SHA = "53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794"
BLOCKS = ("AUD", "RPT", "REC", "DIL", "REV", "ACQ", "GOV")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ALTERNATE_CONCEPTS = {
    "SALES": ("Revenues", "RevenueFromContractWithCustomerIncludingAssessedTax", "OtherSalesRevenueNet"),
    "COGS": ("CostOfGoodsAndServicesSold",),
    "SGA": ("GeneralAndAdministrativeExpense", "SellingAndMarketingExpense"),
    "CURRENT_DEBT_CANDIDATE": ("ConvertibleDebt",),
    "NONCURRENT_DEBT_CANDIDATE": ("ConvertibleDebtNoncurrent",),
}


def verified_json(raw: bytes, seal: bytes) -> dict:
    if seal.decode("ascii").strip() != sha256(raw).hexdigest():
        raise ValueError("SOURCE_RECEIPT_SEAL_CHANGED")
    return json.loads(raw)


def beneish_packet(ticker: str, raw: bytes) -> dict:
    """Recheck exact pinned comparative rows; list unmapped concepts for filing review."""
    base = audit_one(ticker, raw)
    gaap = json.loads(raw)["facts"]["us-gaap"]
    unresolved = {}
    for field in sorted({item.split(".", 1)[1] for item in base["missing_exact_candidate_tags"]}):
        # Exact same-accession comparative rows are candidate mappings only.
        # Accounting scope and addition of expense lines still need review.
        candidates = []
        for tag in ALTERNATE_CONCEPTS.get(field, ()):
            if tag not in gaap:
                continue
            rows = {period: _entry(gaap, tag, base["original_accession"],
                                   base["periods"][period]["TA"]["end"], flow=field not in
                                   ("CURRENT_DEBT_CANDIDATE", "NONCURRENT_DEBT_CANDIDATE"))
                    for period in ("current", "prior")}
            if any(row is not None and row["unit"] == "USD" for row in rows.values()):
                candidates.append({"tag": "us-gaap:" + tag,
                                   "periods": rows,
                                   "both_periods_exact": all(row is not None and row["unit"] == "USD"
                                                             for row in rows.values()),
                                   "accepted_mapping": False})
        unresolved[field] = candidates
    return {
        "ticker": ticker,
        "source_sha256": base["original_companyfacts_sha256"],
        "accession": base["original_accession"],
        "fiscal_periods": {key: {"end": rows["TA"]["end"] if rows["TA"] else None,
                                  "source_rows_present": sum(row is not None for row in rows.values()),
                                  "source_rows_required": len(CONCEPTS)}
                           for key, rows in base["periods"].items()},
        "missing_exact_tag_candidates": base["missing_exact_candidate_tags"],
        "unmapped_standard_concepts_for_review": unresolved,
        "pure_DEPI_ratio": base["DEPI_ratio"],
        "TOTAL_DEBT_scope_accepted": False,
        "serious_flags_reviewed": False,
        "B_Q": None,
        "S5": None,
        "status": "REVIEW_REQUIRED",
    }


def expert_packet(form: dict, form_sha: str) -> dict:
    if form.get("issuer") != "INOD" or set(form.get("blocks", {})) != set(BLOCKS):
        raise ValueError("EXPERT_FORM_ISSUER_OR_BLOCKS_CHANGED")
    if form.get("all_decisions_signed") is not False or form.get("S13") is not None:
        raise ValueError("EXPECTED_UNSIGNED_EXPERT_FORM_CHANGED")
    seen = set()
    blocks = {}
    for name in BLOCKS:
        item = form["blocks"][name]
        findings = item.get("source_findings", [])
        if not findings or item.get("signed") is not False or item.get("risk_level_0_25_50_75_100") is not None:
            raise ValueError("S13_REVIEW_STATE_CHANGED:" + name)
        for finding in findings:
            key = finding["finding_id"]
            if key in seen or not HEX64.fullmatch(finding.get("filing_body_sha256", "")) or not finding.get("source_ref"):
                raise ValueError("S13_FINDING_PROVENANCE_CHANGED")
            seen.add(key)
        blocks[name] = {
            "finding_count": len(findings),
            "finding_ids": [f["finding_id"] for f in findings],
            "source_accessions": sorted({f["accession"] for f in findings}),
            "context": item["mitigating_and_adverse_context"],
            "review_question": item["remaining_review"],
            "required_decision_fields": ["financial_materiality_reason", "risk_level_0_25_50_75_100",
                                         "independent_serious_issue_ids", "duplicate_issue_ids_excluded",
                                         "decision_rationale", "reviewer_name", "reviewed_at", "signed"],
            "signed": False,
        }
    if len(seen) != 27 or not HEX64.fullmatch(form.get("source_packet_sha256", "")):
        raise ValueError("S13_27_FINDING_PACKET_CHANGED")
    return {"issuer": "INOD", "form_sha256": form_sha,
            "source_packet_sha256": form["source_packet_sha256"],
            "source_findings": 27, "signed_blocks": 0, "required_blocks": 7,
            "cross_block_duplicate_review_complete": False,
            "independent_serious_flags_final": None,
            "blocks": blocks, "S13": None, "status": "REVIEW_REQUIRED"}


def inod_s14_packet(s9: dict, form: dict) -> dict:
    gate = inod_quality_gate(s9, form)
    from core.scoring.s1_s14 import s14
    legs = {"B_Q": None, "S6": None, "S7": 100.0, "S11": 0.0,
            "S12": 91.528866, "S13": None}
    score, parts = s14(legs)
    if score is not None or any(value is not None for value in parts.values()):
        raise ValueError("FROZEN_S14_MISSING_LEG_GATE_CHANGED")
    return {"gate": gate, "legs": legs, "accepted_legs": 3,
            "required_legs": 6, "S14": None,
            "S11_zero_is_accepted": True,
            "next_acceptance_test": "Replay six source-accepted legs through core.scoring.s1_s14.s14 and independent Decimal reference"}


def independent_s14_reference(legs: dict[str, float | None]) -> Decimal | None:
    """Independent high-precision reference; missing input never becomes zero."""
    names = ("B_Q", "S6", "S7", "S11", "S12", "S13")
    if any(legs.get(name) is None for name in names):
        return None
    with localcontext() as ctx:
        ctx.prec = 60
        D = lambda name: Decimal(str(legs[name]))
        values = [D(name) for name in names]
        if any(value < 0 or value > 100 for value in values):
            raise ValueError("S14_LEG_OUTSIDE_0_100")
        core = values[:5]
        weights = [Decimal(".20"), Decimal(".20"), Decimal(".15"),
                   Decimal(".20"), Decimal(".25")]
        geometric = sum(weight * max(value, Decimal(1)).ln()
                        for weight, value in zip(weights, core)).exp()
        mean = sum(core) / 5
        variance = sum((value - mean) ** 2 for value in core) / 5
        conflict = min(Decimal(10), Decimal(".20") * variance.sqrt())
        forensic = min(Decimal(15), Decimal(".15") * (100 - values[5]))
        return min(Decimal(100), max(Decimal(0), geometric - conflict - forensic))


def build_report(sec_raw: dict[str, bytes], s9: dict, form: dict, form_sha: str) -> dict:
    if verify_frozen_source() != CONTRACT_SHA:
        raise ValueError("FROZEN_QUALITY_CONTRACT_CHANGED")
    beneish = {ticker: beneish_packet(ticker, sec_raw[ticker]) for ticker in ("CRMD", "ETON", "PENG")}
    eton = candidate_from_pinned_sec(sec_raw["ETON"])
    if eton["S6_score"] is not None or eton["accepted_full_research"] is not False:
        raise ValueError("ETON_S6_CONDITIONAL_SCORE_PROMOTED")
    return {"schema": "M10_V12_QUALITY_ACCEPTANCE_AUDIT_V1",
            "frozen_source_sha256": CONTRACT_SHA, "scope": "CURRENT_RESEARCH_ONLY",
            "B_Q": beneish,
            "ETON_S6": {"source_sha256": eton["source_hash"],
                        "conditional_F_D": eton["F_D_conditional"],
                        "conditional_bin": eton["candidate_bin"],
                        "missing": eton["missing"], "accepted_score": None},
            "S13": expert_packet(form, form_sha),
            "INOD_S14": inod_s14_packet(s9, form),
            "new_full_research_scores": 0, "task9": "PARTIAL", "task10": "BLOCKED"}
