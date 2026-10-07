from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Iterable

from core.features.peer_cohort import PeerObservation
from data.database.sqlite_store import SQLiteStore


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc).isoformat()


class DestinationPeerRepository:
    """PIT peer observations for S15.3 destination valuation.

    Classification fields are explicit inputs. This repository does not invent
    market-cap bucket boundaries, profitability-state categories, or N<30
    expansion rules.
    """

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def save(
        self,
        *,
        security_id: str,
        as_of_month: str,
        route: str,
        sector: str,
        industry: str,
        market_cap_bucket: str,
        profitability_state: str,
        market_cap: float | None,
        sales_multiple: float | None,
        ebitda_multiple: float | None,
        fcf_multiple: float | None,
        feature_as_of: datetime,
        available_at: datetime,
        source_ref: str,
        computation_version: str,
        quality_status: str = "CANONICAL_DERIVED",
        evidence: dict | None = None,
    ) -> str:
        if available_at > feature_as_of:
            raise ValueError("available_at cannot be later than feature_as_of")
        if len(as_of_month) != 7 or as_of_month[4] != "-":
            raise ValueError("as_of_month must be YYYY-MM")
        for label, value in (
            ("route", route),
            ("sector", sector),
            ("industry", industry),
            ("market_cap_bucket", market_cap_bucket),
            ("profitability_state", profitability_state),
        ):
            if not str(value).strip():
                raise ValueError(f"{label} is required; missing classifications fail closed")

        identity = "|".join([
            security_id,
            as_of_month,
            route,
            sector,
            industry,
            market_cap_bucket,
            profitability_state,
            _iso(feature_as_of),
            source_ref,
            computation_version,
        ])
        observation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, identity))
        self.store.connection.execute(
            """
            INSERT INTO destination_peer_observations (
                observation_id,security_id,as_of_month,route,sector,industry,
                market_cap_bucket,profitability_state,market_cap,sales_multiple,
                ebitda_multiple,fcf_multiple,feature_as_of,available_at,source_ref,
                quality_status,computation_version,evidence_json,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(observation_id) DO UPDATE SET
                market_cap=excluded.market_cap,
                sales_multiple=excluded.sales_multiple,
                ebitda_multiple=excluded.ebitda_multiple,
                fcf_multiple=excluded.fcf_multiple,
                quality_status=excluded.quality_status,
                evidence_json=excluded.evidence_json,
                created_at=excluded.created_at
            """,
            (
                observation_id,security_id,as_of_month,route,sector,industry,
                market_cap_bucket,profitability_state,market_cap,sales_multiple,
                ebitda_multiple,fcf_multiple,_iso(feature_as_of),_iso(available_at),
                source_ref,quality_status,computation_version,
                json.dumps(evidence or {},sort_keys=True,separators=(",",":")),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.store.connection.commit()
        return observation_id

    def load_month(self, *, as_of_month: str, as_of: datetime) -> list[PeerObservation]:
        cutoff = _iso(as_of)
        rows = self.store.connection.execute(
            """
            WITH ranked AS (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY security_id,route,sector,industry,
                                        market_cap_bucket,profitability_state
                           ORDER BY feature_as_of DESC,available_at DESC,created_at DESC
                       ) AS rn
                FROM destination_peer_observations
                WHERE as_of_month=?
                  AND feature_as_of<=?
                  AND available_at<=?
            )
            SELECT * FROM ranked WHERE rn=1
            ORDER BY security_id
            """,
            (as_of_month,cutoff,cutoff),
        ).fetchall()
        return [
            PeerObservation(
                security_id=str(row["security_id"]),
                as_of_month=str(row["as_of_month"]),
                route=str(row["route"]),
                sector=str(row["sector"]),
                industry=str(row["industry"]),
                market_cap_bucket=str(row["market_cap_bucket"]),
                profitability_state=str(row["profitability_state"]),
                market_cap=(float(row["market_cap"]) if row["market_cap"] is not None else None),
                sales_multiple=(float(row["sales_multiple"]) if row["sales_multiple"] is not None else None),
                ebitda_multiple=(float(row["ebitda_multiple"]) if row["ebitda_multiple"] is not None else None),
                fcf_multiple=(float(row["fcf_multiple"]) if row["fcf_multiple"] is not None else None),
            )
            for row in rows
        ]

    def save_many(self, rows: Iterable[dict]) -> int:
        count=0
        for row in rows:
            self.save(**row)
            count+=1
        return count
