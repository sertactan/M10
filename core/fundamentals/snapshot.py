from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.fundamentals.metrics import FLOW_METRICS
from data.repositories.fundamental_repository import FundamentalRepository


@dataclass(frozen=True)
class FundamentalSnapshot:
    security_id: str
    as_of: datetime
    facts: dict[str, dict]
    ttm: dict[str, float]


class FundamentalSnapshotService:
    def __init__(self, repository: FundamentalRepository) -> None:
        self.repository = repository

    def snapshot_as_of(self, security_id: str, as_of: datetime) -> FundamentalSnapshot:
        facts = self.repository.canonical_facts_as_of(security_id, as_of)
        latest: dict[str, dict] = {}
        by_metric: dict[str, list[dict]] = {}
        for fact in facts:
            by_metric.setdefault(fact["metric_name"], []).append(fact)
            current = latest.get(fact["metric_name"])
            if current is None or fact["period_end"] > current["period_end"]:
                latest[fact["metric_name"]] = fact

        ttm: dict[str, float] = {}
        for metric in FLOW_METRICS:
            quarters = [
                x for x in by_metric.get(metric, [])
                if x["period_kind"] == "QUARTER"
            ]
            # Only exact, separately reported quarter-duration facts are summed.
            # No silent Q4 derivation from annual minus 9M is performed.
            quarters = sorted(quarters, key=lambda x: x["period_end"], reverse=True)
            unique: list[dict] = []
            seen = set()
            for row in quarters:
                if row["period_end"] in seen:
                    continue
                seen.add(row["period_end"])
                unique.append(row)
                if len(unique) == 4:
                    break
            if len(unique) == 4:
                ttm[metric] = sum(float(x["value"]) for x in unique)

        if "OPERATING_CASH_FLOW" in ttm and "CAPEX" in ttm:
            ttm["FREE_CASH_FLOW"] = ttm["OPERATING_CASH_FLOW"] - abs(ttm["CAPEX"])

        return FundamentalSnapshot(
            security_id=security_id,
            as_of=as_of,
            facts=latest,
            ttm=ttm,
        )
