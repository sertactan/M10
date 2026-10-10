"""Independent Decimal reference arithmetic for recovered S7/S12 private reports."""
from decimal import Decimal as D
import argparse,json,hashlib
from pathlib import Path

def interpolate(x,points):
    x=D(str(x));points=[(D(str(a)),D(str(b))) for a,b in points]
    if x<=points[0][0]:return points[0][1]
    if x>=points[-1][0]:return points[-1][1]
    for (a,b),(c,d) in zip(points,points[1:]):
        if a<=x<=c:return b+(d-b)*(x-a)/(c-a)
    raise ValueError('No segment')

def verify(report):
    checks=[]
    for stock in report['stocks']:
        for name in ('S7','S12'):
            q=stock['quality'][name]
            if q['score'] is None:continue
            refs=q['evidence']['inputs'];v={x['metric']:D(str(x['value'])) for x in refs}
            if name=='S7':
                assets=[D(str(x['value'])) for x in refs if x['metric'] in ('ASSETS','TOTAL_ASSETS')]
                if len(assets)!=2:raise ValueError('Two asset dates required')
                x=(v['NET_INCOME']-v['OPERATING_CASH_FLOW'])/(sum(assets)/2)
                expected=interpolate(x,[(0,100),('.05',75),('.10',50),('.15',25),('.20',0)])
            else:
                cfo,ni,rev,cap=[v[x] for x in ('OPERATING_CASH_FLOW','NET_INCOME','REVENUE','CAPEX')];fcf=cfo-abs(cap)
                expected=(D('.35')*interpolate(cfo/ni,[(0,0),('.5',40),('.8',70),(1,90),('1.2',100)])
                    +D('.30')*interpolate(fcf/ni,[(0,0),('.4',35),('.7',65),(1,90),('1.2',100)])
                    +D('.20')*interpolate(cfo/rev,[(0,0),('.05',40),('.10',60),('.20',85),('.30',100)])
                    +D('.15')*interpolate(fcf/rev,[(0,0),('.05',45),('.10',65),('.15',80),('.25',100)]))
            difference=abs(float(expected)-q['score'])
            if difference>1e-10:raise ValueError('Reference mismatch: '+stock['ticker']+' '+name)
            checks.append({'ticker':stock['ticker'],'model':name,'reference':float(expected),'difference':difference})
    return {'status':'PASS','score_count':len(checks),'checks':checks,'tolerance':1e-10}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
    data=a.report.read_bytes();result=verify(json.loads(data));result['report_sha256']=hashlib.sha256(data).hexdigest()
    with a.receipt.open('x',encoding='utf8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))
