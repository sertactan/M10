"""Verify original offline SEC filings and seal INOD S9 FY2025 Research result."""
from __future__ import annotations
import argparse, os, sys, json, zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.scoring_v9_inod import write_or_verify

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt',type=Path,
        default=Path('E:/M10/.scoring_v9_private/inod_s9/report.json'))
    args=parser.parse_args()
    root=Path('E:/M10/.scoring_v9_private').resolve()
    if args.receipt.resolve().parent!=root/'inod_s9':
        raise ValueError('NEW_PRIVATE_V9_RECEIPT_DIRECTORY_REQUIRED')
    rt=Path(os.environ['LOCALAPPDATA'])/'S153ResearchTerminal'/'runtime'
    with zipfile.ZipFile(rt/'bulk/sec/companyfacts.zip') as z:
        facts=z.read('CIK0000903651.json')
    subs=(rt/'sec_submissions/CIK0000903651.json').read_bytes()
    dir=rt/'scoring_completion/v3_filing_bodies'
    fy2025=(dir/'000110465926020655_inod-20251231x10k.htm').read_bytes()
    fy2024=(dir/'000141057825000194_inod-20241231x10k.htm').read_bytes()
    result=write_or_verify(args.receipt,(facts,subs,fy2025,fy2024))
    print(json.dumps({'ticker':'INOD','S9':result['score'],'signals':result['signals'],
        'status':result['score_status'],'research_only':True,'decimal':result['score_decimal'],
        'receipt':str(args.receipt)},sort_keys=True))
if __name__=='__main__': main()
