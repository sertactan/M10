from __future__ import annotations

from datetime import datetime

from core.models.s153_v12_contracts import S153V12Input
from data.repositories.model_feature_repository import ModelFeatureRepository


CONTROL_KEY_MAP = {
    "F49_MCR": "MCR",
    "F50_TAMMC": "TAMMC",
    "F51_GP": "GP",
    "F52_RPS": "RPS",
    "F53_FPS": "FPS",
    "F54_DIL": "DIL",
    "F55_IROIC": "IROIC",
    "F56_ORG": "ORG",
    "F57_UE": "UE",
    "F58_MOAT": "MOAT",
    "F59_CAPINT": "CAPINT",
    "F60_CONC": "CONC",
}


class S153V12InputLoader:
    def __init__(self, repository: ModelFeatureRepository) -> None:
        self.repository = repository

    def load(self, *, security_id: str, ticker: str, as_of: datetime) -> S153V12Input:
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
        # Raw/peer evidence is consumed by upstream materializers and must not
        # leak into the 0..100 model-score feature map. SupportedMC and
        # PLAUSIBLE_CEILING_MC are canonical model inputs and are intentionally
        # retained because their names do not use the raw/peer prefixes.
        features = {
            key: row["value"]
            for key, row in rows.items()
            if key not in reserved
            and not key.startswith("RAW_")
            and not key.startswith("PEER_")
            and not key.startswith("ROUTE_PEER_")
            and key != "EVIDENCE_BACKED_COMPARABLE_MC"
        }
        return S153V12Input(
            security_id=security_id,
            ticker=ticker,
            as_of=as_of,
            discovery_factors=discovery,
            control_factors=control,
            features=features,
            current_price=rows.get("RAW_CURRENT_PRICE", {}).get("value"),
            current_market_cap=rows.get("RAW_CURRENT_MARKET_CAP", {}).get("value"),
        )
