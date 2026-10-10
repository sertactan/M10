"""Phase25X read-only, fail-closed audit of Phase25W research candidates."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from pathlib import Path

SCHEMA = "phase25x_research_evidence_matrix_v1"
# SEC filing-detail pages are public anchors; time strings are SEC page display times.
SEC_ANCHORS = {
    "BRLT": ("0001866757", "0001866757-25-000038", "2025-03-13 17:12:35", "https://www.sec.gov/Archives/edgar/data/1866757/000186675725000038/0001866757-25-000038-index.htm"),
    "BBCP": ("0001703956", "0001437749-25-000800", "2025-01-10 08:30:35", "https://www.sec.gov/Archives/edgar/data/1703956/000143774925000800/0001437749-25-000800-index.htm"),
    "BKE": ("0000885245", "0000885245-24-000051", "2024-04-03 15:59:57", "https://www.sec.gov/Archives/edgar/data/885245/000088524524000051/0000885245-24-000051-index.htm"),
    "AIV": ("0000922864", "0000950170-25-025775", "2025-02-24 17:05:21", "https://www.sec.gov/Archives/edgar/data/922864/000095017025025775/0000950170-25-025775-index.htm"),
    "CNA": ("0000021175", "0000021175-25-000008", "2025-02-11 10:26:27", "https://www.sec.gov/Archives/edgar/data/21175/000002117525000008/0000021175-25-000008-index.htm"),
    "AMSF": ("0001018979", "0000950170-25-030059", "2025-02-28 16:28:37", "https://www.sec.gov/Archives/edgar/data/1018979/000095017025030059/0000950170-25-030059-index.htm"),
    "ACGL": ("0000947484", "0000947484-25-000017", "2025-02-27 16:14:56", "https://www.sec.gov/Archives/edgar/data/947484/000094748425000017/0000947484-25-000017-index.htm"),
    "AFBI": ("0001823406", "0000950170-25-043249", "2025-03-21 16:30:34", "https://www.sec.gov/Archives/edgar/data/1823406/000095017025043249/0000950170-25-043249-index.htm"),
}
ORDER = tuple(SEC_ANCHORS)
GATES = ("historical_cik_share_class", "full_corporate_actions", "independent_adjusted_price", "delisting_terminal_payoff", "sec_publication_and_feature_available_at", "contemporaneous_pit_membership")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def audit(w: dict, p24: dict, connection: sqlite3.Connection) -> dict:
    if w.get("schema") != "MERIDYEN_PHASE25W_RESEARCH_PILOT_FAIL_CLOSED_V1" or w.get("research_only_pilot_selected") != 25:
        raise ValueError("Expected complete Phase25W 25-security research-only pilot")
    if w.get("conflict_rows") != 464 or w.get("conflict_rows_canonically_resolved") != 0:
        raise ValueError("Phase25W identity quarantine is not intact")
    if len(w.get("conflict_quarantine_rows", [])) != 464 or any(not row.get("conflicting_company_identity_quarantined") for row in w["conflict_quarantine_rows"]):
        raise ValueError("Phase25W per-row identity quarantine is not intact")
    if w.get("canonical_accepted_securities_proven") != 0:
        raise ValueError("Phase25W canonical baseline changed")
    pilot = {r["ticker"]: r for r in w["pilot_candidates"]}
    phase24 = {(r["ticker_strings"][0], str(r["SimFinId"])): r for r in p24["candidate_records"] if len(r["ticker_strings"]) == 1}
    if len(pilot) != 25 or any(t not in pilot for t in ORDER):
        raise ValueError("Selected cohort is not a subset of 25 distinct pilot tickers")
    rows = []
    for ticker in ORDER:
        candidate = pilot[ticker]
        simfin_id = str(candidate["simfin_id"])
        mapping = phase24.get((ticker, simfin_id))
        cik, accession, accepted, sec_url = SEC_ANCHORS[ticker]
        if mapping is None or mapping.get("candidate_CIKs_NOT_verified") != [cik]:
            raise ValueError(f"Phase24 present-day CIK candidate mismatch: {ticker}")
        securities = connection.execute("SELECT security_id, cik, exchange, security_type, delisted_date FROM security_master WHERE ticker=?", (ticker,)).fetchall()
        matching = [s for s in securities if s[1] == cik]
        if len(matching) != 1:
            raise ValueError(f"Local CIK/security binding mismatch: {ticker}")
        sid, _, exchange, security_type, delisted_date = matching[0]
        facts = connection.execute("""SELECT COUNT(*), COUNT(DISTINCT accession_number),
            SUM(CASE WHEN accepted_at IS NOT NULL THEN 1 ELSE 0 END),
            SUM(CASE WHEN available_at IS NOT NULL THEN 1 ELSE 0 END)
            FROM fundamental_facts_source WHERE security_id=?
            AND period_end BETWEEN '2024-01-01' AND '2025-09-30'""", (sid,)).fetchone()
        anchor = connection.execute("""SELECT COUNT(*), MIN(available_at), MAX(available_at),
            SUM(CASE WHEN accepted_at IS NOT NULL THEN 1 ELSE 0 END)
            FROM fundamental_facts_source WHERE security_id=? AND REPLACE(accession_number,'-','')=?""",
            (sid, accession.replace("-", ""))).fetchone()
        # One public annual filing and a current local CIK provide a useful lead,
        # never a full historical daily issuer/share-class chain.
        status = {
            "historical_cik_share_class": "PARTIAL",
            "full_corporate_actions": "BLOCKED",
            "independent_adjusted_price": "BLOCKED",
            "delisting_terminal_payoff": "BLOCKED",
            "sec_publication_and_feature_available_at": "PARTIAL" if anchor[0] else "BLOCKED",
            "contemporaneous_pit_membership": "BLOCKED",
        }
        missing = [
            "dated daily CIK, exchange and traded share-class continuity across full interval",
            "complete split, cash/stock dividend, spin-off and merger action ledger with rights",
            "independent vendor adjusted daily prices and adjustment-method reconciliation",
            "delisting/terminal cash-or-share payoff and exit audit",
            "per-accession public publication clock and independently logged feature ingestion available_at",
            "2024-2025 contemporaneously captured PIT membership rather than 2026 retrospective files",
        ]
        rows.append({"ticker": ticker, "simfin_id": simfin_id, "source_price_rows": candidate["source_price_rows"],
                     "source_months": candidate["months_with_ticker_source_listing"], "present_day_cik_candidate": cik,
                     "local_exchange": exchange, "local_security_type": security_type, "local_delisted_date": delisted_date,
                     "sec_filing_anchor": {"accession": accession, "accepted_sec_display_time": accepted, "url": sec_url,
                                            "local_matching_fact_rows": anchor[0], "local_fact_available_at_min": anchor[1],
                                            "local_fact_available_at_max": anchor[2], "local_fact_accepted_at_rows": anchor[3] or 0},
                     "local_period_fact_rows": facts[0], "local_period_accessions": facts[1],
                     "local_period_accepted_at_rows": facts[2] or 0, "local_period_available_at_rows": facts[3] or 0,
                     "gate_status": status, "missing_evidence": missing, "overall": "BLOCKED",
                     "canonical_admitted": False})
    return {"schema": SCHEMA, "status": "RESEARCH_ONLY_CANONICAL_BLOCKED", "selected_from_phase25w": len(rows),
            "phase25w_pilot_count": len(pilot), "phase25w_conflict_rows_quarantined": w["conflict_rows"],
            "period": w["period"], "candidates": rows, "gate_names": list(GATES),
            "canonical_accepted_securities_proven": 0, "canonical_accepted_security_dates_proven": 0,
            "required_missing_provider": "Independent historical PIT security master, corporate-action-complete adjusted daily price and delisting/terminal-payoff provider with timestamped source/ingestion lineage; verified SEC publication/feature availability archive",
            "wf9_status": "BLOCKED", "operational_db_modified": False, "source_files_modified": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase25w", type=Path, required=True)
    parser.add_argument("--phase24", type=Path, required=True)
    parser.add_argument("--operational-db", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    private_root = (Path(os.environ["LOCALAPPDATA"]) / "S153ResearchTerminal" / "runtime" / "phase25x").resolve()
    if not args.out.resolve().is_relative_to(private_root):
        parser.error("Output must stay inside the private LOCALAPPDATA phase25x directory")
    if args.out.exists():
        parser.error("Output must be a new private path (create-only)")
    if not all(p.is_file() for p in (args.phase25w, args.phase24, args.operational_db)):
        parser.error("Required existing source is missing")
    before = {str(p): sha256(p) for p in (args.phase25w, args.phase24)}
    w, p24 = read_json(args.phase25w), read_json(args.phase24)
    uri = args.operational_db.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        result = audit(w, p24, db)
    after = {str(p): sha256(p) for p in (args.phase25w, args.phase24)}
    if before != after:
        raise RuntimeError("Input source changed during read-only audit")
    result["input_sha256"] = before
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "selected": len(result["candidates"]),
                      "canonical": result["canonical_accepted_securities_proven"], "wf9": result["wf9_status"],
                      "report": str(args.out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()






