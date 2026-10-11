"""Account boundary, source integrity, and missing-value gates for RSST."""
import unittest

from app.scoring_v4_dechow import audit_rsst, rsst_identity, _fact


class RsstIdentityTests(unittest.TestCase):
    def test_original_three_parts_cancel_only_shared_debt_and_investments(self):
        parts, total = rsst_identity()
        self.assertEqual(set(parts), {'WC','NCO','FIN'})
        self.assertEqual(total, {'CASH':-1,'TA':1,'TL':-1,'PREF':-1})

    def test_absent_tag_is_missing_not_zero(self):
        with self.assertRaises(KeyError):
            _fact({'facts':{'us-gaap':{}}},'InventoryNet',2025,'USD')

    def test_wrong_accession_is_rejected(self):
        data={'facts':{'us-gaap':{'Assets':{'units':{'USD':[
            {'end':'2025-12-31','val':1,'accn':'0000000000-00-000000',
             'form':'10-K','filed':'2026-02-26'}]}}}}}
        with self.assertRaisesRegex(ValueError,'EXACT_ANNUAL_INSTANT_MISSING'):
            _fact(data,'Assets',2025,'USD')

    def test_source_tamper_rejected_before_any_score(self):
        with self.assertRaisesRegex(ValueError,'COMPANYFACTS_SOURCE_CHANGED'):
            audit_rsst(b'{}',b'',{})


if __name__ == '__main__':
    unittest.main()
