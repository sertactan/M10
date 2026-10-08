#!/usr/bin/env python3
"""Meridyen Social V5 FREE: read-only keyless public-source and offline audit tools.

No broker calls, paid API, streaming services or canonical S-model calculations.
Python 3.10+ stdlib. Example datasets are synthetic and not trading signals.
"""
import argparse
import csv
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode, urlparse, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler

UTC = dt.timezone.utc
SCHEMA = ('platform','source_id','created_at','observed_at','ticker','text','author_hash',
          'engagement','sentiment','source_url','capture_proof')
PLATFORMS = {'reddit','x','stocktwits','tradingview','bluesky','mastodon','discord','telegram','yahoo','other'}
SYMBOL_RE = re.compile(r'\$([A-Z][A-Z0-9.-]{0,5})(?![A-Z0-9.-])')
VALID_TICKER = re.compile(r'[A-Z][A-Z0-9.-]{0,5}\Z')
ALLOWED_MASTODON = {'mastodon.social', 'fosstodon.org', 'mstdn.social', 'hachyderm.io'}
LIMIT_BYTES = 2_000_000


def stamp(s):
    if not s or not isinstance(s,str): raise ValueError('timestamp missing')
    v = dt.datetime.fromisoformat(s.strip().replace('Z','+00:00'))
    if v.tzinfo is None: raise ValueError('timestamp must include UTC offset')
    return v.astimezone(UTC)


def iso(v): return v.astimezone(UTC).isoformat().replace('+00:00','Z')


def sha(s): return hashlib.sha256(s.encode('utf-8')).hexdigest()


def fingerprint(text):
    # Exact-ish duplicates, NOT an ML bot detection. Avoid removing cashtags.
    v = re.sub(r'https?://\S+', '',text.casefold())
    return sha(' '.join(re.findall(r'[\w$.-]+',v)))


def valid_symbol(s):
    t=str(s).upper().strip()
    if not VALID_TICKER.fullmatch(t): raise ValueError('invalid ticker')
    return t


def verified_event(row):
    r=dict(row)
    platform=str(r.get('platform','')).strip().lower()
    if platform not in PLATFORMS: raise ValueError('unsupported platform')
    ident=str(r.get('source_id','')).strip()
    if not ident or len(ident)>350: raise ValueError('source_id missing/too long')
    created,observed=stamp(r.get('created_at')),stamp(r.get('observed_at'))
    if observed < created: raise ValueError('observed_at before created_at')
    text=str(r.get('text',''))
    if len(text)>6000: raise ValueError('post text too large')
    ticker=valid_symbol(r.get('ticker',''))
    cashtags=set(SYMBOL_RE.findall(text.upper()))
    if ticker not in cashtags: raise ValueError('ticker must appear as exact $CASHTAG in text')
    url=str(r.get('source_url','')).strip()
    parsed=urlparse(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('source_url must be ordinary HTTPS URL')
    engagement=float(r.get('engagement',0) or 0)
    if not math.isfinite(engagement) or engagement<0: raise ValueError('invalid engagement')
    raw_sent=r.get('sentiment')
    sentiment=None if raw_sent in ('',None) else float(raw_sent)
    if sentiment is not None and (not math.isfinite(sentiment) or not -1<=sentiment<=1):
        raise ValueError('sentiment must be -1..1 or missing')
    author=str(r.get('author_hash','')).strip()
    # Anonymous/absent authors are NOT independent authors.
    if author and (len(author)>128 or not re.fullmatch(r'[a-f0-9]{12,128}',author)):
        raise ValueError('author_hash must be pseudonymous hex digest (12..128 chars)')
    proof=str(r.get('capture_proof','user_supplied_unverified')).strip()
    if proof not in {'public_network_capture','user_supplied_unverified'}:
        raise ValueError('invalid capture_proof')
    return {'platform':platform,'source_id':ident,'created_at':iso(created),'observed_at':iso(observed),
            'ticker':ticker,'text':text,'text_hash':fingerprint(text),'author_hash':author,
            'engagement':engagement,'sentiment':sentiment,'source_url':url,'capture_proof':proof}


def load_events(path):
    p=Path(path)
    if p.stat().st_size>20_000_000: raise ValueError('input too large')
    with p.open(encoding='utf-8-sig',newline='') as f:
        if p.suffix.lower()=='.jsonl':
            rows=(json.loads(line) for line in f if line.strip())
        else: rows=csv.DictReader(f)
        # fail closed: don't quietly throw away malformed events
        seen=set(); out=[]
        for row in rows:
            event=verified_event(row)
            key=(event['platform'],event['source_id'],event['ticker'])
            if key in seen: continue
            seen.add(key);out.append(event)
    return out


def write_events(path,rows):
    out=Path(path);out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists(): raise FileExistsError('output exists; refusing overwrite')
    columns=(*SCHEMA,'text_hash')
    with out.open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,columns,extrasaction='ignore');w.writeheader()
        for row in rows:w.writerow(verified_event(row))


