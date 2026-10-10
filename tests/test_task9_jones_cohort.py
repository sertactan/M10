"""Synthetic SEC integration and negative gates; no claimed actual S11 peers."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from app.task9_jones_cohort import (
    SECCache, SECStop, _find_fy2025_facts, _review_amendments,
    _amendment_same_eight, digest, historical_header,
    independent_decimal_reference, read_sec_contact, sic_listing,
)
from app.recovered_jones import compute_s11
from tests.test_scoring_v3_jones_peers import payloads
from tests.test_recovered_jones import issuer


class Response:
    def __init__(self, raw, status=200):
        self.raw=raw
        self.status=status
        self.offset=0
    def read(self,n):
        out=self.raw[self.offset:self.offset+n]
        self.offset+=len(out)
        return out
    def __enter__(self):
        return self
    def __exit__(self,*_):
        return False


class Task9JonesTests(unittest.TestCase):
    @staticmethod
    def fake_amendment():
        sample,companyfacts,submission,header=payloads(29)
        payload=json.loads(submission)
        amended_acc="0001104659-26-060000"
        changes={
            "accessionNumber":amended_acc,
            "form":"10-K/A",
            "reportDate":"2025-12-31",
            "filingDate":"2026-04-30",
            "acceptanceDateTime":"2026-04-30T16:00:00Z",
        }
        for key,value in changes.items():
            payload["filings"]["recent"][key].append(value)
        h=(
            f"<SEC-DOCUMENT>{amended_acc}.txt\n"
            "<SEC-HEADER>\n"
            f"ACCESSION NUMBER: {amended_acc}\n"
            "CONFORMED SUBMISSION TYPE: 10-K/A\n"
            "CONFORMED PERIOD OF REPORT: 20251231\n"
            f"CENTRAL INDEX KEY: {sample['cik']}\n"
            "STANDARD INDUSTRIAL CLASSIFICATION: SERVICES [7374]\n"
            "</SEC-HEADER>\n"
            "EXPLANATORY NOTE: This amendment is being filed solely to include "
            "information required by PART III of the Form 10-K. "
            "No other changes have been made to the original filing."
        ).encode()
        return sample,companyfacts,json.dumps(payload).encode(),h,amended_acc

    def test_read_sec_contact_never_default_fake(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/".env"
            p.write_text("SEC_USER_AGENT=Fake Company test@example.com\n")
            self.assertIsNone(read_sec_contact(p))
            p.write_text("SEC_USER_AGENT=Valid Lab Contact researcher@real.org\n")
            self.assertIsNotNone(read_sec_contact(p))
            self.assertIsNone(read_sec_contact(Path(temp)/"missing"))

    def test_private_cache_no_network_on_second_call_and_sha_strict(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls=[]
            def provider(req,timeout):
                calls.append(req.full_url)
                return Response(b'{"status":"ok"}')
            cache=SECCache(Path(tmp)/"task9_jones_unit",contact="Valid contact@real.org",
                           transport=provider,min_gap=0,sleeper=lambda _:None)
            url="https://data.sec.gov/submissions/CIK0000903651.json"
            a,meta=cache.load(url)
            b,meta2=cache.load(url)
            self.assertEqual(a,b)
            self.assertEqual(len(calls),1)
            self.assertEqual(cache.cached,1)
            self.assertEqual(cache.requests,1)
            self.assertEqual(meta["sha256"],digest(a))
            entry=next((cache.root/"responses").glob("*.bin"))
            entry.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError,"source hash mismatch"):
                cache.load(url)

    def test_no_retry_or_repeated_fetch_after_403_or_429(self):
        for status in (403,429):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                calls=[]
                def provider(req,timeout):
                    calls.append(req.full_url)
                    raise HTTPError(req.full_url,status,"denied",{},None)
                cache=SECCache(Path(tmp)/"task9_jones_unit",contact="Contact@real.org",
                               transport=provider,min_gap=0)
                with self.assertRaisesRegex(SECStop,str(status)):
                    cache.load("https://www.sec.gov/cgi-bin/browse-edgar?SIC=7374")
                with self.assertRaisesRegex(SECStop,"STOPPED"):
                    cache.load("https://www.sec.gov/Archives/edgar/data/1/test")
                self.assertEqual(len(calls),1)
                self.assertTrue(cache.blocked)

    def test_request_budget_no_retries_and_only_official_https(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=SECCache(Path(tmp)/"task9_jones_unit",contact="contact@real.org",
                           request_budget=0,min_gap=0)
            with self.assertRaisesRegex(SECStop,"BUDGET"):
                cache.load("https://www.sec.gov/any")
            with self.assertRaises(ValueError):
                cache.load("https://attacker.invalid/any")
            self.assertEqual(cache.requests,0)

    def test_official_sic_page_parsed_but_not_industry_date(self):
        listing=(
            b'<tr><td><a href="/cgi-bin/browse-edgar?action=getcompany&amp;CIK=0000903651">'
            b'0000903651</a></td><td scope="row">INNODATA INC</td></tr>'
        )
        with tempfile.TemporaryDirectory() as tmp:
            cache=SECCache(Path(tmp)/"task9_jones_unit",contact="Contact@real.org",
                           transport=lambda *a,**k:Response(listing),min_gap=0)
            rows,sources=sic_listing(cache,pages=1)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["cik"],"0000903651")
            self.assertEqual(rows[0]["directory_source_sha256"],sha256(listing).hexdigest())
            self.assertEqual(rows[0]["listed_sec_sic"],"7374")
            self.assertNotIn("effective_on",rows[0])

    def test_exact_eight_field_preflight_and_absent_source(self):
        _,raw,_,_=payloads(29)
        best,error=_find_fy2025_facts(raw)
        self.assertIsNone(error)
        self.assertEqual(best["exact_field_count"],8)
        data=json.loads(raw)
        del data["facts"]["us-gaap"]["PropertyPlantAndEquipmentNet"]
        best,error=_find_fy2025_facts(json.dumps(data).encode())
        self.assertEqual(best["exact_field_count"],7)

    def test_official_header_raw_matches_fy_and_historical_sic(self):
        target,companyfacts,sub,header=payloads(29)
        accession={"accession":"0001104659-26-020655",
                   "accepted_at":"2026-03-01T12:00:00+00:00",
                   "report_date":"2025-12-31"}
        with tempfile.TemporaryDirectory() as tmp:
            cache=SECCache(Path(tmp)/"task9_jones_unit",contact="Contact@real.org",
                           transport=lambda *a,**k:Response(header["header_bytes"]),
                           min_gap=0)
            recovered,receipt,provenance=historical_header(
                cache,target["cik"],accession,end="2025-12-31")
            self.assertIsNotNone(recovered)
            self.assertEqual(receipt["sha256"],sha256(header["header_bytes"]).hexdigest())
            self.assertEqual(provenance["filing_report_date"],"2025-12-31")

    def test_historical_header_source_rejects_wrong_cik(self):
        target,_,_,header=payloads(29)
        accession={"accession":"0001104659-26-020655",
                   "accepted_at":"2026-03-01T12:00:00+00:00",
                   "report_date":"2025-12-31"}
        wrong=header["header_bytes"].replace(target["cik"].encode(),b"0001234001")
        with tempfile.TemporaryDirectory() as tmp:
            cache=SECCache(Path(tmp)/"task9_jones_unit",contact="Contact@real.org",
                           transport=lambda *a,**k:Response(wrong),
                           min_gap=0)
            recovered,receipt,provenance=historical_header(
                cache,target["cik"],accession,end="2025-12-31")
            self.assertIsNone(recovered)
            self.assertIsNone(provenance)

    def test_independent_decimal_reference_matches_20_synthetic_peers(self):
        target=issuer(29,target=True)
        peers=[issuer(i) for i in range(1,21)]
        engine=compute_s11(target,peers,datetime(2026,10,11,tzinfo=timezone.utc))
        self.assertIsNotNone(engine["score"])
        ref=independent_decimal_reference(
            target,peers,engine["components"]["OLS_coefficients"],engine)
        self.assertTrue(ref["within_1e_8"])
        self.assertLessEqual(float(ref["max_abs_score_diff"]),1e-8)
        self.assertLess(float(ref["max_relative_ols_coefficient_error"]),1e-8)

    def test_10ka_part_iii_scope_proven_and_filtered_in_auditable_submissions(self):
        issuer,companyfacts,sub,amended_header,amend_acc=self.fake_amendment()
        with tempfile.TemporaryDirectory() as temp:
            cache=SECCache(Path(temp)/"task9_jones_unit",contact="Contact@real.org",
                           transport=lambda *a,**k:Response(amended_header),min_gap=0)
            filtered,review=_review_amendments(
                cache,sub,companyfacts,issuer["cik"],
                datetime(2026,10,11,tzinfo=timezone.utc))
            self.assertIsNotNone(filtered)
            self.assertEqual(review[0]["status"],"FINANCIALLY_UNCHANGED_AMENDMENT_REVIEWED")
            self.assertTrue(review[0]["explicit_scope_part_iii"])
            self.assertEqual(review[0]["financial_comparison"],"AMENDMENT_NO_US_GAAP_USD_TAGS")
            self.assertNotEqual(digest(filtered),digest(sub))
            # Original stored SEC Submissions bytes remain unmodified.
            self.assertIn(amend_acc,sub.decode())
            self.assertNotIn(amend_acc,filtered.decode())

    def test_10ka_missing_explanatory_scope_is_rejected(self):
        issuer,companyfacts,sub,header,_=self.fake_amendment()
        header=header.replace(
            b"EXPLANATORY NOTE: This amendment is being filed solely to include "
            b"information required by PART III of the Form 10-K. "
            b"No other changes have been made to the original filing.",
            b"Amended disclosure, unspecified scope.")
        with tempfile.TemporaryDirectory() as temp:
            cache=SECCache(Path(temp)/"task9_jones_unit",contact="Contact@real.org",
                           transport=lambda *a,**k:Response(header),min_gap=0)
            filtered,review=_review_amendments(cache,sub,companyfacts,issuer["cik"],
                                               datetime(2026,10,11,tzinfo=timezone.utc))
            self.assertIsNone(filtered)
            self.assertIn("UNRESOLVED",review[0]["status"])

    def test_10ka_financial_change_never_silently_accepted(self):
        issuer,raw,sub,header,acc=self.fake_amendment()
        data=json.loads(raw)
        first=data["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"][0].copy()
        first["accn"]=acc
        first["val"]+=300
        data["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"].append(first)
        safe,reason=_amendment_same_eight(json.dumps(data).encode(),
                                         "0001104659-26-020655",acc,"2025-12-31")
        self.assertFalse(safe)
        self.assertIn("MODIFIED",reason)
        with tempfile.TemporaryDirectory() as temp:
            cache=SECCache(Path(temp)/"task9_jones_unit",contact="Contact@real.org",
                           transport=lambda *a,**k:Response(header),min_gap=0)
            filtered,review=_review_amendments(cache,sub,json.dumps(data).encode(),
                                               issuer["cik"],datetime(2026,10,11,
                                               tzinfo=timezone.utc))
            self.assertIsNone(filtered)
            self.assertEqual(review[0]["status"],"AMENDMENT_SCOPE_OR_FINANCIAL_CHANGE_UNRESOLVED")


if __name__=="__main__":
    unittest.main()
