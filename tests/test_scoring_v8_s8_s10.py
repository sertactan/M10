"""Stdlib regression tests. Fixtures are synthetic, never ticker data."""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from app import scoring_v8_s8_s10 as audit


def _row(year, *, flow=False, end=None, accession=None):
    end = end or f"{year}-12-31"
    rec = {"end": end, "val": 100, "form": "10-K", "filed": f"{year+1}-02-15",
           "accn": accession or f"0000000000-{str(year+1)[-2:]}-000001",
           "fy": year, "fp": "FY"}
    if flow:
        rec["start"] = f"{year}-01-01"
    return rec


def _payload(*, drop=None, bad_cik=False, conflict=False):
    drop = drop or set()
    gaap = {}
    definitions = {**audit.S8_TAGS, **audit.S10_TAGS}
    for name, (tag, flow) in definitions.items():
        if name in drop:
            continue
        years = (2024, 2025) if tag == "Liabilities" else range(2021, 2026)
        rows = [_row(year, flow=flow, accession=(
            audit.TARGETS["INOD"]["accession"] if year == 2025 else None
        )) for year in years]
        if conflict and tag == "Assets":
            rows.append(dict(rows[-1], val=120))
        gaap[tag] = {"units": {"USD": rows}}
    raw = json.dumps({"cik": (10 if bad_cik else 903651), "facts": {"us-gaap": gaap}},
                     sort_keys=True).encode()
    return raw


@contextmanager
def _local_hash(ticker, raw):
    with patch.dict(audit.TARGETS, {ticker: dict(audit.TARGETS[ticker],
                                                 sha256=sha256(raw).hexdigest())}):
        yield


class FrozenInputBoundaryTests(unittest.TestCase):
    def test_complete_gaap_diagnostics_never_equal_complete_score(self):
        raw = _payload()
        with _local_hash("INOD", raw):
            result = audit.audit_payload("INOD", raw)
        self.assertEqual(result["fiscal_ends"][2021], "2021-12-31")
        self.assertEqual(result["s8"]["annual_fact_inventory"]["2025"]["assets"]["status"],
                         "EXACT_REPORTED_10K_FACT")
        self.assertEqual(result["s10"]["annual_fact_inventory"]["2021"]["cfo"]["status"],
                         "EXACT_REPORTED_10K_FACT")
        self.assertIsNone(result["s8"]["score"])
        self.assertIsNone(result["s10"]["score"])
        self.assertFalse(result["canonical_pit_accepted"])
        self.assertTrue(any("GNP_PRICE_INDEX" in x for x in result["s8"]["missing"]))
        self.assertEqual(sum("HISTORIC_INDUSTRY_PEER" in x
                             for x in result["s10"]["missing"]), 5)

    def test_missing_flow_is_never_imputed_zero(self):
        raw = _payload(drop={"cfo"})
        with _local_hash("INOD", raw):
            result = audit.audit_payload("INOD", raw)
        self.assertIsNone(result["s10"]["score"])
        self.assertTrue(any(x.startswith("2022:cfo:US_GAAP_TAG_ABSENT")
                            for x in result["s10"]["missing"]))

    def test_changed_official_bytes_rejected(self):
        raw = _payload()
        with _local_hash("INOD", raw):
            with self.assertRaisesRegex(ValueError, "SHA256_MISMATCH"):
                audit.audit_payload("INOD", raw.replace(b"903651", b"903652"))

    def test_wrong_cik_is_rejected_even_with_valid_sha(self):
        raw = _payload(bad_cik=True)
        with _local_hash("INOD", raw):
            with self.assertRaisesRegex(ValueError, "CIK_MISMATCH"):
                audit.audit_payload("INOD", raw)

    def test_wrong_fy2025_accession_is_missing(self):
        data = json.loads(_payload())
        data["facts"]["us-gaap"]["Assets"]["units"]["USD"][-1]["accn"] = "WRONG"
        raw = json.dumps(data, sort_keys=True).encode()
        with _local_hash("INOD", raw):
            result = audit.audit_payload("INOD", raw)
        self.assertEqual(result["s8"]["annual_fact_inventory"]["2025"]["assets"]["status"],
                         "EXACT_10K_FY_WINDOW_MISSING")

    def test_conflicting_exact_facts_are_rejected(self):
        raw = _payload(conflict=True)
        with _local_hash("INOD", raw):
            result = audit.audit_payload("INOD", raw)
        self.assertEqual(result["s8"]["annual_fact_inventory"]["2025"]["assets"]["status"],
                         "AMBIGUOUS_MULTIPLE_RECORDS")

    def test_nonexistent_historical_year_is_not_interpolated(self):
        data = json.loads(_payload())
        records = data["facts"]["us-gaap"]["Assets"]["units"]["USD"]
        data["facts"]["us-gaap"]["Assets"]["units"]["USD"] = [
            r for r in records if r["end"] != "2022-12-31"
        ]
        raw = json.dumps(data, sort_keys=True).encode()
        with _local_hash("INOD", raw):
            result = audit.audit_payload("INOD", raw)
        self.assertIsNone(result["fiscal_ends"][2022])
        self.assertTrue(any(x.startswith("2022:assets:FISCAL_YEAR_END_NOT_EVIDENCED")
                            for x in result["s10"]["missing"]))

    def test_peng_historical_august_year_end(self):
        gaap = {"Assets": {"units": {"USD": [
            _row(year, end=f"{year}-08-{day}")
            for year, day in ((2021, 27), (2022, 26), (2023, 25), (2024, 30))
        ]}}}
        ends = audit.fiscal_ends(gaap, "2025-08-29")
        self.assertEqual(ends[2024], "2024-08-30")
        self.assertEqual(ends[2023], "2023-08-25")

    def test_existing_bulk_zip_reads_only_five_named_members(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "companyfacts.zip"
            raws = {}
            originals = dict(audit.TARGETS)
            fake_targets = {}
            for ticker, spec in originals.items():
                raw = _payload()
                if ticker != "INOD":
                    data = json.loads(raw)
                    data["cik"] = int(spec["cik"])
                    raw = json.dumps(data, sort_keys=True).encode()
                raws[ticker] = raw
                fake_targets[ticker] = dict(spec, sha256=sha256(raw).hexdigest())
            with zipfile.ZipFile(archive, "w") as zf:
                for ticker, spec in originals.items():
                    zf.writestr(f"CIK{spec['cik']}.json", raws[ticker])
                zf.writestr("DO_NOT_READ.json", b"invalid data")
            with patch.dict(audit.TARGETS, fake_targets):
                result = audit.audit_bulk(archive)
            self.assertEqual(len(result["stocks"]), 5)
            self.assertEqual(result["network_requests"], 0)
            self.assertEqual(result["new_scores"], 0)
            self.assertTrue(all(v["s10"]["score"] is None
                                for v in result["stocks"].values()))

    def test_missing_zip_and_unlisted_ticker(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "ZIP required"):
                audit.audit_bulk(Path(folder) / "not_here.zip")
        with self.assertRaisesRegex(ValueError, "Ticker not"):
            audit.audit_payload("UNKNOWN", b"{}")


if __name__ == "__main__":
    unittest.main()
