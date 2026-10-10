"""Open/close actual isolated research comparison UI with sealed offline data.

No production factories, installation, network, database mutation, or EXE build.
The opt-in report must be validated by its built-in source/hash loader.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication
from app.ui.scoring_completion_page import ScoringCompletionPage


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--report",required=True,type=Path)
    cli.add_argument("--phase27",required=True,type=Path)
    cli.add_argument("--phase28",required=True,type=Path)
    args=cli.parse_args()
    app=QApplication.instance() or QApplication([])
    page=ScoringCompletionPage(args.report,args.phase27,args.phase28)
    try:
        page.refresh()
        if page.report is None:
            raise ValueError("Sealed source/report validation failed: "+page.status.text())
        if page.comparison.rowCount()!=5 or page.comparison.columnCount()!=11:
            raise ValueError("V2 Windows staging comparison shape invalid")
        if page.report.get("full_model_count")!=9:
            raise ValueError("Unexpected promoted research score count")
        if not all(page.comparison.item(i, j).text()=="N/A"
                   for i in range(5) for j in (5,7,8)):
            raise ValueError("S14/S16-E/S16-C are incorrectly promoted")
        if page.comparison.item(0,6).text()!="2/6":
            raise ValueError("INOD S14 coverage incorrectly promoted")
        if not page.report["stocks"][0].get("sec_companyfacts_partial"):
            raise ValueError("Expected official research-only SEC partial receipt")
        page.comparison.selectRow(0)
        page.select_stock()
        if ("sec_companyfacts_partial" not in page.details.toPlainText()
                or not page.details.isReadOnly()):
            raise ValueError("SEC partial evidence not visible in read-only detail")
        print(json.dumps({"result":"PASS","mode":os.environ.get("QT_QPA_PLATFORM"),
            "stocks":page.comparison.rowCount(),"columns":page.comparison.columnCount(),
            "full_research_scores":page.report["full_model_count"],
            "inod_S14_coverage":page.comparison.item(0,6).text(),
            "inod_sec_partial_ratios":page.report["stocks"][0]["sec_companyfacts_partial"]["available_ratio_count"],
            "canonical_securities":page.report["canonical_securities"],
            "personal_installer_touched":False,"database_mutated":False}))
    finally:
        page.close()
        app.processEvents()


if __name__=="__main__":
    main()
