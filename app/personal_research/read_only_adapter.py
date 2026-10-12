"""Validate sealed legacy research receipts without promoting their status."""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

from .contracts import digest


def load_sealed_json(path) -> dict:
    path = Path(path)
    seal = Path(str(path) + ".sha256")
    if not path.is_file() or not seal.is_file() or path.is_symlink() or seal.is_symlink():
        raise FileNotFoundError(f"Sealed local receipt unavailable: {path}")
    raw = path.read_bytes()
    sealed = seal.read_text(encoding="utf-8").strip().split()[0].lower()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != sealed:
        raise ValueError(f"Receipt SHA mismatch: {path}")
    return json.loads(raw.decode("utf-8"))


def imported_legacy_diagnostics(ticker: str, evidence_root) -> dict:
    """Private receipts remain private and explicitly marked historically unverified."""
    root = Path(evidence_root)
    result = {"ticker": ticker, "S6": {}, "B_Q": {}, "S13": {},
              "receipts": [], "source_quality": "LOCAL_RECEIPTS_NOT_PIT_PROOF"}
    options = {
        "INOD": [
            (root / ".scoring_v4_private/s6/rsst_v4.json", "S6"),
            (root / ".scoring_v4_private/beneish/replay1/beneish_v4.json", "B_Q"),
            (root / ".master_tasks_v14_private/quality/inod_broad_ixbrl_census_v1.json", "quality"),
        ],
    }
    for path, model in options.get(ticker, []):
        try:
            data = load_sealed_json(path)
        except (OSError, ValueError, IndexError, json.JSONDecodeError) as exc:
            result["receipts"].append({"path_type": model, "status": "MISSING_OR_INVALID",
                                       "reason": str(exc)})
            continue
        result["receipts"].append({
            "path_type": model, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "status": "SEALED_LOCAL_RESEARCH_RECEIPT",
        })
        if model == "S6":
            years = data.get("years", {})
            try:
                totals = {}
                for year in ("2024", "2025"):
                    sample = years[year]["facts"]
                    a = Decimal(sample["assets"]["value"])
                    cash = Decimal(sample["cash"]["value"])
                    liabilities = Decimal(sample["liabilities"]["value"])
                    totals[year] = (a, a - cash - liabilities)
                denom = (totals["2025"][0] + totals["2024"][0]) / Decimal(2)
                recalculated = (totals["2025"][1] - totals["2024"][1]) / denom
                if denom <= 0 or abs(recalculated - Decimal(data["RSST_decimal"])) > Decimal("1e-20"):
                    raise ValueError("Independent S6 Decimal RSST replay failed")
            except (KeyError, ValueError, ArithmeticError, TypeError) as exc:
                result["receipts"].append({"path_type": "S6_INDEPENDENT_DECIMAL",
                                           "status": "REPLAY_FAILED", "reason": str(exc)})
                continue
            result["S6"] = {
                "RSST_candidate": data.get("RSST_research_candidate"),
                "RSST_decimal": data.get("RSST_decimal"),
                "average_assets_usd": data.get("average_assets_usd"),
                "missing": data.get("missing"),
                "source_hashes": data.get("filing_bodies_sha256"),
                "original_accepted": data.get("RSST_frozen_accepted", False),
                "independent_decimal_replay": "PASS",
                "source_input_matrix": [
                    {"fiscal_year": year, "metric": name,
                     "value": source.get("value"), "unit": source.get("unit"),
                     "concept": source.get("tag"),
                     "period_end": source.get("period_end"),
                     "accession": source.get("accession"),
                     "filing_date": source.get("filed"),
                     "record_sha256": source.get("record_sha256"),
                     "classification": "SOURCE_DERIVED_LOCAL_SEALED_RECEIPT",
                     "historical_pit_verified": False}
                    for year, segment in sorted(data.get("years", {}).items())
                    for name, source in segment.get("facts", {}).items()
                ],
            }
        if model == "B_Q":
            result["B_Q"] = {
                "ratios": data.get("preserved_ratios", {}),
                "coverage": data.get("verified_risk_count"),
                "missing": data.get("missing", []),
                "source_filings": [
                    {k: v for k, v in filing.items() if k in
                     ("accession", "source_ref", "sha256", "retrieved_at",
                      "source_authenticity_independently_verified")}
                    for filing in data.get("sources", [])
                ],
            }
        if model == "quality":
            result["source_census"] = {
                key: data.get(key) for key in ("S6_verified_inputs", "B_Q_verified_risks",
                                               "S13_signed_blocks", "S14_accepted_legs")
            }
    # V10 sealed accounting component is a complete source-backed DEPI
    # calculation, never a completed seven-leg B_Q model.
    path = root / ".scoring_v10_private/quality/component_evidence_v2.json"
    try:
        version = load_sealed_json(path)
        evidence = version.get("components", {}).get(ticker)
        if (evidence and evidence.get("frozen_source_sha256") ==
                "53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794"):
            result["B_Q"]["fiscal_end"] = evidence.get("fiscal_end")
            if evidence.get("depi_ratio") is not None:
                facts = evidence["inputs"]
                cur_dep = Decimal(facts["dep_current"]["value"])
                old_dep = Decimal(facts["dep_prior"]["value"])
                cur_ppe = Decimal(facts["ppe_current"]["value"])
                old_ppe = Decimal(facts["ppe_prior"]["value"])
                if not min(cur_dep, old_dep, cur_ppe, old_ppe) > 0:
                    raise ValueError("Invalid pure-depreciation financial denominators")
                ratio = (old_dep / (old_dep + old_ppe)) / (cur_dep / (cur_dep + cur_ppe))
                reference = Decimal(evidence["depi_ratio_decimal"])
                if abs(ratio - reference) > Decimal("1e-20"):
                    raise ValueError("DEPI independent Decimal replay mismatch")
                result["B_Q"]["verified_partial_DEPI"] = {
                    "ratio": float(ratio),
                    "normalized_risk": float(max(Decimal(0), min(Decimal(1),
                        (ratio - Decimal(1)) / Decimal(".75")))),
                    "status": "SOURCE_DERIVED_LOCAL_SEALED_RESEARCH_COMPONENT",
                    "ratio_from_v10": str(reference),
                    "accession": evidence["current_accession"],
                    "fiscal_end": evidence["fiscal_end"],
                    "inputs": facts,
                    "companyfacts_sha256": evidence["companyfacts_sha256"],
                    "receipt_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "historical_pit_accepted": False,
                    "whole_bq_accepted": False,
                }
            result["receipts"].append({
                "path_type": "V10_DEPI", "status": "SEALED_LOCAL_RESEARCH_RECEIPT",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    except (ValueError, OSError, IndexError, KeyError, ArithmeticError,
            json.JSONDecodeError) as exc:
        result["receipts"].append(
            {"path_type": "V10_DEPI", "status": "MISSING_OR_INVALID", "reason": str(exc)})
    if ticker == "INOD":
        path = root / ".scoring_v5_private/s13/s13_expert_form_v5.json"
        try:
            data = load_sealed_json(path)
            result["S13"] = {
                "signed": data.get("all_decisions_signed", False),
                "expert_blocks": data.get("blocks"),
                "source_packet": data,
                "source_packet_sha256": data.get("source_packet_sha256"),
                "status": data.get("status"),
                "receipt_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "source_quality": "UNSIGNED_EXPERT_FORM_LOCAL_SEALED",
            }
        except (ValueError, OSError, IndexError, json.JSONDecodeError) as exc:
            result["S13"] = {"status": "UNAVAILABLE", "reason": str(exc)}
    result["diagnostic_receipt_sha256"] = digest(result)
    return result