def status():
    return {'module':'MERIDYEN_SOCIAL_V5_FREE', 'mode':'NONCANONICAL_RESEARCH',
            'paid_api_budget_usd':0,'api_keys_required':False,
            'host_live_stream_connected':False,'scheduler_connected':False,
            'm10_database_connected':False,'broker_connected':False,
            'public_optional':['bluesky_search','mastodon_public_hashtag_instance_dependent'],
            'offline_import':sorted(PLATFORMS),
            'restricted':['no X paid API','no Stocktwits scraping','no TradingView scraping',
                          'no unauthorized Discord/Telegram access'],
            'source_status':'not checked until an explicit local fetch is run',
            's15_s16':'READ_ONLY_UNCHANGED'}


def analyze(events,ticker,as_of,current_hours=24,baseline_hours=72):
    if current_hours<=0 or baseline_hours<=0: raise ValueError('windows must be positive')
    t=valid_symbol(ticker);now=stamp(as_of)
    recent=now-dt.timedelta(hours=current_hours)
    start=recent-dt.timedelta(hours=baseline_hours)
    # Cannot count historical posts as alerts before they were actually observed.
    eligible=[r for r in events if r['ticker']==t and stamp(r['observed_at'])<=now and
              stamp(r['created_at'])<=now and stamp(r['observed_at'])>=start]
    cur=[r for r in eligible if stamp(r['observed_at'])>=recent]
    base=[r for r in eligible if start<=stamp(r['observed_at'])<recent]
    platforms=sorted({r['platform'] for r in cur})
    authors={r['author_hash'] for r in cur if r['author_hash']}
    hashes={r['text_hash'] for r in cur}
    dup=max(0,len(cur)-len(hashes))
    velocity_cur=len(cur)/current_hours
    velocity_base=len(base)/baseline_hours
    ratio=(velocity_cur/velocity_base) if len(base)>0 else None
    independent=len(platforms)>=2 and len(authors)>=3 and len(hashes)>=3
    suspicious=bool(cur) and (dup/len(cur)>.50 or (len(cur)>=5 and len(authors)<=1))
    annotated=[r['sentiment'] for r in cur if r['sentiment'] is not None]
    # A sample-specific diagnostic, NOT an S16 or financial signal.
    alert='INSUFFICIENT_EVIDENCE'
    if not base:alert='BASELINE_MISSING'
    elif len(cur)>=5 and ratio is not None and ratio>=2 and independent and not suspicious:
        alert='RESEARCH_WATCH_NONCANONICAL'
    elif suspicious:alert='COORDINATION_HEURISTIC_REVIEW'
    elif not independent:alert='INDEPENDENT_CORROBORATION_MISSING'
    return {'module':'MERIDYEN_SOCIAL_V5_FREE','ticker':t,'as_of':iso(now),
            'coverage':{'current_hours':current_hours,'baseline_hours':baseline_hours,
                        'current_posts':len(cur),'baseline_posts':len(base),'platforms':platforms,
                        'independent_author_hashes':len(authors),'distinct_texts':len(hashes),
                        'duplicate_like_posts':dup,
                        'captures_verified':sum(r['capture_proof']=='public_network_capture' for r in cur),
                        'user_supplied_unverified':sum(r['capture_proof']!='public_network_capture' for r in cur)},
            'mentions_per_hour':round(velocity_cur,5),
            'prior_mentions_per_hour':round(velocity_base,5),
            'velocity_ratio':round(ratio,5) if ratio is not None else None,
            'annotated_sentiment_mean':round(sum(annotated)/len(annotated),4) if annotated else None,
            'sentiment_annotation_count':len(annotated),
            'duplicate_rate':round(dup/len(cur),4) if cur else None,
            'coordination_heuristic':suspicious,'cross_platform_independence_proxy':independent,
            'state':alert,'is_trade_signal':False,'s16_e_status':'UNCHANGED_UNCOMPUTED',
            's16_c_status':'UNCHANGED_UNCOMPUTED',
            'limitations':['Uneven access across platforms makes mention counts nonrepresentative',
                           'Source timestamps/author pseudonyms in manual exports are unverified',
                           'No price, volume, SEC or options confirmation is computed here']}


