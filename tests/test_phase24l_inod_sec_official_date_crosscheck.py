import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.phase24l_inod_sec_official_date_crosscheck import (
    audit, PRIMARY_SEC_INDEX_EVIDENCE,
)


def setup_local(root: Path):
    source=root/"sec_submissions"
    source.mkdir()
    pinned=list(PRIMARY_SEC_INDEX_EVIDENCE)
    ids=[e["accession"] for e in pinned]
    forms=[e["form"] for e in pinned]
    accepted=[e["accepted_utc"] for e in pinned]
    dates=[e["official_filing_date"] for e in pinned]
    # Other historical SEC after-hours source-row differences remain
    # intentionally outside this 3-accession 2024-25 financial audit.
    for n in range(17):
        ids.append(f"0001410578-23-{100000+n:06d}")
        forms.append("8-K")
        accepted.append("2023-06-01T21:59:00+00:00")
        dates.append("2023-06-02")
    (source/"CIK0000903651.json").write_text(json.dumps({
        "cik":903651,
        "filings":{
            "recent":{
                "accessionNumber":ids,
                "form":forms,
                "acceptanceDateTime":accepted,
                "filingDate":dates,
            },"files":[],
        },
    }))
    report=root/"phase24k.json"
    report.write_text(json.dumps({
        "schema":"MERIDYEN_PHASE24K_INOD_TARGET_SEC_PIT_AVAILABILITY_EVIDENCE_V1",
        "status":"INOD_2024_2025_FINANCIAL_PIT_TIMESTAMP_CANDIDATE_AUDIT_ONLY",
        "eligible_for_canonical_PIT_promotion":False,
        "database_modified":False,
        "counts":{"accessions":7,"quarantined_source_chronology_accessions":3},
        "accessions":[
            {
                "accession":e["accession"],
                "form":e["form"],
                "filing_date":e["official_filing_date"],
                "accepted_utc":e["accepted_utc"],
                "source_chronology":"AFTER_HOURS_OR_FORM_RULE_REQUIRES_REVIEW",
                "matched_SEC_fact_rows_bounded":36,
                "issues":["AFTER_HOURS_SEC_FILING_DATE_RULE_NOT_INDEPENDENTLY_VERIFIED"],
                "PIT_certified":False,
            } for e in pinned
        ] + [
            {"source_chronology":"NORMAL_CONSIDERED","PIT_certified":False}
            for i in range(4)
        ],
    }))
    return report,source


class TestPhase24lOfficialSECIndexEvidence(unittest.TestCase):
    def test_three_pinned_primary_SEC_index_dates_match_without_pit_promotion(self):
        with TemporaryDirectory() as td:
            report,source=setup_local(Path(td))
            result=audit(report,source)
            self.assertEqual(result["offline_crosschecked_10Q_count"],3)
            self.assertEqual(result["unexplained_date_difference_in_these_three"],0)
            self.assertEqual(result["public_dissemination_timestamps_verified"],0)
            self.assertFalse(result["canonical_PIT_certified"])
            self.assertFalse(result["database_modified"])
            self.assertEqual(result["network_requests"],0)
            self.assertEqual([r["SEC_official_filing_date_unchanged"]
                              for r in result["records"]],
                             ["2024-05-08","2024-08-09","2025-05-09"])

    def test_original_SEC_date_mutation_blocks(self):
        with TemporaryDirectory() as td:
            report,source=setup_local(Path(td))
            f=source/"CIK0000903651.json"
            s=json.loads(f.read_text())
            s["filings"]["recent"]["filingDate"][0]="2024-05-09"
            f.write_text(json.dumps(s))
            with self.assertRaisesRegex(ValueError,"SEC_OFFICIAL_INDEX_FIELDS"):
                audit(report,source)

    def test_bad_phase24k_pit_claim_blocks(self):
        with TemporaryDirectory() as td:
            report,source=setup_local(Path(td))
            r=json.loads(report.read_text())
            r["eligible_for_canonical_PIT_promotion"]=True
            report.write_text(json.dumps(r))
            with self.assertRaisesRegex(ValueError,"UNTRUSTED_OR_INCOMPLETE"):
                audit(report,source)

    def test_missing_private_report_does_not_create_it(self):
        with TemporaryDirectory() as td:
            report,source=setup_local(Path(td))
            report.unlink()
            with self.assertRaisesRegex(ValueError,"LOCAL_PRIOR_PHASE24K"):
                audit(report,source)
            self.assertFalse(report.exists())


if __name__=="__main__":
    unittest.main()
