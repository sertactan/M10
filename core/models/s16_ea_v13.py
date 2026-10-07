from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal, Sequence

S16_EA_V13_MODEL_ID = "S16_EA_V1.3_CANONICAL_HYBRID_FASTPATH"

EaState = Literal[
    "QUIET", "EA-SEED", "EA-PREALERT", "EA-ALERT", "EA-HOT", "EA-PRIME", "INCONCLUSIVE"
]
EaPath = Literal["NEWS_AT_OPEN", "ZERO_PM_BREAKOUT", "OPENING_FAST_V1.2", "STANDARD_V1.1"]


@dataclass(frozen=True)
class StructuralInputs:
    fuel: float
    pre: float
    compression: float
    catalyst_proximity: float
    attention: float
    theme: float
    regime_sympathy: float
    short_pressure: float
    canonical_ready: bool


@dataclass(frozen=True)
class RiskInputs:
    dilution_risk: float
    extension_risk: float
    data_risk: float
    liquidity_risk: float
    manipulation_risk: float


@dataclass(frozen=True)
class NewsEventInputs:
    materiality: float
    credibility: float
    novelty: float
    immediacy: float
    surprise: float | None
    qualifying_primary_source: bool
    critical_source_conflict: bool
    published_et_minutes: int
    regulator_court_or_control_changing_primary_event: bool = False


@dataclass(frozen=True)
class ReactionPercentiles:
    volume_impulse: float
    positive_return: float
    close_location: float
    range_expansion: float
    provenance: Literal["NEWS_REACTION_1M", "NEWS_REACTION_5M_FALLBACK"]


@dataclass(frozen=True)
class PremarketQuietInputs:
    valid_premarket_observations: bool
    pm_return_abs_pct: float
    pm_pace_percentile: float
    pm_return_percentile: float


@dataclass(frozen=True)
class ZeroPmPressureInputs:
    volume_impulse: float
    positive_return: float
    range_expansion: float
    close_location: float
    vwap_score: float
    provenance: Literal["ZERO_PM_1M", "ZERO_PM_5M"]
    evaluation_et_minutes: int


@dataclass(frozen=True)
class PathResult:
    path: EaPath
    score: float | None
    state: EaState
    label: str
    gate_passed: bool
    canonical_ready: bool
    pillars: int
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class AggregateResult:
    score: float | None
    state: EaState
    winning_path: EaPath | None
    label: str
    considered_paths: tuple[EaPath, ...]
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class AlertSnapshot:
    state: EaState
    score: float
    timestamp_ms: int
    catalyst_id: str | None = None


def _clamp100(value: float) -> float:
    return min(100.0, max(0.0, float(value)))


def _assert_score(value: float, name: str) -> None:
    if not math.isfinite(float(value)) or not 0.0 <= float(value) <= 100.0:
        raise ValueError(f"{name} must be in 0..100")


def _state_rank(state: EaState) -> int:
    return {
        "INCONCLUSIVE": -1,
        "QUIET": 0,
        "EA-SEED": 1,
        "EA-PREALERT": 2,
        "EA-ALERT": 3,
        "EA-HOT": 4,
        "EA-PRIME": 5,
    }[state]


def state_from_score(score: float) -> EaState:
    if score < 45:
        return "QUIET"
    if score < 55:
        return "EA-SEED"
    if score < 65:
        return "EA-PREALERT"
    if score < 75:
        return "EA-ALERT"
    if score < 85:
        return "EA-HOT"
    return "EA-PRIME"


def _news_label(state: EaState) -> str:
    return {
        "EA-PREALERT": "NEWS-PREALERT",
        "EA-ALERT": "NEWS-ALERT",
        "EA-HOT": "NEWS-HOT",
        "EA-PRIME": "NEWS-PRIME",
        "INCONCLUSIVE": "NEWS-INCONCLUSIVE",
    }.get(state, state)


def _zero_pm_label(state: EaState) -> str:
    return {
        "EA-PREALERT": "ZERO-PM-PREALERT",
        "EA-ALERT": "ZERO-PM-ALERT",
        "EA-HOT": "ZERO-PM-HOT",
        "EA-PRIME": "ZERO-PM-PRIME",
        "INCONCLUSIVE": "ZERO-PM-INCONCLUSIVE",
    }.get(state, state)


def _geometric_mean(items: Sequence[tuple[float, float]]) -> float:
    return math.exp(sum(weight * math.log(max(float(value), 1.0)) for value, weight in items))


def _count_true(values: Sequence[bool]) -> int:
    return sum(bool(value) for value in values)


def _inconclusive(path: EaPath, label: str, reasons: list[str]) -> PathResult:
    return PathResult(
        path=path,
        score=None,
        state="INCONCLUSIVE",
        label=label,
        gate_passed=False,
        canonical_ready=False,
        pillars=0,
        reasons=tuple(reasons),
    )


