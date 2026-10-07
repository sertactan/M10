from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone

from app.feature_materializer import CanonicalFeatureMaterializer
from core.features.destination_materializer import DestinationFeatureMaterializer
from core.features.peer_observation_materializer import DestinationPeerObservationMaterializer
from core.features.peer_stats_materializer import DestinationPeerStatsMaterializer
from core.features.s153_v12_input_loader import S153V12InputLoader
from core.models.s153_v12 import CanonicalInputError, S153V12Model
from data.repositories.destination_peer_repository import DestinationPeerRepository
from data.repositories.model_feature_repository import ModelFeatureRepository
from data.repositories.security_classification_repository import SecurityClassificationRepository
from data.repositories.security_repository import SecurityRepository


@dataclass(frozen=True)
class WF3DateReport:
    as_of_date: date
    universe_count: int
    base_feature_materialized: int
    routed: int
    pit_classified: int
    peer_observations: int
    peer_stats_targets: int
    destination_feature_writes: int
    missing_route: int
    missing_pit_classification: int
    missing_peer_observation: int
    model_input_errors: int


class WF3WholeUniverseMaterializer:
    VERSION = "wf3-whole-universe-v1"

    def __init__(self, app) -> None:
        self.app = app
        self.securities = SecurityRepository(app.sqlite)
        self.features = ModelFeatureRepository(app.sqlite)
        self.peers = DestinationPeerRepository(app.sqlite)
        self.classifications = SecurityClassificationRepository(app.sqlite)
        self.base = CanonicalFeatureMaterializer(app)
        self.loader = S153V12InputLoader(self.features)
        self.model = S153V12Model()
        self.peer_observation = DestinationPeerObservationMaterializer(
            app.sqlite, self.features, self.peers
        )
        self.peer_stats = DestinationPeerStatsMaterializer(self.peers, self.features)
        self.destination = DestinationFeatureMaterializer(self.features)

    def materialize_date(self, as_of_date: date) -> WF3DateReport:
        as_of = datetime.combine(as_of_date, time.max, tzinfo=timezone.utc)
        universe = self.securities.universe_as_of(as_of_date)

        base_count = routed = pit_classified = observations = 0
        missing_route = missing_classification = missing_observation = input_errors = 0

        for row in universe:
            security_id = str(row["security_id"])
            ticker = str(row["ticker"])
            base_count += self.base.materialize(row, as_of_date=as_of_date)

            try:
                data = self.loader.load(
                    security_id=security_id,
                    ticker=ticker,
                    as_of=as_of,
                )
                result = self.model.analyze(data)
            except (CanonicalInputError, ValueError):
                input_errors += 1
                continue

            route = result.primary_route
            if not route:
                missing_route += 1
                continue
            routed += 1

            if self.classifications.as_of(security_id, as_of) is None:
                missing_classification += 1
                continue
            pit_classified += 1

            oid = self.peer_observation.materialize(
                security_id=security_id,
                route=route,
                as_of=as_of,
            )
            if oid is None:
                missing_observation += 1
                continue
            observations += 1

        targets = self.peers.load_month(
            as_of_month=as_of.strftime("%Y-%m"),
            as_of=as_of,
        )
        stats_targets = 0
        for target in targets:
            written = self.peer_stats.materialize(target=target, as_of=as_of)
            if written:
                stats_targets += 1

        destination_writes = 0
        for target in targets:
            written = self.destination.materialize(
                security_id=target.security_id,
                as_of=as_of,
            )
            destination_writes += len(written)

        return WF3DateReport(
            as_of_date=as_of_date,
            universe_count=len(universe),
            base_feature_materialized=base_count,
            routed=routed,
            pit_classified=pit_classified,
            peer_observations=observations,
            peer_stats_targets=stats_targets,
            destination_feature_writes=destination_writes,
            missing_route=missing_route,
            missing_pit_classification=missing_classification,
            missing_peer_observation=missing_observation,
            model_input_errors=input_errors,
        )
