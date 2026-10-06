from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Mapping


class ScanMode(StrEnum):
    CURRENT = "CURRENT"
    HISTORICAL = "HISTORICAL"


@dataclass(frozen=True)
class ScanCandidate:
    security_id: str
    ticker: str
    exchange: str
    name: str = ""
    active: bool = True
    delisted_date: str | None = None


@dataclass(frozen=True)
class ScanRow:
    security_id: str
    ticker: str
    exchange: str
    as_of: datetime
    mode: ScanMode
    v12_score: float | None
    v12_status: str
    v12_route: str | None
    v12_destination: str | None
    v14_score: float | None
    v14_status: str
    v14_route: str | None
    v14_destination: str | None
    delisted: bool
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ScanProgress:
    completed: int
    total: int
    last_ticker: str | None = None


@dataclass(frozen=True)
class ScanSummary:
    mode: ScanMode
    as_of: datetime
    total: int
    nasdaq: int
    nyse: int
    amex: int
    delisted: int
    v12_scored: int = 0
    v14_scored: int = 0
