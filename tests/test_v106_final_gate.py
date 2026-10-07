import json
from pathlib import Path

import pytest

from scripts.check_v106_final_gate import FinalProductionBlocked, require_final_evidence


def _payload(status="COMPLETE_AND_ACTIVATED"):
    return {
        "schema_version":"WF9_EVIDENCE_V1",
        "mode":"FULL_EXECUTION",
        "code_identity":"a"*40,
        "generated_at":"2026-10-07T00:00:00+00:00",
        "report":{
            "status":status,
            "preflight":{
                "requested_snapshot_dates":144,
                "existing_snapshot_dates":144,
                "exact_pit_dates":144,
                "any_adjusted_price_dates":144,
                "total_universe_observations":1000,
                "total_price_covered":1000,
                "blockers":[],
                "warnings":[],
            },
            "wf5_run_id":"wf5",
            "wf6_run_id":"wf6",
            "wf7_run_id":"wf7",
            "hardening_id":"h",
            "manifest_id":"m",
            "activation_id":"a",
        },
    }


def test_final_gate_accepts_complete_evidence(tmp_path):
    path=tmp_path/"wf9.json"
    path.write_text(json.dumps(_payload()),encoding="utf-8")
    assert require_final_evidence(path)["report"]["status"]=="COMPLETE_AND_ACTIVATED"


def test_final_gate_rejects_noncomplete_evidence(tmp_path):
    path=tmp_path/"wf9.json"
    path.write_text(json.dumps(_payload("PREFLIGHT_BLOCKED")),encoding="utf-8")
    with pytest.raises(FinalProductionBlocked,match="COMPLETE_AND_ACTIVATED"):
        require_final_evidence(path)


def test_final_gate_rejects_missing_snapshot_coverage(tmp_path):
    payload=_payload()
    payload["report"]["preflight"]["exact_pit_dates"]=143
    path=tmp_path/"wf9.json"
    path.write_text(json.dumps(payload),encoding="utf-8")
    with pytest.raises(FinalProductionBlocked,match="144 exact PIT"):
        require_final_evidence(path)
