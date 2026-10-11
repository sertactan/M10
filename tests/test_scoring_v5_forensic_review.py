from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from app.scoring_v5_forensic_review import BLOCKS, unsigned_form


class ExpertFormTest(unittest.TestCase):
    def test_unsigned_and_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'packet.json'
            packet = {'issuer': {'ticker': 'INOD', 'cik': '0000903651'},
                      'preserved_findings_verified': 27,
                      'completed_risk_decisions': 0, 'source_contract': {},
                      'blocks': {name: {'preserved_findings': [], 'assessment': '',
                                       'remaining_adjudication': ''} for name in BLOCKS}}
            raw = json.dumps(packet).encode()
            path.write_bytes(raw)
            Path(str(path)+'.sha256').write_text(sha256(raw).hexdigest())
            result = unsigned_form(path)
            self.assertEqual(result['status'], 'REVIEW_REQUIRED')
            self.assertTrue(all(not b['signed'] and b['risk_level_0_25_50_75_100'] is None
                                for b in result['blocks'].values()))
            path.write_bytes(raw+b' ')
            with self.assertRaisesRegex(ValueError, 'SEAL_CHANGED'):
                unsigned_form(path)


if __name__ == '__main__':
    unittest.main()
