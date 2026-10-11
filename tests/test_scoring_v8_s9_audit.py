"""V8 S9 evidence gates; synthetic inputs test rejection, not research scoring."""
import json
import tempfile
import unittest
from unittest.mock import patch
from hashlib import sha256
from pathlib import Path

from app.scoring_v8_s9_audit import PILOTS, SOURCE_PINS, audit_company
from app.scoring_v8_report import PRESERVED_SCORES, attach_v8_s9_audits, read_sealed_audit


def _submissions(ticker, bad=False):
    cfg = PILOTS[ticker]
    return json.dumps({"cik":int(cfg["cik"]),"filings":{"recent": {
        "accessionNumber":[cfg["current"], cfg["previous"]],
        "form":["10-Q" if bad else "10-K", "10-K"],
        "reportDate":[cfg["fy"], cfg["prior"]],
        "filingDate":["2026-03-01","2025-03-01"],
        "acceptanceDateTime":["2026-03-01T12:00:00Z","2025-03-01T12:00:00Z"],
        "primaryDocument":["document.htm","previous.htm"]}}}).encode()


def _baseline():
    stocks=[]
    for ticker in ("INOD","TMDX","CRMD","PENG","ETON"):
        scores=PRESERVED_SCORES[ticker]
        models=[{"model":"S"+str(i),"score":scores.get("S"+str(i)),
                 "status":"DATA_MISSING"} for i in range(1,17)]
        stocks.append({"ticker":ticker,"models":models,"full_model_count":len(scores)})
    return {"full_model_count":15,"stocks":stocks,"canonical_securities":0,"canonical_dates":0}


def _audits():
    result={}
    for ticker,count in (("INOD",8),("CRMD",7)):
        signal_names=("F_ROA","F_CFO","F_DELTA_ROA","F_ACCRUAL",
                      "F_DELTA_LEVERAGE","F_DELTA_LIQUIDITY",
                      "F_NO_COMMON_EQUITY_ISSUANCE","F_DELTA_GROSS_MARGIN",
                      "F_DELTA_ASSET_TURNOVER")
        signals={name:(None if name=="F_DELTA_LEVERAGE"
                            or (ticker=="CRMD" and name=="F_DELTA_GROSS_MARGIN")
                            else 0) for name in signal_names}
        result[ticker]={"score":None,"status":"DATA_MISSING","scope":"CURRENT_RESEARCH_ONLY",
            "canonical_accepted":False,"historical_pit_accepted":False,
            "signals_verified":count,"signals_partial":signals,
            "missing":["LONG_TERM_DEBT_COMPLETE_NONOVERLAPPING_MAPPING_NOT_VERIFIED"]}
    return result


class S9EvidenceGates(unittest.TestCase):
    def test_wrong_10k_form_rejected(self):
        facts=json.dumps({"cik":903651,"facts":{"us-gaap":{}}}).encode()
        with self.assertRaisesRegex(ValueError,"FISCAL_FORM_OR_PERIOD_MISMATCH"):
            audit_company("INOD",facts,_submissions("INOD",bad=True))

    def test_issuer_cik_change_rejected(self):
        facts=json.dumps({"cik":1410098,"facts":{"us-gaap":{}}}).encode()
        with self.assertRaisesRegex(ValueError,"COMPANYFACTS_CIK_MISMATCH"):
            audit_company("INOD",facts,_submissions("INOD"))

    def test_no_missing_as_zero(self):
        facts=json.dumps({"cik":903651,"facts":{"us-gaap":{}}}).encode()
        subs=_submissions("INOD")
        with patch.dict(SOURCE_PINS["INOD"],
                        {"companyfacts":sha256(facts).hexdigest(),
                         "submissions":sha256(subs).hexdigest()}):
            result=audit_company("INOD",facts,subs)
        self.assertIsNone(result["score"])
        self.assertIsNone(result["signals_partial"]["F_DELTA_LEVERAGE"])
        self.assertIsNone(result["signals_partial"]["F_NO_COMMON_EQUITY_ISSUANCE"])
        self.assertEqual(result["signals_verified"],0)
        self.assertFalse(result["canonical_accepted"])

    def test_wrong_known_good_companyfacts_pin_rejected(self):
        facts=json.dumps({"cik":903651,"facts":{"us-gaap":{}}}).encode()
        with self.assertRaisesRegex(ValueError,"COMPANYFACTS_PINNED_SHA256_CHANGED"):
            audit_company("INOD",facts,_submissions("INOD"))

    def test_fake_filing_body_rejected_even_when_fact_pin_matches(self):
        facts=json.dumps({"cik":903651,"facts":{"us-gaap":{}}}).encode()
        subs=_submissions("INOD")
        with patch.dict(SOURCE_PINS["INOD"],
                        {"companyfacts":sha256(facts).hexdigest(),
                         "submissions":sha256(subs).hexdigest()}):
            with self.assertRaisesRegex(ValueError,"OFFICIAL_FILING_BODY_SOURCE_IDENTITY_OR_SHA_CHANGED"):
                audit_company("INOD",facts,subs,filing_body=b"NOT AN OFFICIAL FILING")

    def test_v7_fifteen_scores_preserved_with_partial_s9(self):
        report=attach_v8_s9_audits(_baseline(),_audits(),"a"*64)
        self.assertEqual(report["full_model_count"],15)
        self.assertEqual([next(m for m in s["models"] if m["model"]=="S9")["present"]
                          for s in report["stocks"] if s["ticker"] in ("INOD","CRMD")],[8,7])
        self.assertIsNone(next(m for m in report["stocks"][0]["models"] if m["model"]=="S9")["score"])
        self.assertEqual(report["v8"]["s16_c_normalized_pit_accepted"],0)

    def test_unsupported_score_promotion_rejected(self):
        candidate=_audits()
        candidate["INOD"]["score"]=55.55555
        with self.assertRaisesRegex(ValueError,"S9_V8_UNSUPPORTED_MODEL_PROMOTION"):
            attach_v8_s9_audits(_baseline(),candidate,"a"*64)

    def test_baseline_real_zero_must_remain_zero(self):
        base=_baseline()
        next(m for m in base["stocks"][0]["models"] if m["model"]=="S11")["score"]=None
        with self.assertRaisesRegex(ValueError,"V7_REAL_RESEARCH_SCORE_CHANGED"):
            attach_v8_s9_audits(base,_audits(),"a"*64)

    def test_receipt_tampering_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            receipt=Path(temp)/"report.json"
            receipt.write_text('{"hello": "world"}',encoding="utf-8")
            Path(str(receipt)+".sha256").write_text("a"*64,encoding="ascii")
            with self.assertRaisesRegex(ValueError,"SEAL_MISMATCH"):
                read_sealed_audit(receipt)

    def test_real_sec_v8_cached_receipt_if_present(self):
        source=Path("E:/M10/.scoring_v8_private/piotroski_audit/source_pinned.json")
        if not source.is_file():
            self.skipTest("Private official SEC receipt unavailable on CI")
        audits,_=read_sealed_audit(source)
        self.assertEqual(audits["INOD"]["signals_verified"],8)
        self.assertEqual(audits["CRMD"]["signals_verified"],7)
        self.assertIsNone(audits["CRMD"]["signals_partial"]["F_DELTA_GROSS_MARGIN"])
        self.assertEqual(audits["INOD"]["gross_margin_cost_reconciliation"]["2025"]["residual_USD"],"0")
        self.assertNotEqual(audits["CRMD"]["gross_margin_cost_reconciliation"]["2025"]["residual_USD"],"0")


if __name__ == "__main__": unittest.main()
