from __future__ import annotations

from datetime import datetime

from core.features.peer_cohort import PeerObservation, evaluate_peer_cohort
from core.features.wf3_peer_policy import POLICY_VERSION
from data.repositories.destination_peer_repository import DestinationPeerRepository
from data.repositories.model_feature_repository import ModelFeatureRepository


class DestinationPeerStatsMaterializer:
    """Write PIT peer statistics using frozen WF3 Peer Policy V1."""

    VERSION = "wf3-peer-stats-v2-policy-v1"

    def __init__(self, peers: DestinationPeerRepository, features: ModelFeatureRepository) -> None:
        self.peers = peers
        self.features = features

    def _save(self, *, target: PeerObservation, as_of: datetime, key: str, value: float | None, metric_n: int, cohort_n: int, cohort_status: str, evidence: dict) -> str | None:
        if value is None:
            return None
        quality = "CANONICAL_DERIVED" if metric_n >= 50 and cohort_n >= 50 else "CANONICAL_DERIVED_LOW_CONFIDENCE"
        return self.features.save_feature(
            security_id=target.security_id,
            feature_key=key,
            value=float(value),
            feature_as_of=as_of,
            available_at=as_of,
            source_phase="DERIVED_CANONICAL",
            source_ref=f"WF3_PEER:{target.as_of_month}:{target.route}",
            quality_status=quality,
            computation_version=self.VERSION,
            evidence={
                "peer_metric_n": metric_n,
                "peer_cohort_n": cohort_n,
                "cohort_status": cohort_status,
                "peer_policy": POLICY_VERSION,
                "peer_key": {
                    "as_of_month": target.as_of_month,
                    "route": target.route,
                    "sector": target.sector,
                    "industry": target.industry,
                    "market_cap_bucket": target.market_cap_bucket,
                    "profitability_state": target.profitability_state,
                },
                **evidence,
            },
        )

    def materialize(self, *, target: PeerObservation, as_of: datetime) -> dict[str, str]:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        rows = self.peers.load_month(as_of_month=target.as_of_month, as_of=as_of)
        result = evaluate_peer_cohort(target, rows)
        if result.cohort_n < 30:
            return {}

        written: dict[str, str] = {}
        for prefix, stats in (("SALES", result.sales), ("EBITDA", result.ebitda), ("FCF", result.fcf)):
            if stats.median is not None:
                fid = self._save(target=target, as_of=as_of, key=f"PEER_MEDIAN_{prefix}_MULTIPLE", value=stats.median, metric_n=stats.n, cohort_n=result.cohort_n, cohort_status=result.cohort_status, evidence={"statistic":"median","metric":prefix})
                if fid:
                    written[f"PEER_MEDIAN_{prefix}_MULTIPLE"] = fid
            if stats.p90 is not None:
                fid = self._save(target=target, as_of=as_of, key=f"PEER_P90_{prefix}_MULTIPLE", value=stats.p90, metric_n=stats.n, cohort_n=result.cohort_n, cohort_status=result.cohort_status, evidence={"statistic":"p90","metric":prefix})
                if fid:
                    written[f"PEER_P90_{prefix}_MULTIPLE"] = fid

        if result.market_cap.p99 is not None:
            p99_id = self._save(target=target, as_of=as_of, key="ROUTE_PEER_P99_MARKET_CAP", value=result.market_cap.p99, metric_n=result.market_cap.n, cohort_n=result.cohort_n, cohort_status=result.cohort_status, evidence={"statistic":"p99","metric":"MARKET_CAP"})
            n_id = self._save(target=target, as_of=as_of, key="ROUTE_PEER_N", value=float(result.market_cap.n), metric_n=result.market_cap.n, cohort_n=result.cohort_n, cohort_status=result.cohort_status, evidence={"statistic":"valid_n","metric":"MARKET_CAP"})
            if p99_id:
                written["ROUTE_PEER_P99_MARKET_CAP"] = p99_id
            if n_id:
                written["ROUTE_PEER_N"] = n_id
        return written
