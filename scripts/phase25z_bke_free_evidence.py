"""BKE free-source evidence and optional bounded Nasdaq availability probe.

No raw OHLC series is persisted or redistributed. An observed raw Close response
is not a licensed, independently adjusted or PIT-available price certificate.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SCHEMA = "phase25z_bke_free_evidence_v1"
NASDAQ_ENDPOINT = "https://api.nasdaq.com/api/quote/BKE/historical"
WINDOWS = (("2024-01-01", "2025-09-30"), ("2024-01-01", "2024-10-08"))
# Dates/amounts transcribed from the linked SEC filing or issuer release.
# Ex-dates are deliberately null until BKE-specific exchange evidence is obtained.
EVENTS = (
    ("2023-12-04", "2023-12-05", "2024-01-12", "2024-01-26", 2.50, 0.35,
     "https://www.sec.gov/Archives/edgar/data/885245/000088524523000054/bke202312058-kdivex.htm"),
    ("2024-03-25", "2024-03-26", "2024-04-12", "2024-04-26", 0.00, 0.35,
     "https://www.sec.gov/Archives/edgar/data/885245/000088524524000049/bke202403268-kdivex.htm"),
    ("2024-06-03", "2024-06-04", "2024-07-12", "2024-07-26", 0.00, 0.35,
     "https://www.sec.gov/Archives/edgar/data/885245/000088524524000065/bke-20240603.htm"),
    ("2024-09-09", "2024-09-10", "2024-10-11", "2024-10-25", 0.00, 0.35,
     "https://corporate.buckle.com/investor-relations/press-releases/press-release-details/2024/The-Buckle-Inc.-Reports-Quarterly-Dividend-b5b69d6a7/default.aspx"),
    ("2024-12-09", "2024-12-10", "2025-01-15", "2025-01-29", 2.50, 0.35,
     "https://www.sec.gov/Archives/edgar/data/885245/000088524524000117/bke202412108-kdivex.htm"),
    ("2025-03-24", "2025-03-25", "2025-04-15", "2025-04-29", 0.00, 0.35,
     "https://corporate.buckle.com/investor-relations/press-releases/press-release-details/2025/The-Buckle-Inc--Reports-Quarterly-Dividend-and-Announces-the-Appointment-of-Justin-D--Ellison-as-Vice-President-of-Information-Security/default.aspx"),
    ("2025-06-02", "2025-06-03", "2025-07-15", "2025-07-29", 0.00, 0.35,
     "https://www.sec.gov/Archives/edgar/data/885245/000088524525000072/bke202506028-kdivex.htm"),
    ("2025-09-08", "2025-09-09", "2025-10-15", "2025-10-29", 0.00, 0.35,
     "https://corporate.buckle.com/investor-relations/press-releases/press-release-details/2025/The-Buckle-Inc--Reports-Quarterly-Dividend-4c3f50d21/default.aspx"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or linked prior report")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_prior(w: dict, x: dict, yb: dict) -> None:
    if (w.get("schema") != "MERIDYEN_PHASE25W_RESEARCH_PILOT_FAIL_CLOSED_V1"
            or w.get("research_only_pilot_selected") != 25 or w.get("conflict_rows") != 464
            or w.get("conflict_rows_canonically_resolved") != 0 or w.get("canonical_accepted_securities_proven") != 0
            or not any(r.get("ticker") == "BKE" and str(r.get("simfin_id")) == "196385" for r in w.get("pilot_candidates", []))):
        raise ValueError("Phase25W BKE/quarantine baseline changed")
    if (x.get("schema") != "phase25x_research_evidence_matrix_v1"
            or x.get("canonical_accepted_securities_proven") != 0 or x.get("wf9_status") != "BLOCKED"
            or not any(r.get("ticker") == "BKE" and r.get("overall") == "BLOCKED" for r in x.get("candidates", []))):
        raise ValueError("Phase25X BKE evidence baseline changed")
    if (yb.get("schema") != "phase25y_bke_provider_feasibility_v1"
            or yb.get("ticker") != "BKE" or yb.get("canonical_accepted_securities_proven") != 0
            or yb.get("wf9_status") != "BLOCKED"):
        raise ValueError("Phase25Y-B provider baseline changed")


def summarize_nasdaq_response(payload: bytes, start: str, end: str) -> dict:
    body = json.loads(payload)
    if body.get("status", {}).get("rCode") != 200 or not isinstance(body.get("data"), dict):
        raise ValueError("Nasdaq response is not successful data")
    data = body["data"]
    if data.get("symbol") != "BKE":
        raise ValueError("Nasdaq symbol mismatch")
    rows = data.get("tradesTable", {}).get("rows") or []
    if not isinstance(rows, list):
        raise ValueError("Nasdaq rows malformed")
    dates = [datetime.strptime(row["date"], "%m/%d/%Y").date().isoformat() for row in rows]
    if any(not start <= day <= end for day in dates) or len(set(dates)) != len(dates):
        raise ValueError("Nasdaq date outside requested range or duplicated")
    samples = [{"date": day, "source_close": row.get("close")}
               for day, row in zip(dates, rows) if day in {"2025-01-14", "2025-01-15", "2025-01-16"}]
    return {"request_start": start, "request_end": end,
            "response_sha256": hashlib.sha256(payload).hexdigest(), "row_count": len(rows),
            "first_date": min(dates) if dates else None, "last_date": max(dates) if dates else None,
            "field_names": sorted(rows[0]) if rows else [], "private_price_samples": samples,
            "has_adjusted_close_field": bool(rows and any("adjust" in key.lower() for key in rows[0]))}


def probe_nasdaq() -> list[dict]:
    summaries = []
    for start, end in WINDOWS:
        params = urlencode({"assetclass": "stocks", "limit": 500, "fromdate": start, "todate": end})
        request = Request(NASDAQ_ENDPOINT + "?" + params,
                          headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json",
                                   "Origin": "https://www.nasdaq.com"})
        with urlopen(request, timeout=20) as response:
            if response.status != 200:
                raise ValueError("Nasdaq transport status not 200")
            payload = response.read(3_000_001)
            if len(payload) > 3_000_000:
                raise ValueError("Nasdaq response exceeded bounded size")
        summaries.append(summarize_nasdaq_response(payload, start, end))
    return summaries


def build(w: dict, x: dict, yb: dict, price_probe: list[dict] | None) -> dict:
    validate_prior(w, x, yb)
    events = []
    for board, announced, record, payment, special, regular, url in EVENTS:
        if not (board <= announced < record < payment):
            raise ValueError("Invalid event chronology")
        events.append({"board_date": board, "announcement_date": announced,
                       "ex_date": None, "ex_date_status": "BKE_SPECIFIC_EX_DATE_NOT_VERIFIED",
                       "record_date": record, "payment_date": payment,
                       "special_cash_usd_per_share": special, "regular_cash_usd_per_share": regular,
                       "official_source_url": url, "official_document_scope": "ANNOUNCEMENT_ONLY_NOT_COMPLETE_ACTION_LEDGER"})
    return {"schema": SCHEMA, "ticker": "BKE", "cik": "0000885245", "simfin_id": "196385",
            "status": "RESEARCH_ONLY_PARTIAL_FREE_EVIDENCE", "window": {"start": "2024-01-01", "end": "2025-09-30"},
            "official_event_leads": events, "event_count": len(events),
            "nyse_generic_ex_date_rule_url": "https://www.nyse.com/trade/ex-date-dividends",
            "specific_ex_dates_verified": 0,
            "independent_price_probe": price_probe,
            "nasdaq_price_interpretation": "Public raw OHLC availability probe only; no verified dividend adjustment, terminal payoff, PIT snapshot or redistribution/API license.",
            "canonical_gates": {"historical_identity": "PARTIAL", "official_actions_full_interval": "BLOCKED",
                                "independent_adjusted_price": "BLOCKED", "delisting_terminal_payoff": "BLOCKED",
                                "sec_feature_available_at": "BLOCKED", "contemporaneous_membership": "BLOCKED",
                                "mature_252_session_labels": "BLOCKED"},
            "canonical_accepted_securities": 0, "canonical_accepted_security_dates": 0,
            "wf9_status": "BLOCKED", "learning_v3_status": "NOT_TRAINED",
            "required_acquisition": "Licensed complete adjusted daily price/actions/delisting source plus dated identity, PIT universe and archived SEC feature ingestion evidence.",
            "source_files_modified": False, "operational_db_opened": False}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("phase25w", "phase25x", "phase25y_b", "out"):
        p.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    p.add_argument("--online-probe", action="store_true", help="one bounded no-key Nasdaq availability probe")
    a = p.parse_args()
    root = (Path(os.environ["LOCALAPPDATA"]) / "S153ResearchTerminal" / "runtime").resolve()
    paths = (a.phase25w, a.phase25x, a.phase25y_b)
    if any(not path.resolve().is_relative_to(root) for path in paths):
        p.error("All inputs must be existing private runtime reports")
    if not a.out.resolve().is_relative_to(root / "phase25z") or a.out.exists() or a.out.is_symlink():
        p.error("Output must be new and private")
    before = {str(path): sha256(path) for path in paths}
    w, x, yb = [load(path) for path in paths]
    probe = probe_nasdaq() if a.online_probe else None
    result = build(w, x, yb, probe)
    if before != {str(path): sha256(path) for path in paths}:
        raise RuntimeError("Input report changed during audit")
    result["input_sha256"] = before
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "events": len(result["official_event_leads"]),
                      "price_rows": [r["row_count"] for r in probe] if probe else None,
                      "canonical": 0, "report": str(a.out)}))


if __name__ == "__main__":
    main()
