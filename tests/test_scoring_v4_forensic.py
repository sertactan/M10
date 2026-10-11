"""The new proxy is scoped evidence, not an automated risk ruling."""
import unittest

from app.scoring_v4_forensic import proxy_context


class ProxyScopeTests(unittest.TestCase):
    def test_item404_context_retains_threshold_and_no_numeric_risk(self):
        text = ('There have been no related party transactions, as of the date hereof '
                'under Item 404 involving $120,000 or one percent (1%) and a material interest. '
                'EXPENSE OF SOLICITATION')
        result = proxy_context(b'%PDF-1.7\n', text)
        self.assertIsNone(result['risk'])
        self.assertFalse(result['human_review_completed'])
        self.assertEqual(result['scope'],'ITEM404_DISCLOSURE_THRESHOLD_AS_OF_PROXY_DATE')

    def test_claim_without_threshold_context_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'DISCLOSURE_THRESHOLD_CONTEXT_MISSING'):
            proxy_context(b'%PDF-1.7\n',
                          'There have been no related party transactions, as of the date hereof '
                          'EXPENSE OF SOLICITATION')


if __name__ == '__main__':
    unittest.main()
