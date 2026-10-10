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
        if page.comparison.rowCount()!=5 or page.comparison.columnCount()!=13:
            raise ValueError("V2 Windows staging comparison shape invalid")
        if page.report.get("full_model_count")!=9:
            raise ValueError("Unexpected promoted research score count")
        if not all(page.comparison.item(i, j).text()=="N/A"
                   for i in range(5) for j in (5,9,10)):
            raise ValueError("S14/S16-E/S16-C are incorrectly promoted")
        if page.comparison.item(0,6).text()!="2/6":
            raise ValueError("INOD S14 coverage incorrectly promoted")
        if (page.comparison.item(0,7).text() not in ('4/7','5/7') or
            page.comparison.item(0,8).text()!='4/7'):
            raise ValueError('V3 new SEC financial feature coverage not exposed')
        if not page.report["stocks"][0].get("sec_companyfacts_partial"):
            raise ValueError("Expected official research-only SEC partial receipt")
        forensic=page.report['stocks'][0].get('sec_forensic_v3')
        if forensic and (forensic['status']!='REVIEW_REQUIRED'
                         or forensic['body_filing_count']!=14
                         or forensic['reviewed_risk_block_count']!=0
                         or forensic['S13_score'] is not None):
            raise ValueError('SEC filing-body candidate evidence promoted without review')
        candidate=page.report['stocks'][0].get('sec_event_candidates_v3')
        if candidate and (candidate['count']!=10 or candidate['verified_early_alerts']!=0):
            raise ValueError('SEC event research candidates falsely promoted to early alerts')
        jones=page.report['stocks'][0].get('sec_jones_v3')
        if jones and (jones['target_exact_accounting_fields']!=8
                      or jones['eligible_industry_year_peers']!=0
                      or jones['S11'] is not None):
            raise ValueError('Invalid SEC Jones target/peer audit promotion')
        page.comparison.selectRow(0)
        page.select_stock()
        if ("sec_companyfacts_partial" not in page.details.toPlainText()
                or not page.details.isReadOnly()):
            raise ValueError("SEC partial evidence not visible in read-only detail")
        print(json.dumps({"result":"PASS","mode":os.environ.get("QT_QPA_PLATFORM"),
            "stocks":page.comparison.rowCount(),"columns":page.comparison.columnCount(),
            "full_research_scores":page.report["full_model_count"],
            "inod_S14_coverage":page.comparison.item(0,6).text(),
            "inod_B_Q_component_coverage":page.comparison.item(0,7).text(),
            "inod_S6_partial_coverage":page.comparison.item(0,8).text(),
            "inod_sec_partial_ratios":page.report["stocks"][0]["sec_companyfacts_partial"]["available_ratio_count"],
            "inod_sec_filing_bodies":forensic['body_filing_count'] if forensic else None,
            "S13_review_status":forensic['status'] if forensic else None,
            "SEC_8K_event_candidates":candidate['count'] if candidate else None,
            "verified_S16_EA_alerts":candidate['verified_early_alerts'] if candidate else None,
            "INOD_S11_target_financials":jones['target_exact_accounting_fields'] if jones else None,
            "INOD_S11_dated_peers":jones['eligible_industry_year_peers'] if jones else None,
            "canonical_securities":page.report["canonical_securities"],
            "personal_installer_touched":False,"database_mutated":False}))
    finally:
        page.close()
        app.processEvents()


if __name__=="__main__":
    main()
