"""Isolated Windows Qt acceptance of the sealed V12 comparison."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.scoring_v9_report import NEW_REPORT
from app.ui.scoring_completion_page import ScoringCompletionPage

OUTPUT = Path("E:/M10/.master_tasks_v12_private/windows/staging_v2.json")


def run(verify: bool) -> dict:
    source = Path("E:/M10/.master_tasks_v12_private/comparison/five_stock_v2.json")
    source_seal = Path(str(source) + ".sha256")
    raw = source.read_bytes()
    if source_seal.read_text("ascii").strip() != sha256(raw).hexdigest():
        raise ValueError("V12_COMPARISON_SEAL_CHANGED")
    comparison = json.loads(raw)
    if comparison["full_research_scores"] != 17 or comparison["canonical_pit_features"] != 0:
        raise ValueError("V12_COMPARISON_ACCEPTANCE_CHANGED")
    rt = Path(os.environ["LOCALAPPDATA"]) / "S153ResearchTerminal/runtime"
    app = QApplication([])
    page = ScoringCompletionPage(NEW_REPORT, rt / "phase27/current_scoring/staging.db",
                                 rt / "phase28/real_scoring_v1/stage.db")
    result = {"schema": "M10_V12_WINDOWS_STAGING_V2", "status": "FAIL",
              "comparison_sha256": sha256(raw).hexdigest(),
              "installed_app_changed": False, "live_db_written": False}

    def validate() -> None:
        try:
            page.show()
            page.refresh()  # Replays original private SEC receipts.
            if page.report is None or page.comparison.rowCount() != 5 or page.comparison.columnCount() != 15:
                raise ValueError("WINDOW_OR_SOURCE_REPORT_MISSING")
            if "not live" not in page.status.text() or "Cached price" != page.comparison.horizontalHeaderItem(1).text():
                raise ValueError("DATED_PRICE_LABEL_MISSING")
            if page.report["full_model_count"] != 17 or page.report["canonical_securities"] != 0:
                raise ValueError("RESEARCH_OR_PIT_COUNT_CHANGED")
            for i, stock in enumerate(comparison["stocks"]):
                item = lambda j: page.comparison.item(i, j).text()
                if item(0) != stock["ticker"] or item(2) != stock["price_time"]:
                    raise ValueError("ISSUER_OR_PRICE_TIME_CHANGED")
                if item(11) != "N/A" or item(12) != "N/A" or item(7) != "N/A":
                    raise ValueError("ESTIMATED_CANONICAL_OR_S14_PROMOTED")
                if stock["ticker"] == "INOD" and item(5) != "0.00":
                    raise ValueError("INOD_TRUE_ZERO_S11_NOT_RENDERED")
            result.update(status="PASS", stocks=5, columns=15,
                          full_research_scores=17, canonical_pit_features=0,
                          s16_e="OFF", s14="N/A")
        except Exception as exc:
            result["error"] = type(exc).__name__ + ": " + str(exc)
        finally:
            page.close()
            app.quit()

    QTimer.singleShot(100, validate)
    result["qt_exit"] = app.exec()
    result["window_closed"] = not page.isVisible()
    encoded = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    digest = sha256(encoded).hexdigest()
    seal = Path(str(OUTPUT) + ".sha256")
    if verify:
        if OUTPUT.read_bytes() != encoded or seal.read_text("ascii").strip() != digest:
            raise ValueError("V12_WINDOWS_STAGING_REPLAY_CHANGED")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with OUTPUT.open("xb") as f:
            f.write(encoded)
        with seal.open("x", encoding="ascii") as f:
            f.write(digest + "\n")
    if result["status"] != "PASS" or not result["window_closed"]:
        raise ValueError("V12_WINDOWS_STAGING_FAILED:" + str(result.get("error")))
    return {"status": result["status"], "receipt_sha256": digest,
            "stocks": result["stocks"], "columns": result["columns"],
            "full_research_scores": result["full_research_scores"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.verify), sort_keys=True))
