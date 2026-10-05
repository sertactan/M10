from __future__ import annotations

from datetime import datetime

from core.features.s153_v12_input_loader import CONTROL_KEY_MAP
from core.models.s153_v14_contracts import S153V14Input
from data.repositories.model_feature_repository import ModelFeatureRepository


class S153V14InputLoader:
    """Load V1.4 inputs only from the canonical PIT feature repository.

    No provider adapter is called here. Phase 1-3 provider data must already have
    been normalized and materialized into the canonical model-feature layer.
    """

    def __init__(self, repository: ModelFeatureRepository) -> None:
        self.repository = repository

    def load(self, *, security_id: str, ticker: str, as_of: datetime) -> S153V14Input:
        rows = self.repository.load_as_of(security_id, as_of)
        discovery = {
            i: rows.get(f"D{i:02d}", {}).get("value")
            for i in range(1, 49)
        }
        control = {
            canonical: rows.get(storage_key, {}).get("value")
            for storage_key, canonical in CONTROL_KEY_MAP.items()
        }
        reserved = {
            *(f"D{i:02d}" for i in range(1, 49)),
            *CONTROL_KEY_MAP.keys(),
            "RAW_CURRENT_PRICE",
            "RAW_CURRENT_MARKET_CAP",
        }
        features = {
            key: row["value"]
            for key, row in rows.items()
            if key not in reserved
        }
        return S153V14Input(
            security_id=security_id,
            ticker=ticker,
            as_of=as_of,
            discovery_factors=discovery,
            control_factors=control,
            features=features,
            current_price=rows.get("RAW_CURRENT_PRICE", {}).get("value"),
            current_market_cap=rows.get("RAW_CURRENT_MARKET_CAP", {}).get("value"),
        )
