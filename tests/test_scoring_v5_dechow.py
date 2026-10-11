"""The V5 partition boundary must never manufacture individual RSST inputs."""
import unittest
from unittest.mock import patch

from app.scoring_v5_dechow import audit_partitions


class PartitionBoundaryTest(unittest.TestCase):
    def test_source_digest_required(self):
        with self.assertRaisesRegex(ValueError, 'COMPANYFACTS_SOURCE_CHANGED'):
            audit_partitions(b'{}', b'', {})

    def test_symbolic_terms_preserve_missing_classifications(self):
        # Reuse the audit's pinned issuer source; this is a pure-function gate
        # test, while the private replay exercises original SEC bytes.
        from app.scoring_v5_dechow import COMPANYFACTS_SHA256
        fixture = {'facts': {}}
        rows = {str(y): {'facts': {'cash': {'value': 10}, 'assets': {'value': 100},
                                      'liabilities': {'value': 40}},
                         'aggregate_usd': '50'} for y in (2023, 2024, 2025)}
        with patch('app.scoring_v5_dechow.sha256') as digest, \
             patch('app.scoring_v5_dechow.audit_rsst', return_value={
                 'years': rows, 'filing_bodies_sha256': {},
                 'model_source_sha256': 'model', 'RSST_decimal': '0.1'}), \
             patch('app.scoring_v5_dechow.json.loads', return_value=fixture), \
             patch('app.scoring_v5_dechow._fact') as fact:
            digest.return_value.hexdigest.return_value = COMPANYFACTS_SHA256
            fact.side_effect = lambda data, tag, year, unit: {'value': 70 if tag == 'AssetsCurrent' else 20}
            result = audit_partitions(b'source', b'model', {})
        self.assertEqual(result['years']['2025']['WC_base_usd'], '40')
        self.assertEqual(result['years']['2025']['NCO_base_usd'], '10')
        self.assertIsNone(result['years']['2025']['WC_accepted'])
        self.assertFalse(result['RSST_frozen_accepted'])


if __name__ == '__main__':
    unittest.main()
