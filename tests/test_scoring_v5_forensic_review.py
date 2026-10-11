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
                      'filing_bodies_verified': 7,
                      'all_14_official_body_sha256': {str(i): '0'*64 for i in range(14)},
                      'completed_risk_decisions': 0, 'source_contract': {},
                      'S13': None, 'S14': None,
                      'blocks': {name: {'preserved_findings': [dict(
                          finding_id=f'{name}-{i}', block=name, accession='acc',
                          section_reference='section', source_ref='https://www.sec.gov',
                          filing_body_sha256='0'*64, kind='MITIGATING',
                          observed_claim='claim', inference_boundary='boundary')
                          for i in range(4 if name != 'GOV' else 3)],
                          'assessment': '', 'remaining_adjudication': ''}
                          for name in BLOCKS}}
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
