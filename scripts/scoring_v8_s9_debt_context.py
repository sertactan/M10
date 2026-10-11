"""Inspect audited 10-K debt contexts without treating narrative text as a score."""
from __future__ import annotations
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import json
import os
import re

class Plain(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pieces=[]
    def handle_data(self, data):
        if data.strip(): self.pieces.append(data)

def audit(path):
    data=path.read_bytes()
    parsed=Plain()
    parsed.feed(data.decode('utf8',errors='replace'))
    text=' '.join(' '.join(parsed.pieces).split())
    queries=(r'long.term debt', r'borrowings outstanding', r'outstanding borrowings',
             r'convertible notes?',r'credit facilit(?:y|ies)',r'loan agreement',
             r'non.current liabilities',r'long.term obligations')
    passages=[]
    for query in queries:
        matches=list(re.finditer(query,text,re.I))
        for m in matches[:8]:
            passages.append({'phrase':query,'text':text[max(0,m.start()-260):m.end()+320]})
    return {'source_sha256':hashlib.sha256(data).hexdigest(),
            'count_contexts':len(passages),'passages':passages}

def main():
    rt=Path(os.environ['LOCALAPPDATA'])/'S153ResearchTerminal'/'runtime'
    inod=rt/'scoring_completion'/'v3_filing_bodies'/'000110465926020655_inod-20251231x10k.htm'
    private=Path('E:/M10/.scoring_v8_private/task9_jones_v8_piotroski/responses')
    url='https://www.sec.gov/Archives/edgar/data/1410098/000121390026023889/ea0278169-10k_cormedix.htm'
    crmd=private/(hashlib.sha256(url.encode()).hexdigest()+'.bin')
    out={name:audit(src) for name,src in (('INOD',inod),('CRMD',crmd)) if src.is_file()}
    print(json.dumps(out,indent=2))

if __name__=='__main__': main()
