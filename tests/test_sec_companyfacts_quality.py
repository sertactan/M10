"""SEC Companyfacts normalization safety with synthetic XBRL fixtures."""
from datetime import datetime, timezone
import json
import tempfile
from pathlib import Path
import unittest

from app.sec_companyfacts_quality import extract_exact_companyfacts, partial_beneish_diagnostics
from app.scoring_completion import attach_sec_companyfacts_partial


ACCESSION="0001104659-26-020655"
RETRIEVED="2026-10-10T17:53:29+00:00"


def raw(source_tag="AccountsReceivableNetCurrent", year=2025, *, val=123, unit="USD"):
    return json.dumps({"cik":903651,"facts":{"us-gaap":{
        source_tag:{"units":{unit:[{"val":val,"accn":ACCESSION,"form":"10-K",
           "end":f"{year}-12-31","filed":"2026-02-26","fy":2025,"fp":"FY"}]}}
    }}}).encode()


def normalized(data, **kwargs):
    return extract_exact_companyfacts(data,ticker="INOD",cik="0000903651",
        accession=ACCESSION,retrieved_at=RETRIEVED,fiscal_years=(2024,2025),**kwargs)


class SecXbrlTests(unittest.TestCase):
    def test_realistic_exact_tag_from_correct_filing_is_research_only(self):
        result=normalized(raw())
        self.assertEqual(len(result["rows"]),1)
        record=result["rows"][0]
        self.assertEqual(record["metric"],"ACCOUNTS_RECEIVABLE_NET")
        self.assertEqual(record["period_end"],"2025-12-31")
        self.assertEqual(record["value"],123)
        self.assertEqual(record["form_type"],"10-K")
        self.assertIsNone(record["accepted_at"])
        self.assertFalse(record["historical_pit_accepted"])
        self.assertIn("TOTAL_DEBT_FY_2025_EXACT_TAG",result["missing"])
        diag=partial_beneish_diagnostics(result["rows"],2025)
        self.assertIsNone(diag["B_Q_score"])
        self.assertTrue(all(x is None for x in diag["ratios"].values()))

    def test_missing_tag_wrong_unit_or_wrong_accession_never_imputed(self):
        for value in (raw(unit="shares"),raw("DepreciationDepletionAndAmortization"),
                      raw("LongTermDebt")):
            with self.subTest(payload=value):
                result=normalized(value)
                self.assertEqual(result["rows"],[])
                self.assertIn("TOTAL_DEBT_FY_2025_EXACT_TAG",result["missing"])

    def test_issuer_and_temporal_guards(self):
        with self.assertRaisesRegex(ValueError,"issuer"):
            extract_exact_companyfacts(raw(),ticker="INOD",cik="0000777777",
                accession=ACCESSION,retrieved_at=RETRIEVED,fiscal_years=(2025,))
        value=json.loads(raw())
        value["facts"]["us-gaap"]["AccountsReceivableNetCurrent"]["units"]["USD"][0]["filed"]="2027-01-01"
        result=normalized(json.dumps(value).encode())
        self.assertEqual(result["rows"],[])
        self.assertIn("ACCOUNTS_RECEIVABLE_NET_FY_2025_FUTURE_FILED",result["missing"])

    def test_attachment_blocks_unverified_or_missing_receipt(self):
        report={"stocks":[{"ticker":"INOD","models":[{"model":"S14","score":None}],
                            "quality":{"B_Q":{"score":None,"components":{}}}},
                           *[{"ticker":x} for x in ("TMDX","CRMD","PENG","ETON")]]}
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/"quality_partial.json"
            with self.assertRaisesRegex(ValueError,"source missing"):
                attach_sec_companyfacts_partial(report,src)
            self.assertEqual(report["stocks"][0]["quality"]["B_Q"]["score"],None)


if __name__=="__main__":
    unittest.main()