def _apply_early_extension_cap(score: float, risks: RiskInputs) -> float:
    return min(score, 49.0) if risks.extension_risk >= 0.75 else score


def independent_early_driver(structural: StructuralInputs) -> float:
    return max(
        structural.catalyst_proximity,
        structural.attention,
        structural.short_pressure,
        structural.regime_sympathy,
    )


def news_shock(event: NewsEventInputs) -> float:
    for name in ("materiality", "credibility", "novelty", "immediacy"):
        _assert_score(getattr(event, name), name)
    if event.surprise is not None:
        _assert_score(event.surprise, "surprise")
        return _clamp100(
            0.30 * event.materiality
            + 0.20 * event.surprise
            + 0.20 * event.credibility
            + 0.15 * event.novelty
            + 0.15 * event.immediacy
        )
    denominator = 0.30 + 0.20 + 0.15 + 0.15
    return _clamp100(
        (
            0.30 * event.materiality
            + 0.20 * event.credibility
            + 0.15 * event.novelty
            + 0.15 * event.immediacy
        )
        / denominator
    )


def evaluate_immediate_news(
    structural: StructuralInputs,
    risks: RiskInputs,
    event: NewsEventInputs,
) -> PathResult:
    reasons: list[str] = []
    if not structural.canonical_ready:
        reasons.append("inherited structural inputs not canonical-ready")
    if event.published_et_minutes < 9 * 60 + 20 or event.published_et_minutes > 10 * 60:
        reasons.append("news event outside 09:20-10:00 ET eligibility window")
    if not event.qualifying_primary_source:
        reasons.append("qualifying primary source missing")
    if event.critical_source_conflict:
        reasons.append("critical unresolved source conflict")
    if risks.data_risk >= 0.60:
        reasons.append("DataRisk >= 0.60")
    if reasons:
        return _inconclusive("NEWS_AT_OPEN", "NEWS-INCONCLUSIVE", reasons)

    shock = news_shock(event)
    base = 0.30 * structural.fuel + 0.15 * structural.pre + 0.55 * shock
    risk_penalty = 16 * (
        0.25 * risks.dilution_risk
        + 0.20 * risks.extension_risk
        + 0.15 * risks.data_risk
        + 0.10 * risks.liquidity_risk
        + 0.30 * risks.manipulation_risk
    )
    score = min(_clamp100(base - risk_penalty), 64.0)
    gate = (
        shock >= 70
        and event.credibility >= 80
        and event.materiality >= 65
        and structural.fuel >= 45
        and risks.extension_risk < 0.60
        and risks.data_risk < 0.60
        and not event.critical_source_conflict
    )
    if not gate:
        score = min(score, 54.0)
    score = _apply_early_extension_cap(score, risks)
    return PathResult(
        path="NEWS_AT_OPEN",
        score=score,
        state=state_from_score(score),
        label="NEWS-PREALERT" if gate and score >= 55 else state_from_score(score),
        gate_passed=gate,
        canonical_ready=True,
        pillars=0,
    )


def news_reaction(inputs: ReactionPercentiles) -> float:
    for name in ("volume_impulse", "positive_return", "close_location", "range_expansion"):
        _assert_score(getattr(inputs, name), name)
    return _clamp100(
        0.40 * inputs.volume_impulse
        + 0.30 * inputs.positive_return
        + 0.15 * inputs.close_location
        + 0.15 * inputs.range_expansion
    )


def evaluate_confirmed_news(
    structural: StructuralInputs,
    risks: RiskInputs,
    event: NewsEventInputs,
    reaction_inputs: ReactionPercentiles,
) -> PathResult:
    reasons: list[str] = []
    if not structural.canonical_ready:
        reasons.append("inherited structural inputs not canonical-ready")
    if event.published_et_minutes < 9 * 60 + 20 or event.published_et_minutes > 10 * 60:
        reasons.append("news event outside 09:20-10:00 ET eligibility window")
    if not event.qualifying_primary_source:
        reasons.append("qualifying primary source missing")
    if event.critical_source_conflict:
        reasons.append("critical unresolved source conflict")
    if risks.data_risk >= 0.60:
        reasons.append("DataRisk >= 0.60")
    if reasons:
        return _inconclusive("NEWS_AT_OPEN", "NEWS-INCONCLUSIVE", reasons)

    shock = news_shock(event)
    reaction = news_reaction(reaction_inputs)
    base = _geometric_mean(
        ((structural.fuel, 0.25), (max(structural.pre, 1.0), 0.15), (shock, 0.40), (reaction, 0.20))
    )
    pillars = _count_true(
        (
            structural.fuel >= 50,
            shock >= 75,
            event.credibility >= 80,
            event.materiality >= 70,
            reaction >= 55,
            risks.extension_risk <= 0.50,
            risks.manipulation_risk < 0.80,
        )
    )
    bonus = min(10.0, 2.0 * max(0, pillars - 3))
    risk_penalty = 17 * (
        0.24 * risks.dilution_risk
        + 0.28 * risks.extension_risk
        + 0.14 * risks.data_risk
        + 0.09 * risks.liquidity_risk
        + 0.25 * risks.manipulation_risk
    )
    score = _clamp100(base + bonus - risk_penalty)
    gate = (
        shock >= 75
        and reaction >= 55
        and event.credibility >= 80
        and structural.fuel >= 50
        and risks.extension_risk < 0.60
        and pillars >= 4
    )
    if not gate:
        score = min(score, 64.0)
    score = _apply_early_extension_cap(score, risks)
    state = state_from_score(score)
    return PathResult(
        path="NEWS_AT_OPEN",
        score=score,
        state=state,
        label=_news_label(state),
        gate_passed=gate,
        canonical_ready=True,
        pillars=pillars,
    )


