from __future__ import annotations

import math
from dataclasses import asdict

from core.models.s16_contracts import S16Input, S16Result


def _clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return min(high, max(low, float(value)))


def _validate(data: S16Input) -> None:
    if data.as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    values = asdict(data)
    risk_keys = {
        "dilution_risk", "extension_risk", "data_risk",
        "liquidity_risk", "manipulation_risk",
    }
    ignored = {"security_id", "ticker", "as_of", "route"}
    for key, value in values.items():
        if key in ignored:
            continue
        x = float(value)
        if key in risk_keys:
            if not 0.0 <= x <= 1.0:
                raise ValueError(f"{key} must be in [0, 1]")
        elif not 0.0 <= x <= 100.0:
            raise ValueError(f"{key} must be in [0, 100]")


def _fuel(data: S16Input) -> float:
    return _clip(
        0.35 * data.float_scarcity
        + 0.27 * data.short_pressure
        + 0.18 * data.float_turnover
        + 0.12 * data.liquidity_elasticity
        + 0.08 * data.ownership_lock
    )


def _spark(data: S16Input) -> float:
    return _clip(
        0.32 * data.catalyst
        + 0.25 * data.volume_ignition
        + 0.18 * data.momentum_acceleration
        + 0.10 * data.social_velocity
        + 0.08 * data.news_velocity
        + 0.07 * data.regime_sympathy
    )


def _risk_penalty(data: S16Input) -> float:
    return 25.0 * (
        0.40 * data.dilution_risk
        + 0.20 * data.extension_risk
        + 0.15 * data.data_risk
        + 0.15 * data.liquidity_risk
        + 0.10 * data.manipulation_risk
    )


def _convergence_bonus(data: S16Input) -> float:
    n = sum((
        data.float_scarcity > 75.0,
        data.short_pressure > 70.0,
        data.catalyst > 75.0,
        data.volume_ignition > 75.0,
        data.momentum_acceleration > 70.0,
        data.social_velocity > 70.0,
    ))
    return min(10.0, 2.5 * max(0, n - 2))


def _status(armed: float, ignition: float) -> str:
    if ignition >= 90:
        return "EXTREME_IGNITION"
    if ignition >= 80:
        return "IGNITION"
    if ignition >= 75:
        return "IGNITION_WATCH"
    if armed >= 70:
        return "STRONG_ARMED"
    if armed >= 60:
        return "ARMED"
    if armed >= 50:
        return "WATCH"
    return "DORMANT"


class S16V02Model:
    """Frozen V0.2 baseline."""

    version = "S16_V0.2"

    def analyze(self, data: S16Input) -> S16Result:
        _validate(data)
        fuel = _fuel(data)
        spark = _spark(data)
        risk = _risk_penalty(data)
        convergence = _convergence_bonus(data)

        armed = _clip(
            0.45 * fuel
            + 0.15 * data.short_pressure
            + 0.12 * data.attention
            + 0.10 * data.compression
            + 0.08 * data.catalyst_proximity
            + 0.05 * data.theme
            + 0.05 * data.anomaly
            - risk
        )
        ignition = _clip(math.sqrt(fuel * spark) + convergence - risk)
        return S16Result(
            security_id=data.security_id,
            ticker=data.ticker,
            as_of=data.as_of,
            version=self.version,
            armed_score=armed,
            ignition_score=ignition,
            fuel_score=fuel,
            spark_score=spark,
            risk_penalty=risk,
            convergence_bonus=convergence,
            status=_status(armed, ignition),
            route=data.route,
            components={"FUEL": fuel, "SPARK": spark},
            flags={
                "SHORT_DOUBLE_COUNT_BASELINE": True,
                "EXTENDED": data.extension_risk >= 0.75,
            },
        )


