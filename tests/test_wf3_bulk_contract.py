from datetime import date

from core.features.wf3_bulk import WF3DateReport
from core.features.wf3_peer_policy import (
    POLICY_VERSION,
    expansion_stages,
    market_cap_bucket,
)


def test_wf3_policy_and_report_contract_are_stable() -> None:
    assert POLICY_VERSION == "WF3_PEER_POLICY_V1_2026-10-07"
    assert market_cap_bucket(300_000_000) == "SMALL"
    assert expansion_stages("SMALL")[-1].name == "E5_ROUTE_ONLY"

    report=WF3DateReport(
        as_of_date=date(2024,1,31),
        universe_count=100,
        base_feature_materialized=1000,
        routed=80,
        pit_classified=70,
        peer_observations=65,
        peer_stats_targets=50,
        destination_feature_writes=75,
        missing_route=20,
        missing_pit_classification=10,
        missing_peer_observation=5,
        model_input_errors=0,
    )
    assert report.universe_count == 100
    assert report.missing_pit_classification == 10
