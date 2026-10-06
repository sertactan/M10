from __future__ import annotations

from enum import StrEnum


class Market(StrEnum):
    US = "US"


class Exchange(StrEnum):
    NASDAQ = "NASDAQ"
    NYSE = "NYSE"
    AMEX = "AMEX"
    OTC = "OTC"
    CBOE = "CBOE"
    JPX = "JPX"
    BIST = "BIST"
    HKEX = "HKEX"


class DataState(StrEnum):
    LIVE = "LIVE"
    CACHED = "CACHED"
    STALE = "STALE"
    ERROR = "ERROR"
    UNAVAILABLE = "UNAVAILABLE"


class AnalysisMode(StrEnum):
    HISTORICAL = "HISTORICAL"
    FORWARD = "FORWARD"


class ModelVersion(StrEnum):
    V12 = "S15.3_V1.2"
    V14 = "S15.3_V1.4"\n    V141 = "S15.3_V1.4.1"
