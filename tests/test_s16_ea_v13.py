from core.models.s16_ea_v13 import (
    AlertSnapshot,
    NewsEventInputs,
    PremarketQuietInputs,
    ReactionPercentiles,
    RiskInputs,
    StructuralInputs,
    ZeroPmPressureInputs,
    arbitrate_v13,
    evaluate_confirmed_news,
    evaluate_immediate_news,
    evaluate_zero_pm,
    news_shock,
    should_emit_alert,
    state_from_score,
    vwap_wake_score,
)


STRUCTURAL = StructuralInputs(
    fuel=80,
    pre=70,
    compression=90,
    catalyst_proximity=65,
    attention=70,
    theme=60,
    regime_sympathy=65,
    short_pressure=60,
    canonical_ready=True,
)
LOW_RISK = RiskInputs(0, 0, 0, 0, 0)


def _news(**overrides):
    base = dict(
        materiality=90,
        credibility=90,
        novelty=80,
        immediacy=90,
        surprise=80,
        qualifying_primary_source=True,
        critical_source_conflict=False,
        published_et_minutes=9 * 60 + 30,
    )
    base.update(overrides)
    return NewsEventInputs(**base)


def test_news_shock_exact_weights_with_surprise():
    assert news_shock(_news(materiality=80, credibility=80, novelty=80, immediacy=80, surprise=80)) == 80


def test_news_shock_renormalizes_without_surprise():
    score = news_shock(_news(materiality=100, credibility=80, novelty=60, immediacy=40, surprise=None))
    assert score == 76.25


def test_immediate_news_prealert_is_capped_at_64():
    result = evaluate_immediate_news(STRUCTURAL, LOW_RISK, _news())
    assert result.gate_passed is True
    assert result.score == 64
    assert result.label == "NEWS-PREALERT"


def test_confirmed_news_can_reach_prime():
    result = evaluate_confirmed_news(
        STRUCTURAL,
        LOW_RISK,
        _news(materiality=95, credibility=95, novelty=90, immediacy=95, surprise=90),
        ReactionPercentiles(95, 90, 95, 90, "NEWS_REACTION_1M"),
    )
    assert result.gate_passed is True
    assert (result.score or 0) >= 85
    assert result.label == "NEWS-PRIME"


def test_data_risk_blocks_canonical_news_path():
    result = evaluate_confirmed_news(
        STRUCTURAL,
        RiskInputs(0, 0, 0.60, 0, 0),
        _news(materiality=95, credibility=95, novelty=90, immediacy=95, surprise=90),
        ReactionPercentiles(95, 90, 95, 90, "NEWS_REACTION_1M"),
    )
    assert result.state == "INCONCLUSIVE"
    assert result.score is None


def test_zero_pm_requires_observed_quiet_premarket_and_can_alert():
    result = evaluate_zero_pm(
        STRUCTURAL,
        LOW_RISK,
        PremarketQuietInputs(True, 1, 10, 10),
        ZeroPmPressureInputs(90, 90, 90, 90, 100, "ZERO_PM_1M", 9 * 60 + 31),
    )
    assert result.gate_passed is True
    assert (result.score or 0) >= 65
    assert result.label.startswith("ZERO-PM-")


def test_missing_premarket_cannot_be_called_quiet():
    result = evaluate_zero_pm(
        STRUCTURAL,
        LOW_RISK,
        PremarketQuietInputs(False, 0, 0, 0),
        ZeroPmPressureInputs(90, 90, 90, 90, 100, "ZERO_PM_1M", 9 * 60 + 31),
    )
    assert result.state == "INCONCLUSIVE"
    assert result.score is None


def test_vwap_wake_score_frozen_rubric():
    assert vwap_wake_score(0.01, False, False) == 100
    assert vwap_wake_score(-0.20, True, False) == 70
    assert vwap_wake_score(-0.70, False, True) == 40
    assert vwap_wake_score(-0.90, True, True) == 0


def test_arbitration_chooses_maximum_canonical_path():
    from core.models.s16_ea_v13 import PathResult

    result = arbitrate_v13(
        now_et_minutes=9 * 60 + 32,
        risks=LOW_RISK,
        opening_v12=PathResult("OPENING_FAST_V1.2", 68, "EA-ALERT", "OPENING-ALERT", True, True, 5),
        standard_v11=PathResult("STANDARD_V1.1", 66, "EA-ALERT", "EA-ALERT", True, True, 5),
        news=PathResult("NEWS_AT_OPEN", 82, "EA-HOT", "NEWS-HOT", True, True, 6),
        zero_pm=PathResult("ZERO_PM_BREAKOUT", 78, "EA-HOT", "ZERO-PM-HOT", True, True, 6),
    )
    assert result.score == 82
    assert result.winning_path == "NEWS_AT_OPEN"


def test_manipulation_cap_allows_temporary_69_primary_event_override():
    from core.models.s16_ea_v13 import PathResult

    base = PathResult("NEWS_AT_OPEN", 90, "EA-PRIME", "NEWS-PRIME", True, True, 7)
    before = arbitrate_v13(
        now_et_minutes=9 * 60 + 35,
        risks=RiskInputs(0, 0, 0, 0, 0.85),
        news=base,
        news_shock_score=95,
        news_reaction_confirmed=False,
        regulator_court_or_control_changing_primary_event=True,
    )
    assert before.score == 69
    after = arbitrate_v13(
        now_et_minutes=9 * 60 + 35,
        risks=RiskInputs(0, 0, 0, 0, 0.85),
        news=base,
        news_shock_score=95,
        news_reaction_confirmed=True,
        regulator_court_or_control_changing_primary_event=True,
    )
    assert after.score == 90


def test_extension_risk_caps_early_alert_paths_at_49():
    from core.models.s16_ea_v13 import PathResult

    result = arbitrate_v13(
        now_et_minutes=9 * 60 + 35,
        risks=RiskInputs(0, 0.80, 0, 0, 0),
        zero_pm=PathResult("ZERO_PM_BREAKOUT", 90, "EA-PRIME", "ZERO-PM-PRIME", True, True, 7),
    )
    assert result.score == 49
    assert state_from_score(result.score or 0) == "EA-SEED"


def test_alert_dedupe_follows_frozen_rules():
    previous = AlertSnapshot("EA-ALERT", 70, 1_000_000, "A")
    assert not should_emit_alert(previous, AlertSnapshot("EA-ALERT", 74, 1_100_000, "A"))
    assert should_emit_alert(previous, AlertSnapshot("EA-ALERT", 75, 1_100_000, "A"))
    assert should_emit_alert(previous, AlertSnapshot("EA-HOT", 76, 1_050_000, "A"))
    assert should_emit_alert(previous, AlertSnapshot("EA-ALERT", 71, 1_050_000, "B"))
