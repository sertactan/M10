"""Run official SEC INOD XBRL partial forensic audit, private output only."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from app.sec_companyfacts_quality import extract_exact_companyfacts, partial_beneish_diagnostics


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--companyfacts", required=True, type=Path)
    p.add_argument("--submissions", required=True, type=Path)
    p.add_argument("--companyfacts-sha256", required=True)
    p.add_argument("--output", required=True, type=Path)
    args=p.parse_args()
    dest=args.output
    if ("scoring_completion" not in {part.lower() for part in dest.resolve().parts}
            or dest.is_symlink() or dest.exists() or dest.name != "quality_partial.json"):
        raise ValueError("Only new private scoring_completion output is allowed")
    raw=args.companyfacts.read_bytes()
    if sha256(raw).hexdigest()!=args.companyfacts_sha256:
        raise ValueError("Official raw SEC Companyfacts hash changed")
    submission=json.loads(args.submissions.read_bytes())
    accession="0001104659-26-020655"
    recent=submission["filings"]["recent"]
    indices=[i for i, acc in enumerate(recent["accessionNumber"]) if acc==accession]
    if len(indices)!=1:
        raise ValueError("2026 INOD 10-K acceptance missing or ambiguous")
    index=indices[0]
    if recent["form"][index]!="10-K":
        raise ValueError("10-K form mismatch")
    source=extract_exact_companyfacts(raw,ticker="INOD",cik="0000903651",
            accession=accession, retrieved_at="2026-10-10T17:53:29.445570+00:00",
            fiscal_years=(2024,2025))
    # SEC administrative acceptance and provider retrieval remain distinct.
    accepted=recent["acceptanceDateTime"][index]
    for row in source["rows"]:
        if row["filing_date"]!=recent["filingDate"][index]:
            raise ValueError("SEC filing date mismatch")
        row["accepted_at"]=accepted
    source["sec_submissions_sha256"]=sha256(args.submissions.read_bytes()).hexdigest()
    source["accepted_at"]=accepted
    source["partial_beneish_2025"]=partial_beneish_diagnostics(source["rows"],2025)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open("x",encoding="utf-8") as f:
        json.dump(source,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({"status":"SEC_EXACT_TAG_PARTIAL_RESEARCH_ONLY",
        "rows":len(source["rows"]),"missing":source["missing"],
        "partial_ratios":source["partial_beneish_2025"]["ratios"],
        "source_sha256":source["source_sha256"],
        "output_sha256":sha256(dest.read_bytes()).hexdigest(),
        "S14":None,"B_Q":None,"canonical_accepted":False}))


if __name__=="__main__":
    main()