def quiet_premarket(
    structural: StructuralInputs,
    inputs: PremarketQuietInputs,
) -> tuple[bool, float | None, tuple[str, ...]]:
    if not inputs.valid_premarket_observations:
        return False, None, ("valid premarket price/volume observations missing",)
    _assert_score(inputs.pm_pace_percentile, "pm_pace_percentile")
    _assert_score(inputs.pm_return_percentile, "pm_return_percentile")
    if inputs.pm_return_abs_pct < 0:
        raise ValueError("pm_return_abs_pct must be >= 0")
    quiet = _clamp100(
        0.50 * (100 - inputs.pm_pace_percentile)
        + 0.30 * (100 - inputs.pm_return_percentile)
        + 0.20 * structural.compression
    )
    reasons: list[str] = []
    if quiet < 60:
        reasons.append("QUIET_PM < 60")
    if inputs.pm_return_abs_pct > 5:
        reasons.append("PM_ReturnAbs > 5%")
    return quiet >= 60 and inputs.pm_return_abs_pct <= 5, quiet, tuple(reasons)


def zero_pm_pressure(inputs: ZeroPmPressureInputs) -> float:
    for name in ("volume_impulse", "positive_return", "range_expansion", "close_location", "vwap_score"):
        _assert_score(getattr(inputs, name), name)
    return _clamp100(
        0.35 * inputs.volume_impulse
        + 0.25 * inputs.positive_return
        + 0.15 * inputs.range_expansion
        + 0.15 * inputs.close_location
        + 0.10 * inputs.vwap_score
    )


def vwap_wake_score(close_vs_vwap_pct: float, positive_return: bool, improving: bool) -> int:
    if close_vs_vwap_pct > 0:
        return 100
    if close_vs_vwap_pct >= -0.25 and positive_return:
        return 70
    if close_vs_vwap_pct >= -0.75 and improving:
        return 40
    return 0


def evaluate_zero_pm(
    structural: StructuralInputs,
    risks: RiskInputs,
    quiet_inputs: PremarketQuietInputs,
    pressure_inputs: ZeroPmPressureInputs,
) -> PathResult:
    reasons: list[str] = []
    if not structural.canonical_ready:
        reasons.append("inherited structural inputs not canonical-ready")
    if not 9 * 60 + 31 <= pressure_inputs.evaluation_et_minutes <= 9 * 60 + 44:
        reasons.append("Zero-PM evaluation outside 09:31-09:44 ET fast-path window")
    if pressure_inputs.provenance == "ZERO_PM_5M" and pressure_inputs.evaluation_et_minutes < 9 * 60 + 35:
        reasons.append("5-minute Zero-PM confirmation cannot be used before 09:35 ET")
    if risks.data_risk >= 0.60:
        reasons.append("DataRisk >= 0.60")
    if reasons:
        return _inconclusive("ZERO_PM_BREAKOUT", "ZERO-PM-INCONCLUSIVE", reasons)

    qualified, quiet, quiet_reasons = quiet_premarket(structural, quiet_inputs)
    if quiet is None:
        return _inconclusive("ZERO_PM_BREAKOUT", "ZERO-PM-INCONCLUSIVE", list(quiet_reasons))
    pressure = zero_pm_pressure(pressure_inputs)
    driver = max(
        structural.short_pressure,
        structural.theme,
        structural.regime_sympathy,
        structural.attention,
        structural.catalyst_proximity,
    )
    base = _geometric_mean(
        ((structural.fuel, 0.38), (max(structural.pre, 1.0), 0.22), (quiet, 0.15), (pressure, 0.25))
    )
    pillars = _count_true(
        (
            structural.fuel >= 55,
            structural.pre >= 45,
            quiet >= 60,
            pressure >= 55,
            pressure_inputs.volume_impulse >= 60,
            risks.extension_risk <= 0.45,
            driver >= 50,
        )
    )
    bonus = min(10.0, 2.0 * max(0, pillars - 3))
    risk_penalty = 18 * (
        0.22 * risks.dilution_risk
        + 0.40 * risks.extension_risk
        + 0.14 * risks.data_risk
        + 0.08 * risks.liquidity_risk
        + 0.16 * risks.manipulation_risk
    )
    score = _clamp100(base + bonus - risk_penalty)
    prealert_gate = (
        qualified
        and structural.fuel >= 50
        and structural.pre >= 45
        and pressure >= 50
        and risks.extension_risk < 0.55
        and pillars >= 4
    )
    alert_gate = (
        structural.fuel >= 55
        and structural.pre >= 48
        and quiet >= 60
        and pressure >= 60
        and pressure_inputs.volume_impulse >= 65
        and risks.extension_risk < 0.58
        and pillars >= 5
    )
    if not prealert_gate:
        score = min(score, 54.0)
    elif not alert_gate:
        score = min(score, 64.0)
    score = _apply_early_extension_cap(score, risks)
    state = state_from_score(score)
    return PathResult(
        path="ZERO_PM_BREAKOUT",
        score=score,
        state=state,
        label=_zero_pm_label(state),
        gate_passed=alert_gate,
        canonical_ready=True,
        pillars=pillars,
        reasons=quiet_reasons,
    )


