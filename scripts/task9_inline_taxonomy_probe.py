"""Offline FY2024/25 inline-XBRL extension concept inventory, without imputation."""
from __future__ import annotations
import argparse
from collections import Counter
from pathlib import Path
import json
import re

TAG=re.compile(rb'<ix:(?:nonfraction|nonnumeric)\b([^>]*)>',re.I|re.S)
ATTR=re.compile(rb'\bname\s*=\s*["\']([^"\']+)',re.I)
DETAIL_TAGS=('CurrentPortionOfLongTermObligations',
             'NoncurrentPortionOfLongTermObligations',
             'TotalLongTermObligations','MicrosoftLicensesObligations')
FOCUS=('deprecia','amortiz','inventory','inventories','debt','borrow',
       'creditfacility','longtermoblig','interestbearing','optionexercis',
       'stockoption','financialasset','financialliab','operatingasset')

def scan(raw:bytes):
    namespaces=Counter();focus=Counter();extensions=Counter();matched=[]
    for match in TAG.finditer(raw):
        attr=ATTR.search(match.group(1))
        if not attr: continue
        name=attr.group(1).decode('utf8','replace')
        if ':' not in name: continue
        ns, local=name.split(':',1)
        namespaces[ns]+=1
        if ns not in {'us-gaap','dei','srt','ecd','invest','ffd'}:
            extensions[name]+=1
        if any(term in local.lower() for term in FOCUS):
            focus[name]+=1
        if any(term.lower()==local.lower() for term in DETAIL_TAGS):
            fields={}
            for field in ('contextref','scale','unitref','decimals','sign'):
                m=re.search(rb'\b'+field.encode()+rb'\s*=\s*["\']([^"\']+)',match.group(1),re.I)
                if m: fields[field]=m.group(1).decode('utf8','replace')
            following=raw[match.end():match.end()+300]
            cutoff=re.search(rb'</ix:nonfraction\s*>',following,re.I)
            rendered=re.sub(rb'<[^>]+>',b'',following[:cutoff.start()] if cutoff else following[:80])
            matched.append({'tag':name,'attributes':fields,'raw_display':rendered.decode('utf8','replace').strip()})
    return {'namespaces':dict(sorted(namespaces.items())),
            'focused_names':dict(sorted(focus.items())),
            'private_extension_names':dict(sorted(extensions.items())),
            'inline_tag_count':sum(namespaces.values()),
            'longterm_obligation_extension_facts':matched}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--filing-cache',type=Path,required=True)
    p.add_argument('--only-obligations',action='store_true')
    args=p.parse_args()
    names={2024:'000141057825000194_inod-20241231x10k.htm',
           2025:'000110465926020655_inod-20251231x10k.htm'}
    results={y:scan((args.filing_cache/name).read_bytes()) for y,name in names.items()}
    if args.only_obligations:
        results={y:r['longterm_obligation_extension_facts'] for y,r in results.items()}
    print(json.dumps(results,ensure_ascii=False,indent=2))
