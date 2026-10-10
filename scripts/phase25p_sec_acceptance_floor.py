"""Phase25P: read-only issuer SEC filing timestamp acceptance research evidence."""
from __future__ import annotations
import argparse,json,os
from pathlib import Path
from core.research.sec_publication_gate import OBSERVED_ACCEPTANCES

def main():
    root=Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))/"S153ResearchTerminal/runtime"
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,default=root/"phase25p/sec_acceptance_not_public_dissemination.json")
    args=p.parse_args()
    if args.out.is_symlink():
        print("PHASE25P_BLOCKED: OUTPUT_SYMLINK")
        return 2
    rows=[{
      "ticker":f.ticker,"cik":f.cik,"accession":f.accession,
      "form":f.form,"period_end":f.reported_period_end,
      "SEC_index_accepted_at_ET":f.sec_index_accepted_et,
      "SEC_index_accepted_at_UTC":f.sec_accepted_at_utc.isoformat(),
      "original_SEC_index_url":f.sec_index_url,
      "public_dissemination_time_independently_verified":False,
      "SEC_feature_available_at_independently_verified":False,
      "feature_usable_for_historical_training":False,
    } for f in OBSERVED_ACCEPTANCES]
    result={
       "schema":"MERIDYEN_PHASE25P_SEC_ACCEPTED_NOT_PUBLIC_AVAILABILITY_V1",
       "status":"THREE_SEC_INDEX_ACCEPTANCES_DOCUMENTED_NO_HISTORIC_FEATURE_PIT_CERTIFICATION",
       "observed_official_SEC_index_acceptance_stamps":len(rows),
       "historical_public_dissemination_stamps_independently_verified":0,
       "model_signal_eligible_records":0,
       "records":rows,"operational_DB_modified":False,"models_modified":False,
       "WF9_executed":False,"Learning_V3_executed":False,
    }
    try:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        tmp=args.out.with_name(args.out.name+".tmp")
        if tmp.is_symlink():raise ValueError("TEMP_SYMLINK")
        tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        tmp.replace(args.out)
    except (ValueError,OSError):
        print("PHASE25P_BLOCKED: UNABLE_TO_SAVE_LOCAL_RESEARCH")
        return 2
    print(json.dumps({"status":result["status"],"sec_filings":len(rows),
                      "PIT_certified":0,"out":str(args.out)},ensure_ascii=False))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