def arbitrate_v13(
    *,
    now_et_minutes: int,
    risks: RiskInputs,
    standard_v11: PathResult | None = None,
    opening_v12: PathResult | None = None,
    news: PathResult | None = None,
    zero_pm: PathResult | None = None,
    news_shock_score: float | None = None,
    news_reaction_confirmed: bool = False,
    regulator_court_or_control_changing_primary_event: bool = False,
) -> AggregateResult:
    candidates: list[PathResult] = []
    if 9 * 60 + 20 <= now_et_minutes < 9 * 60 + 30:
        active = (opening_v12, news)
    elif 9 * 60 + 30 <= now_et_minutes < 9 * 60 + 45:
        active = (opening_v12, standard_v11, news, zero_pm)
    elif 9 * 60 + 45 <= now_et_minutes <= 10 * 60:
        active = (standard_v11, news)
    elif now_et_minutes > 10 * 60:
        active = (standard_v11,)
    else:
        active = ()
    candidates.extend(p for p in active if p is not None and p.canonical_ready)

    numeric = [p for p in candidates if p.score is not None]
    if not numeric:
        return AggregateResult(
            score=None,
            state="INCONCLUSIVE",
            winning_path=None,
            label="S16-EA-E V1.3",
            considered_paths=tuple(p.path for p in candidates),
            reasons=("no canonical-ready numeric path in active arbitration window",),
        )

    winner = max(numeric, key=lambda p: float(p.score))
    score = float(winner.score)
    reasons: list[str] = []
    if risks.extension_risk >= 0.75:
        score = min(score, 49.0)
        reasons.append("ExtensionRisk >= 0.75 aggregate early-alert cap")
    if risks.manipulation_risk >= 0.80:
        override = (
            regulator_court_or_control_changing_primary_event
            and (news_shock_score or 0.0) >= 90
        )
        if override and not news_reaction_confirmed:
            score = min(score, 69.0)
            reasons.append("ManipulationRisk >= 0.80 temporary primary-event cap 69 until reaction confirmation")
        elif not override:
            score = min(score, 54.0)
            reasons.append("ManipulationRisk >= 0.80 aggregate cap 54")

    state = state_from_score(score)
    if winner.path == "NEWS_AT_OPEN":
        label = _news_label(state)
    elif winner.path == "ZERO_PM_BREAKOUT":
        label = _zero_pm_label(state)
    elif score == winner.score:
        label = winner.label
    else:
        label = state
    return AggregateResult(
        score=score,
        state=state,
        winning_path=winner.path,
        label=label,
        considered_paths=tuple(p.path for p in candidates),
        reasons=tuple(reasons),
    )


def should_emit_alert(previous: AlertSnapshot | None, next_: AlertSnapshot) -> bool:
    if next_.state in {"INCONCLUSIVE", "QUIET", "EA-SEED"}:
        return False
    if previous is None:
        return True
    if _state_rank(next_.state) > _state_rank(previous.state):
        return True
    if _state_rank(next_.state) < _state_rank(previous.state):
        return False
    if next_.catalyst_id and next_.catalyst_id != previous.catalyst_id:
        return True
    if next_.timestamp_ms - previous.timestamp_ms >= 15 * 60_000:
        return True
    return next_.score - previous.score >= 5


def lead_time_minutes(early_timestamp_ms: int, ignition_timestamp_ms: int) -> float:
    return (ignition_timestamp_ms - early_timestamp_ms) / 60_000
