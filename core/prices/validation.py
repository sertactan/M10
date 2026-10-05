from __future__ import annotations

from statistics import median

from core.prices.models import SourcePriceBar


def compare_adjusted_close(a: list[SourcePriceBar], b: list[SourcePriceBar]) -> dict:
    amap = {x.trade_date: x.adjusted_close for x in a}
    bmap = {x.trade_date: x.adjusted_close for x in b}
    overlap = sorted(amap.keys() & bmap.keys())
    diffs=[]
    for d in overlap:
        av=amap[d]; bv=bmap[d]
        if av == 0 or bv == 0:
            continue
        base=(abs(av)+abs(bv))/2.0
        diffs.append(abs(av-bv)/base*100.0)
    if not diffs:
        return {"overlap_rows":0,"median_abs_pct_diff":None,"max_abs_pct_diff":None,"status":"NO_OVERLAP"}
    med=median(diffs); mx=max(diffs)
    status="OK" if med <= 0.5 and mx <= 5.0 else ("WARN" if med <= 2.0 else "SUSPECT")
    return {"overlap_rows":len(diffs),"median_abs_pct_diff":med,"max_abs_pct_diff":mx,"status":status}
