"""Dependency-free Beneish gate checks for Windows staging."""
import unittest

from app.scoring_v4_beneish import decimal_ratios, InlineEvidence


class BeneishGateTests(unittest.TestCase):
    def test_inline_presentation_dash_is_missing(self):
        parser = InlineEvidence()
        parser.feed('<ix:nonFraction name="inod:Debt" scale="3">—</ix:nonFraction>')
        self.assertIsNone(parser.facts[0]['value'])

    def test_missing_and_zero_prior_debt_remain_distinct(self):
        base = dict(dep_prior=10, dep_current=12, ppe_prior=100, ppe_current=110,
                    debt_prior=20, debt_current=22, assets_prior=200, assets_current=250)
        self.assertEqual(decimal_ratios(**dict(base, debt_prior=None))['LVGI']['status'], 'DATA_MISSING')
        self.assertEqual(decimal_ratios(**dict(base, debt_prior=0))['LVGI']['status'], 'UNDEFINED_ZERO_DENOMINATOR')

    def test_pure_depreciation_missing_blocks_depi(self):
        inputs = dict(dep_prior=10, dep_current=None, ppe_prior=100, ppe_current=110,
                      debt_prior=20, debt_current=22, assets_prior=200, assets_current=250)
        self.assertEqual(decimal_ratios(**inputs)['DEPI'], {'value':None,'status':'DATA_MISSING'})

    def test_reference_math(self):
        inputs = dict(dep_prior=10, dep_current=12, ppe_prior=100, ppe_current=110,
                      debt_prior=20, debt_current=22, assets_prior=200, assets_current=250)
        ratios = decimal_ratios(**inputs)
        self.assertAlmostEqual(float(ratios['DEPI']['value']), 10*122/(110*12))
        self.assertEqual(ratios['LVGI']['value'], '0.88')


if __name__ == '__main__':
    unittest.main()
