from __future__ import annotations

from collections.abc import Mapping


VECTOR_VERSION = "WF4_HISTORICAL_VECTOR_V1_2026-10-07"

BROAD_KEYS = (
    "DNA60","RB","U","A","C","M","G","V",
    "ETRQ","RER","CMAG","FCVX",
)

MAGNITUDE10_KEYS = (
    "DF10","MCH10","ETRQ","RER","CMAG","FCVX",
)

ROUTES = ("F10","I10","D10","B10","R10","Q10")


def _route_one_hot(primary_route: str | None) -> dict[str,float]:
    return {f"ROUTE_{route}": (100.0 if primary_route == route else 0.0) for route in ROUTES}


def broad_vector(
    components: Mapping[str,float|None],
    *,
    primary_route: str | None,
) -> dict[str,float|None]:
    return {
        **{key: components.get(key) for key in BROAD_KEYS},
        **_route_one_hot(primary_route),
    }


def magnitude10_vector(
    components: Mapping[str,float|None],
    *,
    primary_route: str | None,
) -> dict[str,float|None]:
    return {
        **{key: components.get(key) for key in MAGNITUDE10_KEYS},
        **_route_one_hot(primary_route),
    }
