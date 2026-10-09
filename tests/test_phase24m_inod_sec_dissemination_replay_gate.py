import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.phase24m_inod_sec_dissemination_replay_gate import audit


def fixtures(root: Path):
    k=root/"phase24k.json"
    l=root/"phase24l.json"
    pinned=[
        ("0001410578-24-000611","2024-05-08","2024-05-07T21:48:33+00:00"),
        ("0001410578-24-001246","2024-08-09","2024-08-08T22:00:33+00:00"),
        ("0001410578-25-001113","2025-05-09","2025-05-08T21:49:06+00:00"),
    ]
    records=[{
        "accession":a, "form":"10-Q",
        "filing_date":d, "accepted_utc":ts,
        "source_chronology":"AFTER_HOURS_OR_FORM_RULE_REQUIRES_REVIEW",
        "issues":["AFTER_HOURS_SEC_FILING_DATE_RULE_NOT_INDEPENDENTLY_VERIFIED"],
        "PIT_certified":False,
    } for a,d,ts in pinned]
    records += [{
        "accession":f"0001410578-24-{1000+i:06d}",
        "form":"10-Q" if i<2 else "10-K",
        "filing_date":"2024-11-07", "accepted_utc":"2024-11-07T18:01:00+00:00",
        "source_chronology":"NORMAL_CONSIDERED",
        "issues":[],
        "PIT_certified":False,
    } for i in range(4)]
    k.write_text(json.dumps({
        "schema":"MERIDYEN_PHASE24K_INOD_TARGET_SEC_PIT_AVAILABILITY_EVIDENCE_V1",
        "status":"INOD_2024_2025_FINANCIAL_PIT_TIMESTAMP_CANDIDATE_AUDIT_ONLY",
        "target_window":{"start":"2024-01-01","end":"2025-09-30"},
        "eligible_for_canonical_PIT_promotion":False,"database_modified":False,
        "counts":{"accessions":7},
        "accessions":records,
    }))
    l.write_text(json.dumps({
        "schema":"MERIDYEN_PHASE24L_INOD_SEC_PRIMARY_FILING_DATE_REVIEW_V1",
        "status":"THREE_INOD_SEC_10Q_FILING_DATES_PRIMARY_SOURCE_CROSSCHECKED_NO_PIT",
        "SEC_public_dissemination_lookahead_gate":"BLOCKED_UNKNOWN",
        "public_dissemination_timestamps_verified":0,
        "canonical_PIT_certified":False,
        "database_modified":False,
        "offline_crosschecked_10Q_count":3,
        "records":[{
            "accession":a, "form":"10-Q",
            "official_filing_date_and_acceptance_match_pinned_index":True,
            "public_dissemination_time_verified":False,"PIT_certified":False,
            "SEC_official_filing_date_unchanged":d,
            "SEC_accepted_UTC_unchanged":ts,
        } for a,d,ts in pinned],
    }))
    return k,l


class TestPhase24mSecDisseminationGate(unittest.TestCase):
    def test_daily_replay_blocked_even_after_official_dates_crosschecked(self):
        with TemporaryDirectory() as td:
            k,l=fixtures(Path(td))
            result=audit(k,l)
            self.assertEqual(result["financial_accessions_scoped"],7)
            self.assertEqual(result["official_filing_date_primary_index_crosschecked"],3)
            self.assertEqual(result["SEC_public_dissemination_proven"],0)
            self.assertEqual(result["PIT_replay_eligible_count"],0)
            self.assertFalse(result["canonical_PIT_certified"])
            self.assertFalse(result["DB_modified"])
            rows={r["accession"]:r for r in result["records"]}
            self.assertEqual(
                rows["0001410578-24-000611"]["review_only_next_weekday_after_filing_date"],
                "2024-05-09")
            self.assertEqual(
                rows["0001410578-24-001246"]["review_only_next_weekday_after_filing_date"],
                "2024-08-12")
            self.assertEqual(
                rows["0001410578-25-001113"]["review_only_next_weekday_after_filing_date"],
                "2025-05-12")
            self.assertTrue(all(not r["daily_PIT_replay_use_permitted"]
                                for r in result["records"]))

    def test_prior_claimed_certification_is_rejected(self):
        with TemporaryDirectory() as td:
            k,l=fixtures(Path(td))
            doc=json.loads(k.read_text())
            doc["eligible_for_canonical_PIT_promotion"]=True
            k.write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError,"PIT_OR_PROVENANCE_GATES_NOT_CLOSED"):
                audit(k,l)

    def test_extra_quarantined_form_blocks(self):
        with TemporaryDirectory() as td:
            k,l=fixtures(Path(td))
            doc=json.loads(k.read_text())
            doc["accessions"][3]["source_chronology"]="AFTER_HOURS_OR_FORM_RULE_REQUIRES_REVIEW"
            k.write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError,"AFTER_HOURS_SEC_SOURCE_NOT_CROSSCHECKED"):
                audit(k,l)

    def test_active_lookahead_risk_blocks(self):
        with TemporaryDirectory() as td:
            k,l=fixtures(Path(td))
            doc=json.loads(k.read_text())
            doc["accessions"][0]["issues"].append(
                "LOOKAHEAD_RISK_AVAILABLE_BEFORE_SEC_ACCEPTANCE")
            k.write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError,"ACTIVE_LOOKAHEAD_RISK_BLOCKS_HANDOFF"):
                audit(k,l)


if __name__=="__main__":
    unittest.main()
