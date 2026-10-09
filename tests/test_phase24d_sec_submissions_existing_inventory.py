import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.phase24d_sec_submissions_existing_inventory import inventory


CIK = "0000000123"
ARCHIVE = f"CIK{CIK}-submissions-001.json"
ROOT = f"CIK{CIK}.json"


def _filings():
    return {
        "accessionNumber":["0000000123-24-000001"],
        "acceptanceDateTime":["2024-04-18T13:00:00Z"],
        "form":["10-Q"],
        "filingDate":["2024-04-18"],
    }


def _set_up(p, manifest=False, missing_archive=False):
    p.mkdir()
    roots={"cik":123,"filings":{"recent":_filings(),
                                "files":[{"name":ARCHIVE}]}}
    source=json.dumps(roots).encode()
    (p/ROOT).write_bytes(source)
    archived=json.dumps(_filings()).encode()
    if not missing_archive:
        (p/ARCHIVE).write_bytes(archived)
    if manifest:
        (p/"sec_sources_manifest.json").write_text(json.dumps({
            "schema":"MERIDYEN_PHASE14_SEC_SUBMISSIONS_COLLECT_V1",
            "documents":{
                ROOT:{"sha256":hashlib.sha256(source).hexdigest(),
                      "origin":"FETCHED_FROM_PINNED_SEC_HTTPS_ENDPOINT"},
                ARCHIVE:{"sha256":hashlib.sha256(archived).hexdigest(),
                         "origin":"FETCHED_FROM_PINNED_SEC_HTTPS_ENDPOINT"},
            }
        }))


def _prior(path):
    path.write_text(json.dumps({
        "schema":"MERIDYEN_PHASE24_SIMFIN_SEC_CIK_CANDIDATES_V1",
        "status":"SIMFIN_ID_TO_CIK_CANDIDATES_ONLY_ZERO_HISTORICAL_ID_CERTIFICATIONS",
        "reconciled_phase19_20_21_23":True,
        "historical_identity_certifications":0,
        "simfin_ids_in_window":2,
        "candidate_records":[
            {"SimFinId":"101","candidate_CIKs_NOT_verified":[CIK]},
            {"SimFinId":"102","candidate_CIKs_NOT_verified":["0000000456"]},
        ],
    }))


class TestPhase24dExistingSECSubmissions(unittest.TestCase):
    def test_existing_root_and_archive_reported_but_not_pit(self):
        with TemporaryDirectory() as folder:
            temp=Path(folder)
            old=temp/"phase24.json"
            _prior(old)
            sec=temp/"sec"
            _set_up(sec,manifest=True)
            r=inventory(old,[sec])
            self.assertEqual(r["phase24_CIK_candidates"],2)
            self.assertEqual(r["candidate_CIKs_with_locally_schema_valid_root"],1)
            self.assertEqual(r["candidate_CIKs_with_all_root_listed_archives_schema_valid"],1)
            self.assertEqual(r["candidate_CIKs_without_local_schema_valid_root_IN_SCOPED_DIRS"],1)
            self.assertEqual(r["source_file_counts"]["candidate_archive_files_schema_valid"],1)
            self.assertFalse(r["sec_provenance_independently_verified"])
            self.assertEqual(r["historical_share_class_CIK_certifications"],0)
            self.assertFalse(r["database_modified"])
            self.assertEqual(r["network_requests"],0)

    def test_missing_archived_doc_not_inferred_from_root(self):
        with TemporaryDirectory() as folder:
            temp=Path(folder)
            old=temp/"phase24.json"
            _prior(old)
            sec=temp/"sec"
            _set_up(sec,missing_archive=True)
            r=inventory(old,[sec])
            self.assertEqual(r["candidate_CIKs_with_locally_schema_valid_root"],1)
            self.assertEqual(r["candidate_CIKs_with_all_root_listed_archives_schema_valid"],0)
            self.assertEqual(r["source_file_counts"]["candidate_archive_status_MISSING_UNSAFE_OR_OVERSIZED"],1)

    def test_hash_mismatch_is_not_accepted(self):
        with TemporaryDirectory() as folder:
            temp=Path(folder)
            old=temp/"phase24.json"
            _prior(old)
            sec=temp/"sec"
            _set_up(sec,manifest=True)
            (sec/ROOT).write_bytes(b"fake json")
            r=inventory(old,[sec])
            self.assertEqual(r["candidate_CIKs_with_locally_schema_valid_root"],0)
            self.assertEqual(r["source_file_counts"]["candidate_root_status_MANIFEST_SHA_MISMATCH"],1)

    def test_missing_dirs_are_reported_not_created(self):
        with TemporaryDirectory() as folder:
            temp=Path(folder)
            old=temp/"phase24.json"
            _prior(old)
            missing=temp/"not_downloaded"
            r=inventory(old,[missing])
            self.assertEqual(r["scoped_directories"][0]["status"],"NOT_FOUND_OR_NOT_DIRECTORY")
            self.assertFalse(r["all_possible_computer_directories_searched"])
            self.assertFalse(missing.exists())

    def test_untrusted_prior_historical_claim_rejected(self):
        with TemporaryDirectory() as folder:
            temp=Path(folder)
            old=temp/"phase24.json"
            _prior(old)
            a=json.loads(old.read_text())
            a["historical_identity_certifications"]=1
            old.write_text(json.dumps(a))
            with self.assertRaisesRegex(ValueError,"PHASE24_REPORT_NOT_VERIFIED"):
                inventory(old, [temp])


if __name__=="__main__":
    unittest.main()
