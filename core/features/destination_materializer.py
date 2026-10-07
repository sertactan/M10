from __future__ import annotations

from datetime import datetime, timezone

from core.features.destination_evidence import (
    capped_peer_multiple,
    plausible_ceiling_mc,
    supported_mc_fundamental_inflection,
)
from data.repositories.model_feature_repository import ModelFeatureRepository


FI_RAW_KEYS = {
    "RAW_FWD_REVENUE_12",
    "RAW_FWD_EBITDA_12",
    "RAW_FWD_FCF_12",
    "RAW_NET_DEBT",
    "PEER_P90_SALES_MULTIPLE",
    "PEER_MEDIAN_SALES_MULTIPLE",
    "PEER_P90_EBITDA_MULTIPLE",
    "PEER_MEDIAN_EBITDA_MULTIPLE",
    "PEER_P90_FCF_MULTIPLE",
    "PEER_MEDIAN_FCF_MULTIPLE",
}

CEILING_RAW_KEYS = {
    "ROUTE_PEER_P99_MARKET_CAP",
    "ROUTE_PEER_N",
    "EVIDENCE_BACKED_COMPARABLE_MC",
}


class DestinationFeatureMaterializer:
    """Materialize canonical destination fields only from PIT raw evidence."""

    VERSION = "wf2-destination-materializer-v1"

    def __init__(self, repository: ModelFeatureRepository) -> None:
        self.repository = repository

    @staticmethod
    def _value(rows: dict[str, dict], key: str) -> float | None:
        row = rows.get(key)
        if row is None or row.get("value") is None:
            return None
        return float(row["value"])

    @staticmethod
    def _latest_availability(rows: dict[str, dict], keys: set[str], as_of: datetime) -> datetime:
        timestamps = [
            datetime.fromisoformat(str(rows[key]["available_at"]))
            for key in keys
            if key in rows and rows[key].get("value") is not None
        ]
        if not timestamps:
            return as_of.astimezone(timezone.utc)
        return max(timestamps).astimezone(timezone.utc)

    def materialize(self, *, security_id: str, as_of: datetime) -> dict[str, str]:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        rows = self.repository.load_as_of(security_id, as_of)
        written: dict[str, str] = {}

        sales_multiple = capped_peer_multiple(
            peer_p90=self._value(rows, "PEER_P90_SALES_MULTIPLE"),
            peer_median=self._value(rows, "PEER_MEDIAN_SALES_MULTIPLE"),
        )
        ebitda_multiple = capped_peer_multiple(
            peer_p90=self._value(rows, "PEER_P90_EBITDA_MULTIPLE"),
            peer_median=self._value(rows, "PEER_MEDIAN_EBITDA_MULTIPLE"),
        )
        fcf_multiple = capped_peer_multiple(
            peer_p90=self._value(rows, "PEER_P90_FCF_MULTIPLE"),
            peer_median=self._value(rows, "PEER_MEDIAN_FCF_MULTIPLE"),
        )
        fi = supported_mc_fundamental_inflection(
            revenue_12=self._value(rows, "RAW_FWD_REVENUE_12"),
            ebitda_12=self._value(rows, "RAW_FWD_EBITDA_12"),
            fcf_12=self._value(rows, "RAW_FWD_FCF_12"),
            sales_multiple=sales_multiple,
            ebitda_multiple=ebitda_multiple,
            fcf_multiple=fcf_multiple,
            net_debt=self._value(rows, "RAW_NET_DEBT"),
        )
        if fi.supported_mc is not None:
            available = self._latest_availability(rows, FI_RAW_KEYS, as_of)
            written["SUPPORTED_MC_12_FI"] = self.repository.save_feature(
                security_id=security_id,
                feature_key="SUPPORTED_MC_12_FI",
                value=fi.supported_mc,
                feature_as_of=as_of,
                available_at=available,
                source_phase="DERIVED_CANONICAL",
                source_ref=f"WF2_DESTINATION_FI:{security_id}:{as_of.isoformat()}",
                quality_status="CANONICAL_DERIVED",
                computation_version=self.VERSION,
                evidence={
                    "valid_methods": list(fi.valid_methods),
                    "equity_estimates": fi.equity_estimates,
                    "single_method_model_fit_penalty": fi.model_fit_penalty,
                    "blockers": list(fi.blockers),
                    "multiple_cap_rule": "min(peer_p90, 2*peer_median)",
                },
            )

        ceiling = plausible_ceiling_mc(
            route_peer_p99_market_cap=self._value(rows, "ROUTE_PEER_P99_MARKET_CAP"),
            route_peer_n=(
                int(self._value(rows, "ROUTE_PEER_N"))
                if self._value(rows, "ROUTE_PEER_N") is not None
                else None
            ),
            evidence_backed_comparable_mc=self._value(rows, "EVIDENCE_BACKED_COMPARABLE_MC"),
        )
        if ceiling is not None:
            available = self._latest_availability(rows, CEILING_RAW_KEYS, as_of)
            written["PLAUSIBLE_CEILING_MC"] = self.repository.save_feature(
                security_id=security_id,
                feature_key="PLAUSIBLE_CEILING_MC",
                value=ceiling,
                feature_as_of=as_of,
                available_at=available,
                source_phase="DERIVED_CANONICAL",
                source_ref=f"WF2_DESTINATION_CEILING:{security_id}:{as_of.isoformat()}",
                quality_status="CANONICAL_DERIVED",
                computation_version=self.VERSION,
                evidence={
                    "peer_p99_market_cap": self._value(rows, "ROUTE_PEER_P99_MARKET_CAP"),
                    "peer_n": self._value(rows, "ROUTE_PEER_N"),
                    "evidence_backed_comparable_mc": self._value(rows, "EVIDENCE_BACKED_COMPARABLE_MC"),
                    "rule": "max(valid peer P99 when N>=30, evidence-backed comparable)",
                },
            )
        return written
