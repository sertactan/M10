"""Private, read-only scoring acceptance inside the packaged Windows EXE."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window import ResearchTerminalWindow


MODEL_COLUMNS = {"S7": 3, "S12": 4, "S11": 5, "S9": 6, "S14": 7,
                 "S16-E": 11, "S16-C": 12}


def _sealed_comparison() -> tuple[dict, str]:
    value = os.environ.get("M10_V12_COMPARISON_RECEIPT")
    if not value:
        raise ValueError("M10_V12_COMPARISON_RECEIPT_REQUIRED")
    path = Path(value)
    raw = path.read_bytes()
    digest = sha256(raw).hexdigest()
    if Path(str(path) + ".sha256").read_text("ascii").strip() != digest:
        raise ValueError("V12_COMPARISON_SEAL_CHANGED")
    result = json.loads(raw)
    if result["full_research_scores"] != 17 or result["canonical_pit_features"] != 0:
        raise ValueError("V12_COMPARISON_ACCEPTANCE_CHANGED")
    return result, digest


def _check(window: ResearchTerminalWindow, comparison: dict) -> dict:
    page = getattr(window, "scoring_completion_page", None)
    if page is None:
        raise ValueError("SCORING_COMPLETION_TAB_MISSING")
    window.tabs.setCurrentWidget(page)
    page.refresh()
    if page.report is None or page.comparison.rowCount() != 5 or page.comparison.columnCount() != 15:
        raise ValueError("PACKAGED_SCORING_SOURCE_OR_TABLE_MISSING")
    if page.report["full_model_count"] != 17 or page.report["canonical_securities"] != 0:
        raise ValueError("PACKAGED_RESEARCH_OR_CANONICAL_COUNT_CHANGED")
    if "not live" not in page.status.text() or page.comparison.horizontalHeaderItem(1).text() != "Cached price":
        raise ValueError("DATED_CACHED_PRICE_LABEL_MISSING")
    for row, stock in enumerate(comparison["stocks"]):
        cell = lambda col: page.comparison.item(row, col).text()
        if cell(0) != stock["ticker"] or cell(2) != stock["price_time"]:
            raise ValueError("ISSUER_OR_PRICE_TIME_CHANGED")
        for model, col in MODEL_COLUMNS.items():
            score = stock["models"][model]["score"]
            expected = "N/A" if score is None else f"{score:.2f}"
            if cell(col) != expected:
                raise ValueError(f"PACKAGED_SCORE_CHANGED:{stock['ticker']}:{model}")
        if len(stock["all_source_models"]) != 20:
            raise ValueError("ORIGINAL_MODEL_INVENTORY_CHANGED")
    if page.comparison.item(0, 5).text() != "0.00":
        raise ValueError("INOD_TRUE_ZERO_S11_MISSING")
    return {"stocks": 5, "columns": 15, "research_scores": 17,
            "canonical_pit_features": 0, "s16_e": "OFF", "s14_inod": "N/A"}


def run(output: Path) -> int:
    if not getattr(sys, "frozen", False):
        raise ValueError("PACKAGED_EXE_REQUIRED")
    if not os.environ.get("S153_RUNTIME_ROOT") or not os.environ.get("LOCALAPPDATA"):
        raise ValueError("ISOLATED_RUNTIME_AND_LOCALAPPDATA_REQUIRED")
    if not all(os.environ.get(key) for key in ("M10_PHASE27_STAGING_DB",
                                                "M10_PHASE28_STAGING_DB",
                                                "M10_SCORING_COMPLETION_REPORT")):
        raise ValueError("PRIVATE_SCORING_SOURCE_PATHS_REQUIRED")
    comparison, comparison_sha = _sealed_comparison()
    application = QApplication.instance() or QApplication([])
    first = ResearchTerminalWindow()
    first.show()
    application.processEvents()
    if not first.isVisible():
        raise ValueError("PACKAGED_MAIN_WINDOW_NOT_OPEN")
    checks = _check(first, comparison)
    application.processEvents()

    original_local = os.environ["LOCALAPPDATA"]
    try:
        os.environ["LOCALAPPDATA"] = str(output.parent / "missing_private_source")
        first.scoring_completion_page.refresh()
        fail_closed = (first.scoring_completion_page.report is None
                       and first.scoring_completion_page.comparison.rowCount() == 0
                       and "MISSING / INVALID / SOURCE CHANGED" in first.scoring_completion_page.status.text())
    finally:
        os.environ["LOCALAPPDATA"] = original_local
    if not fail_closed:
        raise ValueError("MISSING_PRIVATE_SOURCE_NOT_FAIL_CLOSED")
    first.close()
    application.processEvents()
    if first.isVisible():
        raise ValueError("FIRST_WINDOW_DID_NOT_CLOSE")

    second = ResearchTerminalWindow()
    second.show()
    application.processEvents()
    if not second.isVisible() or _check(second, comparison) != checks:
        raise ValueError("PACKAGED_REOPEN_CHANGED")
    second.close()
    application.processEvents()
    if second.isVisible():
        raise ValueError("SECOND_WINDOW_DID_NOT_CLOSE")

    exe = Path(sys.executable)
    receipt = {"schema": "M10_V13_PACKAGED_WINDOWS_ACCEPTANCE_V1", "status": "PASS",
               "executable": str(exe), "executable_sha256": sha256(exe.read_bytes()).hexdigest(),
               "comparison_sha256": comparison_sha, "runtime_root": os.environ["S153_RUNTIME_ROOT"],
               "source_localappdata": original_local, "checks": checks,
               "missing_source_fail_closed": True, "window_open_close_reopen": True}
    encoded = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(encoded)
    with Path(str(output) + ".sha256").open("x", encoding="ascii") as stream:
        stream.write(sha256(encoded).hexdigest() + "\n")
    return 0
