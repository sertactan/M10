"""Synthetic accounting sample validates the recovered S6 arithmetic and gates."""
import math
import unittest
from datetime import datetime, timezone
from app.recovered_dechow import calculate_dechow


AT = datetime(2026, 10, 11, tzinfo=timezone.utc)
DATA = [
    dict(assets=100, receivables=10, inventory=5, ppe=40, cash=10,
         sales=100, net_income=10, wc=20, nco=11, fin=5),
    dict(assets=120, receivables=12, inventory=6, ppe=50, cash=12,
         sales=140, net_income=12, wc=23, nco=12, fin=4),
    dict(assets=150, receivables=14, inventory=7, ppe=60, cash=15,
         sales=160, net_income=13, wc=25, nco=14, fin=3),
]


def fixture():
    return [dict(start=f"{year}-01-01", end=f"{year}-12-31", facts={
        field: dict(value=value, period_end=f"{year}-12-31", source="SEC_EDGAR",
                    source_ref=f"https://data.sec.gov/api/xbrl/companyfacts/CIK0000903651.json",
                    accession=f"TEST:{year}",
                    available_at="2026-03-01T00:00:00Z", evidence_hash="a5"*32)
        for field, value in DATA[year - 2023].items()}) for year in range(2023, 2026)]


def reviews():
    return dict(decomposition_review={"verified": True, "reviewer": "synthetic-test",
                    "methodology_ref": "fixture:wc_nco_fin", "source_hash": "bb"*32},
                issuance_review={"verified": True, "issued": 0,
                    "source_ref": "fixture:issuance_audit", "evidence_hash": "cd"*32,
                    "available_at": "2026-03-01T00:00:00Z"})


class DechowTests(unittest.TestCase):
    def test_exact_original_logit_and_unambiguous_fallback(self):
        res = calculate_dechow(fixture(), as_of=AT, **reviews())
        self.assertIsNotNone(res["score"], res["missing"])
        expected_rsst = ((25-23)+(14-12)+(3-4))/135
        self.assertAlmostEqual(res["components"]["RSST"], expected_rsst)
        expected_l = (-7.893 + .790*expected_rsst + 2.518*(2/135) +
                      1.191*(1/135) + 1.979*((150-60-15)/150)
                      + .171*((160-2-(140-2))/138)
                      - .932*(13/135-12/110))
        self.assertAlmostEqual(res["components"]["logistic_L"], expected_l)
        self.assertAlmostEqual(res["components"]["F_D"],
                               (1/(1+math.exp(-expected_l)))/.0037)
        self.assertEqual(res["score"], 95)
        self.assertFalse(res["canonical_accepted"])

    def test_missing_review_or_issuance_never_defaults(self):
        self.assertIsNone(calculate_dechow(fixture(), as_of=AT)["score"])
        self.assertIn("AUDITED_RSST_WC_NCO_FIN_DECOMPOSITION",
                      calculate_dechow(fixture(), as_of=AT)["missing"])
        self.assertIn("DOCUMENTED_DEBT_EQUITY_ISSUANCE_OR_CONFIRMED_ABSENCE",
                      calculate_dechow(fixture(), as_of=AT)["missing"])

    def test_requires_three_contiguous_years_and_source_times(self):
        self.assertIsNone(calculate_dechow(fixture()[1:], as_of=AT, **reviews())["score"])
        periods=fixture()
        periods[1]["start"]="2024-02-01"
        self.assertIn("FISCAL_PERIOD_GAP_OR_FUTURE",
                      calculate_dechow(periods, as_of=AT, **reviews())["missing"])
        periods=fixture()
        periods[2]["facts"]["assets"]["available_at"]="2027-01-01T00:00:00Z"
        self.assertIn("FY_2_ASSETS_SOURCE",
                      calculate_dechow(periods, as_of=AT, **reviews())["missing"])

    def test_false_peers_or_unverified_issuance_block(self):
        bad = dict(reviews())
        bad["issuance_review"] = {**bad["issuance_review"], "verified": False}
        self.assertIsNone(calculate_dechow(fixture(), as_of=AT, **bad)["score"])
        self.assertIsNone(calculate_dechow(fixture(), as_of=AT, peer_percentile={
            "verified": True, "percentile": .4, "fiscal_year": 2025,
            "cohort": ["A", "B"], "evidence_hash": "ab"*32,
            "source_ref": "fixture:peers"}, **reviews())["score"])


if __name__ == "__main__":
    unittest.main()
