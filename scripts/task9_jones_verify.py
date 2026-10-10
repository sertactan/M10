"""Strict offline replay of original SIC/SEC peer cohort and Jones score."""
import argparse
import json
from pathlib import Path
from app.task9_jones_acceptance import verify_jones_task9_receipt

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--receipt',required=True,type=Path)
    p.add_argument('--cache',required=True,type=Path)
    a=p.parse_args()
    result=verify_jones_task9_receipt(a.receipt,cache=a.cache)
    print(json.dumps({k:result[k] for k in ('score','score_status','eligible_peer_count',
                         'discretionary_accrual','source_file_sha256','independent_confirmed')}))
