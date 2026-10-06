from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GlobalReferenceListing:
    listing_key: str
    ticker: str
    exchange: str
    name: str
    asset_type: str | None
    country: str | None
    country_code: str | None
    isin: str | None
    aliases: str | None
    currency: str | None = None
    mic: str | None = None
    sector: str | None = None
    industry_group: str | None = None
    industry: str | None = None
    figi: str | None = None
    composite_figi: str | None = None
    shareclass_figi: str | None = None
    active: bool = True
    source: str = "ADANOS_REFERENCE"
    source_scope: str = "REFERENCE_ONLY"
    redistribution_status: str = "LOCAL_REFERENCE_ONLY"

    @property
    def market(self) -> str:
        code = (self.country_code or "").strip().upper()
        return code or "GLOBAL"