class S16V03Model:
    """False-positive-resistant challenger.

    V0.3 removes explicit SHORT from ARMED, uses geometric readiness,
    independent-pillar gates, and extension/dilution caps.
    """

    version = "S16_V0.3_CHALLENGER"

    @staticmethod
    def _early_spark(data: S16Input) -> float:
        return _clip(
            0.25 * data.attention
            + 0.15 * data.compression
            + 0.25 * data.catalyst_proximity
            + 0.15 * data.theme
            + 0.20 * data.anomaly
        )

    def analyze(self, data: S16Input) -> S16Result:
        _validate(data)
        fuel = _fuel(data)
        spark = _spark(data)
        risk = _risk_penalty(data)
        convergence = _convergence_bonus(data)
        early_spark = self._early_spark(data)

        pillars = sum((
            fuel >= 60.0,
            data.attention >= 60.0,
            data.compression >= 60.0,
            data.catalyst_proximity >= 60.0,
            data.theme >= 60.0,
            data.anomaly >= 60.0,
        ))
        early_bonus = min(8.0, 2.0 * max(0, pillars - 2))
        armed = _clip(math.sqrt(fuel * early_spark) + early_bonus - risk)

        if fuel < 55.0 or early_spark < 55.0:
            armed = min(armed, 49.0)
        elif pillars < 3:
            armed = min(armed, 59.0)
        if data.extension_risk >= 0.60 and data.catalyst_proximity < 70.0:
            armed = min(armed, 59.0)
        if data.dilution_risk >= 0.80:
            armed = min(armed, 49.0)

        continuation = math.sqrt(
            data.volume_ignition * data.momentum_acceleration
        )
        ignition = _clip(
            0.72 * math.sqrt(fuel * spark)
            + 0.28 * continuation
            + convergence
            - risk
        )

        independent_driver = max(
            data.catalyst,
            data.social_velocity,
            data.short_pressure,
            data.regime_sympathy,
        )
        if not (
            data.volume_ignition >= 70.0
            and data.momentum_acceleration >= 60.0
            and independent_driver >= 60.0
        ):
            ignition = min(ignition, 74.0)
        if data.extension_risk >= 0.75 and data.catalyst < 85.0:
            ignition = min(ignition, 69.0)
        if data.dilution_risk >= 0.80:
            ignition = min(ignition, 74.0)

        return S16Result(
            security_id=data.security_id,
            ticker=data.ticker,
            as_of=data.as_of,
            version=self.version,
            armed_score=armed,
            ignition_score=ignition,
            fuel_score=fuel,
            spark_score=spark,
            risk_penalty=risk,
            convergence_bonus=convergence,
            status=_status(armed, ignition),
            route=data.route,
            components={
                "FUEL": fuel,
                "SPARK": spark,
                "EARLY_SPARK": early_spark,
                "EARLY_PILLARS": float(pillars),
                "CONTINUATION": continuation,
            },
            flags={
                "SHORT_DOUBLE_COUNT_BASELINE": False,
                "INDEPENDENT_IGNITION_DRIVER": independent_driver >= 60.0,
                "EXTENDED": data.extension_risk >= 0.75,
                "DILUTION_HEAVY": data.dilution_risk >= 0.80,
            },
        )


def _weighted_geometric(parts: tuple[tuple[float, float], ...]) -> float:
    """Weighted geometric mean on 0..100 factors.

    A floor of 1 avoids numerical collapse from an exact cross-sectional zero
    while still making weak pillars strongly suppress the result.
    """
    total_weight = sum(weight for _, weight in parts)
    if total_weight <= 0:
        raise ValueError("weighted geometric mean requires positive weights")
    return math.exp(
        sum(
            weight * math.log(max(1.0, _clip(value)))
            for value, weight in parts
        ) / total_weight
    )


def _status_v1(armed: float, ignition: float, ignition_gate: bool) -> str:
    if ignition_gate and ignition >= 90.0:
        return "EXTREME_IGNITION"
    if ignition_gate and ignition >= 80.0:
        return "IGNITION"
    if ignition_gate and ignition >= 70.0:
        return "IGNITION_WATCH"
    if armed >= 75.0:
        return "STRONG_ARMED"
    if armed >= 60.0:
        return "ARMED"
    if armed >= 50.0:
        return "WATCH"
    return "DORMANT"