def evaluate(path,as_of,split_date):
    now=stamp(as_of);split=stamp(split_date)
    if split>=now:raise ValueError('split must be before as_of')
    with open(path,encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    train=[];test=[];excluded=Counter()
    for row in rows:
        signal=stamp(row.get('signal_time'))
        seen=stamp(row.get('signal_observed_at'))
        matured=stamp(row.get('outcome_available_at'))
        if seen>signal:excluded['not_observed_as_of_signal']+=1;continue
        if matured<=signal:excluded['outcome_not_after_signal']+=1;continue
        if matured>now:excluded['not_matured']+=1;continue
        # Train outcomes must be available by time model would enter test window.
        if signal<split:
            if matured>split:excluded['train_label_leakage']+=1;continue
            group=train
        else:group=test
        if row.get('prediction') not in ('0','1') or row.get('label') not in ('0','1'):
            raise ValueError('binary prediction and label required')
        if not row.get('source_ref'):raise ValueError('source_ref mandatory')
        group.append((int(row['prediction']),int(row['label'])))
    def metric(items):
        tp=sum(p==1 and y==1 for p,y in items)
        fp=sum(p==1 and y==0 for p,y in items)
        tn=sum(p==0 and y==0 for p,y in items)
        fn=sum(p==0 and y==1 for p,y in items)
        def div(a,b):return round(a/b,5) if b else None
        return {'n':len(items),'tp':tp,'fp':fp,'tn':tn,'fn':fn,
                'precision':div(tp,tp+fp),'recall':div(tp,tp+fn),
                'false_positive_rate':div(fp,fp+tn)}
    return {'module':'MERIDYEN_SOCIAL_V5_FREE','type':'OFFLINE_HISTORICAL_OOS_AUDIT',
            'split_date':iso(split),'as_of':iso(now),'train':metric(train),'test':metric(test),
            'excluded':dict(excluded),'model_trained':False,
            'p_it_status':'USER_SUPPLIED_TIMESTAMPS_NOT_EXTERNALLY_VERIFIED',
            'canonical_s_series':'UNCHANGED','causal_claim':False}


class _Stripper(HTMLParser):
    def __init__(self):super().__init__();self.out=[]
    def handle_data(self,data):self.out.append(data)
    def result(self):return ' '.join(html.unescape(' '.join(self.out)).split())


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('redirect blocked')


def public_get(url):
    host=urlparse(url).hostname
    if host not in {'public.api.bsky.app',*ALLOWED_MASTODON} or not url.startswith('https://'):
        raise ValueError('disallowed public endpoint')
    req=Request(url,headers={'User-Agent':'MeridyenSocialV5Free/0.26.0 (+research; no automation)',
                             'Accept':'application/json'})
    with build_opener(_NoRedirect()).open(req,timeout=8) as res:
        if res.status!=200:raise RuntimeError(f'HTTP status {res.status}')
        raw=res.read(LIMIT_BYTES+1)
        if len(raw)>LIMIT_BYTES:raise ValueError('public response too large')
        return json.loads(raw.decode('utf-8'))


def _public_row(platform,source_id,created,observed,text,author,url,engagement):
    # Hash author to minimize stored profile identifiers; original post URL remains traceable.
    return {'platform':platform,'source_id':source_id,'created_at':created,'observed_at':observed,
            'ticker':'', 'text':text,'author_hash':sha(platform+'|'+str(author))[:24] if author else '',
            'engagement':engagement,'sentiment':'','source_url':url,'capture_proof':'public_network_capture'}


def collect_bluesky(ticker,limit=30,fetch=public_get):
    ticker=valid_symbol(ticker)
    if not 1<=limit<=50:raise ValueError('limit must be 1..50')
    url='https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?'+urlencode({'q':'$'+ticker,'limit':limit,'sort':'latest'})
    data=fetch(url)
    observed=iso(dt.datetime.now(UTC))
    rows=[]
    for item in data.get('posts',[])[:limit]:
        rec=item.get('record') or {}
        txt=rec.get('text') or ''
        if ticker not in set(SYMBOL_RE.findall(txt.upper())):continue
        uri=item.get('uri','')
        rkey=uri.split('/')[-1]
        author=item.get('author') or {}
        handle=author.get('handle','')
        link=f'https://bsky.app/profile/{quote(handle,safe="")}/post/{quote(rkey,safe="")}'
        row=_public_row('bluesky',uri,rec.get('createdAt',''),observed,txt,
                        author.get('did'),link,sum(int(item.get(k,0) or 0) for k in ('likeCount','replyCount','repostCount')))
        row['ticker']=ticker
        rows.append(verified_event(row))
    return rows


def collect_mastodon(ticker,instance='mastodon.social',hashtag='stocks',limit=30,fetch=public_get):
    ticker=valid_symbol(ticker)
    if instance not in ALLOWED_MASTODON:raise ValueError('Mastodon instance not on public endpoint allowlist')
    if not re.fullmatch('[A-Za-z0-9_]{1,35}',hashtag):raise ValueError('invalid hashtag')
    if not 1<=limit<=40:raise ValueError('limit must be 1..40')
    url=f'https://{instance}/api/v1/timelines/tag/{hashtag}?'+urlencode({'limit':limit})
    data=fetch(url)
    if not isinstance(data,list):raise ValueError('unexpected mastodon response')
    observed=iso(dt.datetime.now(UTC));rows=[]
    for item in data[:limit]:
        if item.get('visibility','public')!='public':continue
        parser=_Stripper();parser.feed(item.get('content') or '')
        txt=parser.result()
        if ticker not in set(SYMBOL_RE.findall(txt.upper())):continue
        account=item.get('account') or {}
        row=_public_row('mastodon',str(item.get('uri') or item.get('id','')),
                        item.get('created_at',''),observed,txt,account.get('id'),
                        item.get('url',''),sum(int(item.get(k,0) or 0) for k in ('favourites_count','replies_count','reblogs_count')))
        row['ticker']=ticker
        rows.append(verified_event(row))
    return rows


def main(argv=None):
    p=argparse.ArgumentParser(description='Meridyen Social V5 FREE (offline/read-only research)')
    s=p.add_subparsers(dest='cmd',required=True)
    s.add_parser('status')
    a=s.add_parser('analyze');a.add_argument('--input',required=True);a.add_argument('--ticker',required=True);a.add_argument('--as-of',required=True);a.add_argument('--current-hours',type=float,default=24);a.add_argument('--baseline-hours',type=float,default=72)
    b=s.add_parser('evaluate');b.add_argument('--input',required=True);b.add_argument('--as-of',required=True);b.add_argument('--split-date',required=True)
    c=s.add_parser('collect-bluesky');c.add_argument('--ticker',required=True);c.add_argument('--limit',type=int,default=30);c.add_argument('--output',required=True)
    d=s.add_parser('collect-mastodon');d.add_argument('--ticker',required=True);d.add_argument('--instance',default='mastodon.social');d.add_argument('--hashtag',default='stocks');d.add_argument('--limit',type=int,default=30);d.add_argument('--output',required=True)
    e=s.add_parser('validate');e.add_argument('--input',required=True)
    args=p.parse_args(argv)
    try:
        if args.cmd=='status':result=status()
        elif args.cmd=='analyze':result=analyze(load_events(args.input),args.ticker,args.as_of,args.current_hours,args.baseline_hours)
        elif args.cmd=='evaluate':result=evaluate(args.input,args.as_of,args.split_date)
        elif args.cmd=='validate':result={'valid_posts':len(load_events(args.input)),'is_canonical':False}
        elif args.cmd=='collect-bluesky':
            rows=collect_bluesky(args.ticker,args.limit);write_events(args.output,rows)
            result={'saved':len(rows),'output':args.output,'source':'bluesky_public','no_api_key':True}
        else:
            rows=collect_mastodon(args.ticker,args.instance,args.hashtag,args.limit);write_events(args.output,rows)
            result={'saved':len(rows),'output':args.output,'source':'mastodon_public','no_api_key':True}
        print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2));return 0
    except (ValueError,KeyError,TypeError,IOError,RuntimeError,OverflowError,json.JSONDecodeError) as exc:
        print(json.dumps({'status':'FREE_DATA_BLOCKED','error':str(exc)},ensure_ascii=False),file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
