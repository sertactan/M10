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
