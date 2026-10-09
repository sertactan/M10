import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.phase25b_simfin_distinct_daily_depth_audit import PER_MONTH_KEYS
from scripts.phase25e_simfin_dated_source_anomalies import audit


def _fixture(root):
    source = root/"simfin.csv"
    lines=["Ticker,SimFinId,Date,Open,High,Low,Close,Adj. Close"]
    for m in PER_MONTH_KEYS:
        for ticker,sid in (("AAA","101"),("BBB","102")):
            day=m+"-03"
            raw=10.0
            adj=10.0
            if ticker=="AAA" and m=="2025-01":
                adj=5.0
            if ticker=="BBB" and m>="2025-01":
                raw=adj=20.0
            lines.append(f"{ticker},{sid},{day},{raw},{raw+2},{raw-1},{raw},{adj}")
    lines.append("AAA,101,2025-01-17,10,12,9,10,10")
    source.write_text("\n".join(lines)+"\n",encoding="utf-8")
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    queue=[
        {
            "SimFinId":"101","ticker":"AAA","priority":"P1_MULTI_ALERT",
            "qualified_source_rows":22,
            "intra_month_factor_5pct_months":1,
            "factor_5pct_month_boundary_events":1,
            "extreme_adj_month_boundary_moves":1,
            "present_day_CIK_candidate_NOT_verified":"0000000101",
        },
        {
            "SimFinId":"102","ticker":"BBB",
            "priority":"P3_EXTREME_ADJ_RETURN_ONLY",
            "qualified_source_rows":21,
            "intra_month_factor_5pct_months":0,
            "factor_5pct_month_boundary_events":0,
            "extreme_adj_month_boundary_moves":1,
            "present_day_CIK_candidate_NOT_verified":"0000000102",
        },
    ]
    expected={
        "source_price_SHA256":sha,
        "SimFinIds_reviewed":2,
        "unique_review_candidates":2,
        "metrics":{
            "intra_month_factor_months":1,
            "month_boundary_factor_events":1,
            "extreme_adjusted_boundary_events":2,
        },
    }
    report={
        "schema":"MERIDYEN_PHASE25D_CORPORATE_ACTION_RESEARCH_WORKLIST_V1",
        "status":"UNIQUE_SOURCE_FACTOR_AND_RETURN_ALERT_WORKLIST_RESEARCH_ONLY_NOT_CANONICAL",
        "source_price_SHA256":sha,
        "SimFinIds_reviewed":2,
        "canonical_backtest_eligible_securities":0,
        "metrics":expected["metrics"],
        "database_modified":False,
        "source_price_modified":False,
        "training_performed":False,
        "review_queue":queue,
    }
    p25d=root/"phase25d.json"
    p25d.write_text(json.dumps(report),encoding="utf-8")
    membership={m:{"AAA","BBB"} for m in PER_MONTH_KEYS}
    return source,p25d,expected,queue,membership


class TestPhase25eDatedSourceEvidence(unittest.TestCase):
    def test_event_dates_reconcile_without_independent_certification(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            source,d,expected,q,listing=_fixture(root)
            original=source.read_bytes()
            with (
                patch("scripts.phase25e_simfin_dated_source_anomalies.review_queue_analyze",
                      return_value=(expected,q)),
                patch("scripts.phase25e_simfin_dated_source_anomalies._monthly_pit",
                      return_value=listing),
            ):
                data=audit(source,root/"p25b.json",root/"p25c.json",d,root)
            self.assertEqual(data["candidate_SimFinIds"],2)
            self.assertEqual(data["priority_counts"]["P1_MULTI_ALERT"],1)
            self.assertEqual(data["priority_counts"]["P3_EXTREME_ADJ_RETURN_ONLY"],1)
            self.assertEqual(
                data["event_counts"]["SOURCE_FACTOR_WITHIN_MONTH_RANGE_5PCT"],1)
            self.assertEqual(
                data["event_counts"]["SOURCE_FACTOR_MONTH_BOUNDARY_5PCT"],1)
            self.assertEqual(
                data["event_counts"]["SOURCE_ADJ_CLOSE_MONTH_BOUNDARY_MOVE_50PCT"],2)
            self.assertEqual(len(data["source_only_event_observations"]),4)
            self.assertEqual(data["source_only_event_observations"][0]["ticker"],"AAA")
            self.assertEqual(data["split_verified"],0)
            self.assertEqual(data["canonical_backtest_eligible_securities"],0)
            self.assertEqual(source.read_bytes(),original)

    def test_modified_csv_sha_rejected(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            source,d,expected,q,listing=_fixture(root)
            source.write_text(source.read_text()+"JUNK,1,2025-01-04,1,1,1,1,1\n")
            with patch(
                "scripts.phase25e_simfin_dated_source_anomalies.review_queue_analyze",
                return_value=(expected,q),
            ):
                with self.assertRaisesRegex(ValueError,"SIMFIN_SOURCE_SHA256_MISMATCH"):
                    audit(source,root/"p25b.json",root/"p25c.json",d,root)

    def test_tampered_phase25d_queue_rejected(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            source,d,expected,q,listing=_fixture(root)
            report=json.loads(d.read_text())
            report["review_queue"][0]["qualified_source_rows"]=23
            d.write_text(json.dumps(report))
            with patch(
                "scripts.phase25e_simfin_dated_source_anomalies.review_queue_analyze",
                return_value=(expected,q),
            ):
                with self.assertRaisesRegex(
                    ValueError,"PHASE25D_REPORT_OR_QUEUE_PROVENANCE_MISMATCH"
                ):
                    audit(source,root/"p25b.json",root/"p25c.json",d,root)


if __name__=="__main__":
    unittest.main()
