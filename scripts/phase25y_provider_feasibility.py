"""Offline Phase25Y BKE provider-feasibility audit of existing private pilot reports."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

SCHEMA = "phase25y_bke_provider_feasibility_v1"
W_SCHEMA = "MERIDYEN_PHASE25W_RESEARCH_PILOT_FAIL_CLOSED_V1"
X_SCHEMA = "phase25x_research_evidence_matrix_v1"
REQUIRED_GATES = (
    "historical_cik_share_class", "full_corporate_actions",
    "independent_adjusted_price", "delisting_terminal_payoff",
    "sec_publication_and_feature_available_at", "contemporaneous_pit_membership",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(w: dict, x: dict) -> dict:
    if w.get("schema") != W_SCHEMA or w.get("research_only_pilot_selected") != 25:
        raise ValueError("Phase25W pilot must contain 25 research-only securities")
    if w.get("conflict_rows") != 464 or w.get("conflict_rows_canonically_resolved") != 0:
        raise ValueError("Phase25W identity quarantine changed")
    if w.get("canonical_accepted_securities_proven") != 0:
        raise ValueError("Phase25W canonical baseline changed")
    if x.get("schema") != X_SCHEMA or x.get("phase25w_pilot_count") != 25:
        raise ValueError("Expected Phase25X evidence matrix")
    if x.get("canonical_accepted_securities_proven") != 0 or x.get("canonical_accepted_security_dates_proven") != 0:
        raise ValueError("Phase25X canonical baseline changed")
    if x.get("phase25w_conflict_rows_quarantined") != 464:
        raise ValueError("Phase25X identity quarantine changed")
    pilot = [row for row in w.get("pilot_candidates", []) if row.get("ticker") == "BKE"]
    rows = [row for row in x.get("candidates", []) if row.get("ticker") == "BKE"]
    if len(pilot) != 1 or len(rows) != 1:
        raise ValueError("BKE must appear once in both prior reports")
    row = rows[0]
    if str(pilot[0].get("simfin_id")) != str(row.get("simfin_id")) or row.get("present_day_cik_candidate") != "0000885245":
        raise ValueError("BKE identity lead differs across prior reports")
    if row.get("overall") != "BLOCKED" or row.get("canonical_admitted") is not False:
        raise ValueError("Phase25X BKE canonical decision changed")
    if set(row.get("gate_status", {})) != set(REQUIRED_GATES):
        raise ValueError("Phase25X BKE gate coverage incomplete")
    if any(row["gate_status"][gate] == "PASS" for gate in REQUIRED_GATES):
        raise ValueError("Provider feasibility cannot assume canonical gate PASS")
    anchor = row.get("sec_filing_anchor", {})
    if anchor.get("accession") != "0000885245-24-000051" or anchor.get("local_fact_accepted_at_rows") != 0:
        raise ValueError("BKE SEC accepted-time anchor changed")
    return {
        "schema": SCHEMA,
        "ticker": "BKE",
        "window": x.get("period"),
        "purpose": "RESEARCH_ONLY_PROVIDER_FEASIBILITY",
        "prior_gate_status": row["gate_status"],
        "local_source_price_rows": row["source_price_rows"],
        "retrospective_month_listings": row["source_months"],
        "local_sec_fact_rows": row["local_period_fact_rows"],
        "local_sec_fact_rows_with_accepted_at": row["local_period_accepted_at_rows"],
        "official_sec_anchor": anchor,
        "provider_data_acquired": False,
        "provider_coverage_for_bke_verified": False,
        "corporate_actions_complete_verified": False,
        "independent_adjusted_prices_verified": False,
        "feature_available_at_verified": False,
        "canonical_accepted_securities_proven": 0,
        "canonical_accepted_security_dates_proven": 0,
        "wf9_status": "BLOCKED",
        "blocker": "No acquired independent daily adjusted-price/action/delisting feed or archived feature ingestion timeline; provider catalogue is procurement feasibility only.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase25w", required=True, type=Path)
    parser.add_argument("--phase25x", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    private_root = (Path(os.environ["LOCALAPPDATA"]) / "S153ResearchTerminal" / "runtime" / "phase25y").resolve()
    if not args.out.resolve().is_relative_to(private_root):
        parser.error("Output must stay in private LOCALAPPDATA phase25y directory")
    if args.out.exists():
        parser.error("Output must be create-only")
    for source in (args.phase25w, args.phase25x):
        if not source.is_file():
            parser.error(f"Existing report missing: {source}")
    with args.phase25w.open(encoding="utf-8") as stream:
        w = json.load(stream)
    with args.phase25x.open(encoding="utf-8") as stream:
        x = json.load(stream)
    result = audit(w, x)
    result["input_sha256"] = {"phase25w": sha256(args.phase25w), "phase25x": sha256(args.phase25x)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    print(json.dumps({"output": str(args.out), "sha256": sha256(args.out), "ticker": "BKE", "canonical": 0, "wf9": "BLOCKED"}))


if __name__ == "__main__":
    main()
