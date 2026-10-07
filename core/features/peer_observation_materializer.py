from __future__ import annotations

from datetime import datetime, timezone

from data.database.sqlite_store import SQLiteStore
from data.repositories.destination_peer_repository import DestinationPeerRepository
from data.repositories.model_feature_repository import ModelFeatureRepository
from data.repositories.security_classification_repository import SecurityClassificationRepository
from core.features.wf3_peer_policy import (
    POLICY_VERSION,
    market_cap_bucket as classify_market_cap_bucket,
    profitability_state as classify_profitability_state,
)


RAW_KEYS = {
    "RAW_CURRENT_MARKET_CAP",
    "RAW_EV_TO_SALES_TTM",
    "RAW_EV_TO_EBITDA_TTM",
    "RAW_PRICE_TO_FCF_TTM",
    "RAW_TTM_REVENUE",
    "RAW_TTM_OPERATING_INCOME",
    "RAW_TTM_FCF",
}


class DestinationPeerObservationMaterializer:
    """Build one peer observation from canonical PIT feature rows.

    market_cap_bucket and profitability_state are explicit required inputs
    because S15.3 did not freeze their category definitions. They are never
    inferred from unrelated legacy classification rules.
    """

    VERSION = "wf3-peer-observation-v2-policy-v1"

    def __init__(self, store: SQLiteStore, features: ModelFeatureRepository, peers: DestinationPeerRepository) -> None:
        self.store = store
        self.features = features
        self.peers = peers
        self.classifications = SecurityClassificationRepository(store)

    def materialize(
        self,
        *,
        security_id: str,
        route: str,
        as_of: datetime,
        market_cap_bucket: str | None = None,
        profitability_state: str | None = None,
    ) -> str | None:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        security = self.store.connection.execute(
            "SELECT 1 FROM security_master WHERE security_id=?",
            (security_id,),
        ).fetchone()
        if security is None:
            raise ValueError(f"unknown security_id: {security_id}")

        classification = self.classifications.as_of(security_id, as_of)
        if classification is None:
            return None
        sector = str(classification["sector"]).strip()
        industry = str(classification["industry"]).strip()

        rows = self.features.load_as_of(security_id, as_of)
        def value(key: str) -> float | None:
            row = rows.get(key)
            if row is None or row.get("value") is None:
                return None
            return float(row["value"])

        market_cap = value("RAW_CURRENT_MARKET_CAP")
        if market_cap is None or market_cap <= 0:
            return None

        bucket = market_cap_bucket or classify_market_cap_bucket(market_cap)
        state = profitability_state or classify_profitability_state(
            ttm_revenue=value("RAW_TTM_REVENUE"),
            ttm_operating_income=value("RAW_TTM_OPERATING_INCOME"),
            ttm_fcf=value("RAW_TTM_FCF"),
        )
        if not bucket or not state:
            return None

        used = [rows[key] for key in RAW_KEYS if key in rows and rows[key].get("value") is not None]
        latest_available = max(
            (datetime.fromisoformat(str(row["available_at"])) for row in used),
            default=as_of.astimezone(timezone.utc),
        )
        return self.peers.save(
            security_id=security_id,
            as_of_month=as_of.strftime("%Y-%m"),
            route=route,
            sector=sector,
            industry=industry,
            market_cap_bucket=bucket,
            profitability_state=state,
            market_cap=market_cap,
            sales_multiple=value("RAW_EV_TO_SALES_TTM"),
            ebitda_multiple=value("RAW_EV_TO_EBITDA_TTM"),
            fcf_multiple=value("RAW_PRICE_TO_FCF_TTM"),
            feature_as_of=as_of,
            available_at=latest_available,
            source_ref=f"CANONICAL_FEATURES:{security_id}:{as_of.isoformat()}",
            computation_version=self.VERSION,
            evidence={
                "source_feature_keys": sorted(key for key in RAW_KEYS if key in rows and rows[key].get("value") is not None),
                "classification_policy": POLICY_VERSION,
                "classification_source": classification["source"],
                "classification_available_at": classification["available_at"],
            },
        )
