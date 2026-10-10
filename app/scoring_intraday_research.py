"""Research-only minute-bar parsing; no alert or historical PIT promotion."""
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
import math

def parse_minutes(payload, ticker, retrieved):
    result=payload['chart']['result'][0]
    if result['meta']['symbol'].upper()!=ticker.upper():raise ValueError('Ticker mismatch')
    if result['meta'].get('dataGranularity')!='1m':raise ValueError('Not minute bars')
    stamps=result['timestamp'];q=result['indicators']['quote'][0]
    if any(len(q[k])!=len(stamps) for k in ('open','high','low','close','volume')):raise ValueError('Unequal arrays')
    rows=[];skipped=0;zone=ZoneInfo('America/New_York')
    for i,t in enumerate(stamps):
        at=datetime.fromtimestamp(t,timezone.utc)
        values=[q[k][i] for k in ('open','high','low','close','volume')]
        if at.second or at+timedelta(minutes=1)>retrieved or any(v is None for v in values):skipped+=1;continue
        o,h,l,c,v=map(float,values)
        if not all(math.isfinite(x) for x in (o,h,l,c,v)) or min(o,h,l,c)<=0 or v<0 or l>min(o,c) or h<max(o,c):raise ValueError('Invalid OHLCV')
        local=at.astimezone(zone);minute=local.hour*60+local.minute
        session='PREMARKET_CLOCK' if 240<=minute<570 else 'REGULAR_CLOCK' if 570<=minute<960 else 'OTHER_CLOCK'
        rows.append(dict(timestamp=at.isoformat(),exchange_time=local.isoformat(),o=o,h=h,l=l,c=c,volume=v,session=session))
    if len({r['timestamp'] for r in rows})!=len(rows):raise ValueError('Duplicate minute')
    return sorted(rows,key=lambda r:r['timestamp']),skipped

def five_minute(rows):
    groups={}
    for r in rows:
        t=datetime.fromisoformat(r['timestamp']);key=t.replace(minute=t.minute//5*5,second=0,microsecond=0)
        groups.setdefault(key,[]).append(r)
    result=[]
    for start,group in sorted(groups.items()):
        group.sort(key=lambda r:r['timestamp'])
        if len(group)!=5 or any(datetime.fromisoformat(r['timestamp'])!=start+timedelta(minutes=i) for i,r in enumerate(group)):continue
        result.append(dict(timestamp=start.isoformat(),o=group[0]['o'],h=max(r['h'] for r in group),l=min(r['l'] for r in group),c=group[-1]['c'],volume=sum(r['volume'] for r in group),source='DERIVED_FROM_FIVE_COMPLETE_1M_BARS'))
    return result
