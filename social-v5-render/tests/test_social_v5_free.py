import csv
import datetime as dt
import importlib.util
from pathlib import Path
import tempfile
import unittest

MODPATH=Path(__file__).resolve().parents[1]/'social_v5_free.py'
spec=importlib.util.spec_from_file_location('social_free',MODPATH)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ASOF='2026-10-08T18:00:00Z'


def post(i,platform='reddit',age=1,text=None,author=None):
    now=dt.datetime.fromisoformat(ASOF.replace('Z','+00:00'))
    d=(now-dt.timedelta(hours=age)).isoformat()
    return dict(platform=platform,source_id=f'{platform}-{i}',created_at=d,observed_at=d,
                ticker='INOD',text=text or f'new idea for $INOD {i}',
                author_hash=m.sha(str(author or i))[:24],engagement=1,sentiment='',
                source_url='https://example.org/p/'+str(i),capture_proof='user_supplied_unverified')


class SocialV5Tests(unittest.TestCase):
    def test_status_no_paid_key(self):
        s=m.status();self.assertEqual(s['paid_api_budget_usd'],0);self.assertFalse(s['host_live_stream_connected'])
    def test_valid_input(self):self.assertEqual(m.verified_event(post(1))['ticker'],'INOD')
    def test_requires_cashtag(self):
        p=post(1);p['text']='INOD is up';self.assertRaises(ValueError,m.verified_event,p)
    def test_reject_ambiguous_substring(self):
        p=post(1,text='hello $INODE and other stuff');self.assertRaises(ValueError,m.verified_event,p)
    def test_reject_naive_timestamp(self):
        p=post(1);p['observed_at']='2026-10-08T13:00:00';self.assertRaises(ValueError,m.verified_event,p)
    def test_observed_before_created(self):
        p=post(1);p['observed_at']='2020-01-01T00:00:00Z';self.assertRaises(ValueError,m.verified_event,p)
    def test_reject_http(self):
        p=post(1);p['source_url']='http://example.org';self.assertRaises(ValueError,m.verified_event,p)
    def test_reject_nan(self):
        p=post(1);p['engagement']='NaN';self.assertRaises(ValueError,m.verified_event,p)
    def test_reject_infinite_sentiment(self):
        p=post(1);p['sentiment']='inf';self.assertRaises(ValueError,m.verified_event,p)
    def test_deduplicate_source_ids(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'posts.csv';m.write_events(f,[post(1),post(1)])
            self.assertEqual(len(m.load_events(f)),1)
    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'posts.csv';m.write_events(f,[post(1)]);
            self.assertRaises(FileExistsError,m.write_events,f,[post(2)])
    def test_future_posts_not_counted(self):
        p=post(1);p['observed_at']='2026-10-09T00:00:00Z';
        a=m.analyze([m.verified_event(p)],'INOD',ASOF)
        self.assertEqual(a['coverage']['current_posts'],0)
    def test_zero_baseline_not_infinity(self):
        a=m.analyze([m.verified_event(post(1))],'INOD',ASOF)
        self.assertIsNone(a['velocity_ratio']);self.assertEqual(a['state'],'BASELINE_MISSING')
    def test_qualifies_research_watch_with_sources(self):
        rows=[post(20,age=40)] + [post(i,platform='reddit' if i%2 else 'bluesky',age=1) for i in range(6)]
        a=m.analyze([m.verified_event(x) for x in rows],'INOD',ASOF)
        self.assertEqual(a['state'],'RESEARCH_WATCH_NONCANONICAL')
        self.assertFalse(a['is_trade_signal'])
    def test_duplicates_flagged_not_independent(self):
        rows=[post(90,age=48)] + [post(i,platform='reddit' if i%2 else 'bluesky',text='copy $INOD BUY!',age=1) for i in range(7)]
        a=m.analyze([m.verified_event(x) for x in rows],'INOD',ASOF)
        self.assertEqual(a['state'],'COORDINATION_HEURISTIC_REVIEW')
        self.assertTrue(a['coordination_heuristic'])
    def test_missing_authors_not_independent(self):
        rows=[post(90,age=48)] + [post(i,platform='reddit' if i%2 else 'bluesky',age=1) for i in range(7)]
        for x in rows:x['author_hash']=''
        a=m.analyze([m.verified_event(x) for x in rows],'INOD',ASOF)
        self.assertFalse(a['cross_platform_independence_proxy'])
    def test_no_sentiment_fabrication(self):
        a=m.analyze([m.verified_event(post(1))],'INOD',ASOF)
        self.assertIsNone(a['annotated_sentiment_mean'])
    def test_no_symbol_from_plain_ai(self):
        p=post(1);p['ticker']='AI';p['text']='Artificial Intelligence is taking off';
        self.assertRaises(ValueError,m.verified_event,p)
    def test_mastodon_instance_allowlist(self):
        self.assertRaises(ValueError,m.collect_mastodon,'INOD',instance='localhost')
    def test_bluesky_url_fixed(self):
        urls=[]
        def fake(u): urls.append(u);return {'posts':[{'uri':'at://did:plc:myid/app.bsky.feed.post/abcd','record':{'createdAt':'2026-10-01T00:00:00Z','text':'Good news $INOD'},'author':{'handle':'example.bsky.social','did':'did:plc:myid'}}]}
        rows=m.collect_bluesky('INOD',fetch=fake)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['capture_proof'],'public_network_capture')
        self.assertEqual(__import__('urllib.parse',fromlist=['urlparse']).urlparse(urls[0]).hostname,'public.api.bsky.app')
    def test_mastodon_rejects_nonpublic(self):
        def fake(_):return [{'id':'1','uri':'https://mastodon.social/users/1/statuses/1','created_at':'2026-10-01T00:00:00Z','content':'Hello <b>$INOD</b>','visibility':'private','url':'https://mastodon.social/@person/1'}]
        self.assertEqual(m.collect_mastodon('INOD',fetch=fake),[])
    def test_mastodon_strips_html(self):
        def fake(_):return [{'id':'1','uri':'https://mastodon.social/users/1/statuses/1','created_at':'2026-10-01T00:00:00Z','content':'Hello <b>$INOD</b>','visibility':'public','url':'https://mastodon.social/@person/1'}]
        rows=m.collect_mastodon('INOD',fetch=fake)
        self.assertEqual(len(rows),1);self.assertIn('Hello $INOD',rows[0]['text'])
    def test_backtest_leakage_and_future_maturity(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'signals.csv'
            cols=['signal_time','signal_observed_at','outcome_available_at','prediction','label','source_ref']
            rows=[
            ['2026-09-01T00:00:00Z','2026-09-01T00:00:00Z','2026-09-03T00:00:00Z','1','1','a'],
            ['2026-09-30T00:00:00Z','2026-09-30T00:00:00Z','2026-10-04T00:00:00Z','1','0','b'],
            ['2026-10-02T00:00:00Z','2026-10-02T00:00:00Z','2026-10-04T00:00:00Z','0','1','c'],
            ['2026-10-07T00:00:00Z','2026-10-07T00:00:00Z','2026-10-15T00:00:00Z','1','1','d'],
            ['2026-10-03T00:00:00Z','2026-10-04T00:00:00Z','2026-10-05T00:00:00Z','1','1','e']]
            with f.open('w',newline='',encoding='utf-8') as fp:
                w=csv.writer(fp);w.writerow(cols);w.writerows(rows)
            result=m.evaluate(f,ASOF,'2026-10-01T00:00:00Z')
            self.assertEqual(result['train']['n'],1)
            self.assertEqual(result['test']['n'],1)
            self.assertEqual(result['excluded']['train_label_leakage'],1)
            self.assertEqual(result['excluded']['not_matured'],1)
            self.assertEqual(result['excluded']['not_observed_as_of_signal'],1)
            self.assertFalse(result['model_trained'])
    def test_backtest_invalid_label(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'labels.csv'
            with f.open('w',newline='') as fp:
                w=csv.writer(fp);w.writerow(['signal_time','signal_observed_at','outcome_available_at','prediction','label','source_ref'])
                w.writerow(['2026-10-02T00:00:00Z','2026-10-02T00:00:00Z','2026-10-04T00:00:00Z','yes','1','x'])
            self.assertRaises(ValueError,m.evaluate,f,ASOF,'2026-10-01T00:00:00Z')

if __name__=='__main__':unittest.main()
