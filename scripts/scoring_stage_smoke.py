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
        if page.comparison.rowCount()!=5 or page.comparison.columnCount()!=14:
            raise ValueError("V2 Windows staging comparison shape invalid")
        if page.report.get("full_model_count") not in (9,10):
            raise ValueError("Unexpected promoted research score count")
        if not all(page.comparison.item(i, j).text()=="N/A"
                   for i in range(5) for j in (6,10,11)):
            raise ValueError("S14/S16-E/S16-C are incorrectly promoted")
        if page.comparison.item(0,7).text()!=("3/6" if page.report['full_model_count']==10 else "2/6"):
            raise ValueError("INOD S14 coverage incorrectly promoted")
        if (page.comparison.item(0,8).text() not in ('4/7','5/7') or
            page.comparison.item(0,9).text() not in ('4/7','5/7')):
            raise ValueError('V3 new SEC financial feature coverage not exposed')
        task9=page.report['stocks'][0].get('task9_financial_evidence')
        if task9 and (page.comparison.item(0,9).text()!='5/7'
                      or task9['S6_ISSUE']!=1 or task9['S6_score'] is not None
                      or task9['B_Q'] is not None or task9['S14'] is not None):
            raise ValueError('Task9 verified issuance or full score gating invalid')
        if task9 and any(v.get('LVGI') is not None for v in
                         task9['long_term_obligations'].values()):
            raise ValueError('Pension/software license obligations promoted to interest-bearing debt')
        context=page.report['stocks'][0].get('task9_forensic_context')
        if context and (context['context_block_count']!=7
                        or context['source_findings_count']!=27
                        or context['reviewed_numeric_risk_block_count']!=0
                        or context['S13'] is not None):
            raise ValueError('Source-contextual S13 review improperly scored')
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
        if jones and jones['target_exact_accounting_fields']!=8:
            raise ValueError('Invalid SEC Jones target/peer audit promotion')
        scored_jones=page.report['stocks'][0].get('task9_jones_research')
        if scored_jones and (scored_jones['score']!=0.0
                            or scored_jones['eligible_peer_count']!=20
                            or not scored_jones['independent_confirmed']
                            or page.report['full_model_count']!=10
                            or page.comparison.item(0,5).text()!='0.00'):
            raise ValueError('Real S11 independent SEC OLS acceptance invalid')
        page.comparison.selectRow(0)
        page.select_stock()
        if scored_jones:
            found=[i for i in range(page.models.rowCount()) if
                   page.models.item(i,0).text()=='S11']
            if (len(found)!=1 or page.models.item(found[0],1).text()!='0.00'
                or page.models.item(found[0],2).text()!='REAL_SCORE_ACCEPTED_RESEARCH'):
                raise ValueError('A genuine zero S11 score rendered as N/A or lost provenance')
        if ("sec_companyfacts_partial" not in page.details.toPlainText()
                or not page.details.isReadOnly()):
            raise ValueError("SEC partial evidence not visible in read-only detail")
        print(json.dumps({"result":"PASS","mode":os.environ.get("QT_QPA_PLATFORM"),
            "stocks":page.comparison.rowCount(),"columns":page.comparison.columnCount(),
            "full_research_scores":page.report["full_model_count"],
            "inod_S14_coverage":page.comparison.item(0,7).text(),
            "inod_B_Q_component_coverage":page.comparison.item(0,8).text(),
            "inod_S6_partial_coverage":page.comparison.item(0,9).text(),
            "task9_INOD_ISSUE":task9['S6_ISSUE'] if task9 else None,
            "task9_S13_context_findings":context['source_findings_count'] if context else None,
            "inod_sec_partial_ratios":page.report["stocks"][0]["sec_companyfacts_partial"]["available_ratio_count"],
            "inod_sec_filing_bodies":forensic['body_filing_count'] if forensic else None,
            "S13_review_status":forensic['status'] if forensic else None,
            "SEC_8K_event_candidates":candidate['count'] if candidate else None,
            "verified_S16_EA_alerts":candidate['verified_early_alerts'] if candidate else None,
            "INOD_S11_target_financials":jones['target_exact_accounting_fields'] if jones else None,
            "INOD_S11_dated_peers":jones['eligible_industry_year_peers'] if jones else None,
            "task9_accepted_S11":scored_jones['score'] if scored_jones else None,
            "task9_S11_peers":scored_jones['eligible_peer_count'] if scored_jones else None,
            "canonical_securities":page.report["canonical_securities"],
            "personal_installer_touched":False,"database_mutated":False}))
    finally:
        page.close()
        app.processEvents()


if __name__=="__main__":
    main()
