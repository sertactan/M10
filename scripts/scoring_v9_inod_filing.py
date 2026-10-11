"""Offline, source-hashed targeted extracts of INOD FY2025/24 audited debt notes."""
from __future__ import annotations
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import json, os, re

PINS={
 2025:"2d5dd7f964d0239ea18a982f24e077d1b8e0f08baa73fd28dd66f539d9befba2",
}
FILES={2025:"000110465926020655_inod-20251231x10k.htm",
       2024:"000141057825000194_inod-20241231x10k.htm"}
TERMS=(r"Note 16",r"Line of Credit",r"no borrowings",r"no amounts outstanding",
       r"no outstanding borrowings",r"borrowing base",r"Revolving Credit Facility",
       r"Long-term obligations",r"Long-term debt",r"interest bearing",
       r"interest-bearing",r"leases",r"Microsoft licenses",r"pension obligations")
class Text(HTMLParser):
 def __init__(self): super().__init__(convert_charrefs=True); self.pieces=[]
 def handle_data(self,data):
  if data.strip(): self.pieces.append(data)
def read(path:Path,year:int):
 raw=path.read_bytes(); digest=sha256(raw).hexdigest()
 if year in PINS and digest!=PINS[year]: raise ValueError("PINNED_SEC_10K_BODY_CHANGED")
 parser=Text();parser.feed(raw.decode("utf8",errors="replace"))
 text=" ".join(" ".join(parser.pieces).split());sections=[]
 for term in TERMS:
  matches=list(re.finditer(term,text,re.I))
  sections.append({"term":term,"matches":len(matches),"contexts":[text[max(0,m.start()-450):m.end()+1000] for m in matches[:18]]})
 return {"year":year,"body_sha256":digest,"bytes":len(raw),"sections":sections}
def main():
 root=Path(os.environ["LOCALAPPDATA"])/"S153ResearchTerminal"/"runtime"/"scoring_completion"/"v3_filing_bodies"
 print(json.dumps({str(yr):read(root/name,yr) for yr,name in FILES.items()},indent=2,ensure_ascii=False))
if __name__=="__main__":
 import sys
 sys.stdout.reconfigure(encoding="utf-8", errors="replace")
 main()
