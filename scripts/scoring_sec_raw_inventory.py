"""Inspect private cached official SEC Companyfacts tags without leaking raw data.

The `units` arrays can hold different SEC accessions/periods; this is only
inventory and never a financial-concept alias or an accepted model input.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


KEYWORDS = ("receiv", "costof", "grossprofit", "costofrevenue", "inventory", "inventories",
            "propertyplant", "depreci", "amort", "revenue", "sellinggeneral",
            "longtermdebt", "shorttermborrow", "debttotal", "debta", "cashand",
            "assetscurrent", "assets", "liabilities", "netincome", "operatingactivities",
            "relatedparty")


def inventory(path, accession, fiscal_years):
    payload = json.loads(Path(path).read_bytes())
    result = []
    for taxonomy, taxonomy_tags in payload.get("facts", {}).items():
        for tag, obj in taxonomy_tags.items():
            if not any(word in tag.lower() for word in KEYWORDS):
                continue
            samples = []
            for unit, rows in obj.get("units", {}).items():
                records = [r for r in rows if r.get("accn") == accession
                           and any(str(r.get("end", "")).startswith(str(y)) for y in fiscal_years)]
                for r in sorted(records, key=lambda x:(x.get("end", ""),x.get("start","")),reverse=True)[:5]:
                    samples.append({k: r.get(k) for k in
                                    ("start", "end", "fy", "fp", "form", "filed", "frame")}
                                   | {"unit": unit})
            if samples:
                result.append({"taxonomy": taxonomy, "tag": tag,
                               "label": obj.get("label"), "examples": samples[:5]})
    return sorted(result, key=lambda x:(x["taxonomy"],x["tag"]))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--file", required=True, type=Path)
    p.add_argument("--accession", default="0001104659-26-020655")
    p.add_argument("--years", nargs="+", type=int, default=[2024, 2025])
    p.add_argument("--compact", action="store_true")
    args = p.parse_args()
    rows=inventory(args.file,args.accession,args.years)
    if args.compact:
        print(json.dumps({"matching_tag_count": len(rows), "tags": [
            {"tag": r["tag"], "taxonomy": r["taxonomy"], "periods": [
                f"{e.get('start','INSTANT')}:{e['end']}" for e in r["examples"][:2]]}
            for r in rows]}, ensure_ascii=False))
    else:
        print(json.dumps({"matching_tag_count": len(rows), "tags": rows},indent=2))
