import unittest
from datetime import datetime,timezone,timedelta
from app.scoring_intraday_research import parse_minutes,five_minute
class IntradayTests(unittest.TestCase):
    def payload(self,start):
        return {'chart':{'result':[{'meta':{'symbol':'INOD','dataGranularity':'1m'},'timestamp':[int((start+timedelta(minutes=i)).timestamp()) for i in range(5)],'indicators':{'quote':[{'open':[10]*5,'high':[12]*5,'low':[9]*5,'close':[11]*5,'volume':[100]*5}]}}]}}
    def test_complete_bars_only_and_volume_conserved(self):
        start=datetime(2026,10,9,13,30,tzinfo=timezone.utc)
        rows,skip=parse_minutes(self.payload(start),'INOD',start+timedelta(minutes=5))
        five=five_minute(rows);self.assertEqual(skip,0);self.assertEqual(len(five),1);self.assertEqual(five[0]['volume'],500)
        self.assertEqual(len(five_minute(rows[:-1])),0)
        partial,skip=parse_minutes(self.payload(start),'INOD',start+timedelta(minutes=4,seconds=30))
        self.assertEqual(len(partial),4);self.assertEqual(skip,1)
    def test_dst_offsets_and_premarket_not_zero(self):
        for month,day,hour,offset in ((10,9,13,'-04:00'),(11,9,14,'-05:00')):
            start=datetime(2026,month,day,hour,30,tzinfo=timezone.utc)
            rows,_=parse_minutes(self.payload(start),'INOD',start+timedelta(minutes=5))
            self.assertTrue(rows[0]['exchange_time'].endswith(offset));self.assertEqual(rows[0]['session'],'REGULAR_CLOCK')
    def test_identity_interval_and_bad_ohlc_rejected(self):
        start=datetime(2026,10,9,13,30,tzinfo=timezone.utc)
        p=self.payload(start);p['chart']['result'][0]['indicators']['quote'][0]['low'][0]=15
        with self.assertRaises(ValueError):parse_minutes(p,'INOD',start+timedelta(minutes=5))
        with self.assertRaisesRegex(ValueError,'Ticker'):parse_minutes(self.payload(start),'TMDX',start+timedelta(minutes=5))
if __name__=='__main__':unittest.main()
