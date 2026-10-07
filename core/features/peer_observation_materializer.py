from __future__ import annotations

from datetime import datetime, timezone

from data.database.sqlite_store import SQLiteStore
from data.repositories.destination_peer_repository import DestinationPeerRepository
from data.repositories.model_feature_repository import ModelFeatureRepository


RAW_KEYS = {
    "RAW_CURRENT_MARKET_CAP",
    "RAW_EV_TO_SALES_TTM",
    "RAW_EV_TO_EBITDA_TTM",
    "RAW_PRICE_TO_FCF_TTM",
}


class DestinationPeerObservationMaterializer:
    """Build one peer observation from canonical PIT feature rows.

    market_cap_bucket and profitability_state are explicit required inputs
    because S15.3 did not freeze their category definitions. They are never
    inferred from unrelated legacy classification rules.
    """

    VERSION = "wf3-peer-observation-v1"

    def __init__(self, store: SQLiteStore, features: ModelFeatureRepository, peers: DestinationPeerRepository) -> None:
        self.store = store
        self.features = features
        self.peers = peers

    def materialize(self, *, security_id: str, route: str, as_of: datetime, market_cap_bucket: str, profitability_state: str) -> str | None:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        security = self.store.connection.execute(
            "SELECT sector,industry FROM security_master WHERE security_id=?",
            (security_id,),
        ).fetchone()
        if security is None:
            raise ValueError(f"unknown security_id: {security_id}")
        sector = str(security["sector"] or "").strip()
        industry = str(security["industry"] or "").strip()
        if not sector or not industry:
            return None
        if not market_cap_bucket.strip() or not profitability_state.strip():
            return None

        rows = self.features.load_as_of(security_id, as_of)
        def value(key: str) -> float | None:
            row = rows.get(key)
            if row is None or row.get("value") is None:
                return None
            return float(row["value"])

        market_cap = value("RAW_CURRENT_MARKET_CAP")
        if market_cap is None or market_cap <= 0:
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
            market_cap_bucket=market_cap_bucket,
            profitability_state=profitability_state,
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
                "classification_policy": "explicit canonical inputs; no inferred bucket/state",
            },
        )