class S16V1Model:
    """Canonical S16 V1.0 — Explosive 1-Week Discovery.

    V1.0 freezes the ranking/state formula. Future work may calibrate thresholds
    and 3x/5x/10x probability heads, but must not silently alter these weights.
    """

    version = "S16_V1.0_CANONICAL"

    @staticmethod
    def _fuel(data: S16Input) -> float:
        return _clip(
            0.26 * data.market_cap_scarcity
            + 0.30 * data.float_scarcity
            + 0.18 * data.short_pressure
            + 0.10 * data.float_turnover
            + 0.08 * data.liquidity_elasticity
            + 0.08 * data.ownership_lock
        )

    @staticmethod
    def _pre_ignition(data: S16Input) -> float:
        return _clip(
            0.20 * data.attention
            + 0.18 * data.compression
            + 0.22 * data.catalyst_proximity
            + 0.12 * data.theme
            + 0.18 * data.anomaly
            + 0.10 * data.regime_sympathy
        )

    @staticmethod
    def _spark(data: S16Input) -> float:
        return _clip(
            0.30 * data.catalyst
            + 0.22 * data.volume_ignition
            + 0.18 * data.momentum_acceleration
            + 0.10 * data.float_turnover
            + 0.08 * data.social_velocity
            + 0.05 * data.news_velocity
            + 0.07 * data.regime_sympathy
        )

    @staticmethod
    def _armed_risk(data: S16Input) -> float:
        return 22.0 * (
            0.35 * data.dilution_risk
            + 0.15 * data.extension_risk
            + 0.20 * data.data_risk
            + 0.15 * data.liquidity_risk
            + 0.15 * data.manipulation_risk
        )

    @staticmethod
    def _ignition_risk(data: S16Input) -> float:
        return 25.0 * (
            0.35 * data.dilution_risk
            + 0.25 * data.extension_risk
            + 0.15 * data.data_risk
            + 0.10 * data.liquidity_risk
            + 0.15 * data.manipulation_risk
        )

    def analyze(self, data: S16Input) -> S16Result:
        _validate(data)

        fuel = self._fuel(data)
        pre = self._pre_ignition(data)
        spark = self._spark(data)
        continuation = math.sqrt(
            data.volume_ignition * data.momentum_acceleration
        )

        armed_pillars = sum((
            fuel >= 65.0,
            data.attention >= 60.0,
            data.catalyst_proximity >= 60.0,
            max(data.compression, data.anomaly) >= 65.0,
            max(data.theme, data.regime_sympathy) >= 60.0,
        ))
        armed_bonus = min(8.0, 2.0 * max(0, armed_pillars - 2))
        armed_risk = self._armed_risk(data)
        armed_base = _weighted_geometric((
            (fuel, 0.55),
            (pre, 0.45),
        ))
        armed = _clip(armed_base + armed_bonus - armed_risk)

        # Fail-closed caps for early discovery.
        if fuel < 50.0 or pre < 50.0:
            armed = min(armed, 49.0)
        elif armed_pillars < 3:
            armed = min(armed, 59.0)
        if data.dilution_risk >= 0.80:
            armed = min(armed, 49.0)
        if data.data_risk >= 0.60:
            armed = min(armed, 59.0)
        if (
            data.extension_risk >= 0.65
            and data.catalyst_proximity < 70.0
        ):
            armed = min(armed, 59.0)

        ignition_driver = max(
            data.catalyst,
            data.social_velocity,
            data.news_velocity,
            data.short_pressure,
            data.regime_sympathy,
        )
        ignition_pillars = sum((
            fuel >= 60.0,
            data.catalyst >= 70.0,
            data.volume_ignition >= 75.0,
            data.momentum_acceleration >= 65.0,
            ignition_driver >= 65.0,
        ))
        ignition_bonus = min(
            10.0,
            2.5 * max(0, ignition_pillars - 2),
        )
        ignition_risk = self._ignition_risk(data)
        ignition_base = _weighted_geometric((
            (fuel, 0.30),
            (spark, 0.45),
            (continuation, 0.25),
        ))
        ignition = _clip(
            ignition_base + ignition_bonus - ignition_risk
        )

        ignition_gate = (
            data.volume_ignition >= 65.0
            and data.momentum_acceleration >= 55.0
            and ignition_driver >= 60.0
        )
        if not ignition_gate:
            ignition = min(ignition, 69.0)
        if (
            data.dilution_risk >= 0.80
            and data.catalyst < 90.0
        ):
            ignition = min(ignition, 69.0)
        if (
            data.extension_risk >= 0.80
            and data.catalyst < 85.0
        ):
            ignition = min(ignition, 64.0)
        if data.manipulation_risk >= 0.80:
            ignition = min(ignition, 59.0)
        if data.data_risk >= 0.60:
            ignition = min(ignition, 74.0)

        explosive = _clip(
            armed
            if not ignition_gate
            else 0.30 * armed + 0.70 * ignition
        )
        convergence = max(armed_bonus, ignition_bonus)

        return S16Result(
            security_id=data.security_id,
            ticker=data.ticker,
            as_of=data.as_of,
            version=self.version,
            armed_score=armed,
            ignition_score=ignition,
            fuel_score=fuel,
            spark_score=spark,
            risk_penalty=ignition_risk,
            convergence_bonus=convergence,
            status=_status_v1(armed, ignition, ignition_gate),
            route=data.route,
            explosive_score=explosive,
            components={
                "FUEL": fuel,
                "PRE_IGNITION": pre,
                "SPARK": spark,
                "CONTINUATION": continuation,
                "ARMED_BASE": armed_base,
                "IGNITION_BASE": ignition_base,
                "ARMED_RISK": armed_risk,
                "IGNITION_RISK": ignition_risk,
                "ARMED_CONVERGENCE": armed_bonus,
                "IGNITION_CONVERGENCE": ignition_bonus,
                "ARMED_PILLARS": float(armed_pillars),
                "IGNITION_PILLARS": float(ignition_pillars),
                "IGNITION_DRIVER": ignition_driver,
                "EXPLOSIVE_SCORE": explosive,
            },
            flags={
                "CANONICAL_V1": True,
                "IGNITION_GATE": ignition_gate,
                "EXTENDED": data.extension_risk >= 0.80,
                "DILUTION_HEAVY": data.dilution_risk >= 0.80,
                "DATA_RISK_HIGH": data.data_risk >= 0.60,
                "MANIPULATION_HIGH": data.manipulation_risk >= 0.80,
            },
        )
