from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from app.bootstrap import AppContainer
from core.backtest.outcomes import CanonicalForwardOutcomeEngine
from core.prices.models import AdjustmentStatus, PriceQualityStatus, SourcePriceBar
from data.repositories.backtest_repository import BacktestRepository
from data.storage.parquet_price_store import ParquetPriceStore


PilotKind = Literal["WINNER", "CONTROL"]


@dataclass(frozen=True)
class PilotObservation:
    kind: PilotKind
    observation_key: str
    ticker: str
    anchor_group: str
    expected_theme: str | None = None
    proxy_band: str | None = None


@dataclass(frozen=True)
class PilotVerification:
    kind: PilotKind
    observation_key: str
    ticker: str
    anchor_group: str
    security_id: str | None
    anchor_date: str | None
    status: str
    outcome_status: str | None = None
    fm252: float | None = None
    outcome_class: str | None = None
    source: str | None = None
    source_symbol: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class PilotVerificationSummary:
    total: int
    verified_winners: int
    valid_controls: int
    rejected_true_10x_controls: int
    rejected_non_10x_winners: int
    missing_canonical_price: int
    unresolved_identity: int
    unresolved_anchor: int
    partial_or_censored: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def load_pilot_observations(seed_root: Path) -> list[PilotObservation]:
    winners_path = seed_root / "s153_pilot_winners_46.csv"
    controls_path = seed_root / "s153_pilot_controls_150.csv"
    if not winners_path.exists() or not controls_path.exists():
        raise FileNotFoundError(
            "S15.3 pilot seed files are missing from the packaged data/seeds directory"
        )

    observations: list[PilotObservation] = []
    with winners_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            observations.append(
                PilotObservation(
                    kind="WINNER",
                    observation_key=str(row["winner_event_id"]).strip(),
                    ticker=str(row["ticker"]).strip().upper(),
                    anchor_group=str(row["anchor_group"]).strip(),
                    expected_theme=(str(row.get("expected_theme") or "").strip() or None),
                )
            )

    with controls_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("fm252_verified") or "").strip().lower() == "true":
                # The frozen source currently contains no pre-verified controls.
                # If a future seed does, it is still reverified from canonical prices.
                pass
            observations.append(
                PilotObservation(
                    kind="CONTROL",
                    observation_key=str(row["candidate_id"]).strip(),
                    ticker=str(row["ticker"]).strip().upper(),
                    anchor_group=str(row["year"]).strip(),
                    proxy_band=(str(row.get("proxy_band") or "").strip() or None),
                )
            )
    return observations


class PilotHistoricalVerifier:
    """Verify frozen pilot rows using canonical adjusted BACKTEST price paths only.

    Endpoint-return proxy bands are never treated as FM252 labels. Month-only
    event anchors are deliberately unresolved because the frozen pilot manifest
    does not contain an exact event date.
    """

    def __init__(self, app: AppContainer) -> None:
        self.app = app
        self.parquet = ParquetPriceStore(
            app.resolve_data_path(app.app_config.database.parquet_root)
        )
        self.backtests = BacktestRepository(app.sqlite, self.parquet)
        self.engine = CanonicalForwardOutcomeEngine()

    @staticmethod
    def _year_anchor(anchor_group: str) -> int | None:
        value = anchor_group.strip()
        if len(value) == 4 and value.isdigit():
            return int(value)
        return None

    def _resolve_security(self, ticker: str, year: int) -> str | None:
        row = self.app.sqlite.connection.execute(
            """
            SELECT security_id
            FROM ticker_aliases
            WHERE alias=?
              AND (valid_from='' OR valid_from<=?)
              AND (valid_to IS NULL OR valid_to>=?)
            ORDER BY
              CASE WHEN valid_from='' THEN 1 ELSE 0 END,
              valid_from DESC
            LIMIT 1
            """,
            (ticker.upper(), f"{year}-12-31", f"{year}-01-01"),
        ).fetchone()
        if row is not None:
            return str(row["security_id"])

        row = self.app.sqlite.connection.execute(
            """
            SELECT security_id
            FROM security_master
            WHERE ticker=?
            ORDER BY active DESC, updated_at DESC
            LIMIT 1
            """,
            (ticker.upper(),),
        ).fetchone()
        return str(row["security_id"]) if row is not None else None

    def _eligible_selection(self, security_id: str, year: int):
        return self.app.sqlite.connection.execute(
            """
            SELECT cps.*, psr.quality_status, psr.adjustment_status
            FROM canonical_price_selection cps
            JOIN price_series_registry psr
              ON psr.security_id=cps.security_id
             AND psr.source=cps.source
             AND psr.source_symbol=cps.source_symbol
            WHERE cps.security_id=?
              AND cps.purpose='BACKTEST'
              AND cps.start_date<=?
              AND cps.end_date>=?
              AND psr.quality_status<>'FALLBACK_ONLY'
              AND psr.adjustment_status NOT IN ('RAW_ONLY','UNKNOWN')
            ORDER BY cps.selected_at DESC
            LIMIT 1
            """,
            (security_id, f"{year}-12-31", f"{year}-01-01"),
        ).fetchone()

    def _bars_for_selection(self, selection) -> list[SourcePriceBar]:
        frame = self.parquet.read_bars(
            security_id=str(selection["security_id"]),
            source=str(selection["source"]),
            source_symbol=str(selection["source_symbol"]),
            start_date=date.fromisoformat(str(selection["start_date"])),
            end_date=date.fromisoformat(str(selection["end_date"])),
        )
        bars: list[SourcePriceBar] = []
        for row in frame.to_dict(orient="records"):
            trade_date = row["trade_date"]
            if not isinstance(trade_date, date):
                trade_date = date.fromisoformat(str(trade_date)[:10])
            retrieved_at = row["retrieved_at"]
            if not hasattr(retrieved_at, "tzinfo"):
                from datetime import datetime
                retrieved_at = datetime.fromisoformat(str(retrieved_at))
            bars.append(
                SourcePriceBar(
                    security_id=str(row["security_id"]),
                    source=str(row["source"]),
                    source_symbol=str(row["source_symbol"]),
                    trade_date=trade_date,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    raw_close=float(row["raw_close"]),
                    adjusted_close=float(row["adjusted_close"]),
                    volume=float(row["volume"]),
                    vwap=(float(row["vwap"]) if row.get("vwap") is not None else None),
                    retrieved_at=retrieved_at,
                    quality_status=PriceQualityStatus(str(row["quality_status"])),
                    adjustment_status=AdjustmentStatus(str(row["adjustment_status"])),
                    raw_payload_hash=(
                        str(row["raw_payload_hash"])
                        if row.get("raw_payload_hash") is not None
                        else None
                    ),
                )
            )
        return sorted(bars, key=lambda item: item.trade_date)

    @staticmethod
    def _first_session_in_year(bars: list[SourcePriceBar], year: int) -> date | None:
        sessions = [bar.trade_date for bar in bars if bar.trade_date.year == year]
        return min(sessions) if sessions else None

    def verify_one(self, observation: PilotObservation) -> PilotVerification:
        year = self._year_anchor(observation.anchor_group)
        if year is None:
            return PilotVerification(
                kind=observation.kind,
                observation_key=observation.observation_key,
                ticker=observation.ticker,
                anchor_group=observation.anchor_group,
                security_id=None,
                anchor_date=None,
                status="UNRESOLVED_ANCHOR",
                message=(
                    "Pilot manifest has an event/month anchor without an exact date; "
                    "no day is invented."
                ),
            )

        security_id = self._resolve_security(observation.ticker, year)
        if security_id is None:
            return PilotVerification(
                kind=observation.kind,
                observation_key=observation.observation_key,
                ticker=observation.ticker,
                anchor_group=observation.anchor_group,
                security_id=None,
                anchor_date=None,
                status="UNRESOLVED_IDENTITY",
                message="No security_master/ticker_alias identity is available for this historical ticker.",
            )

        selection = self._eligible_selection(security_id, year)
        if selection is None:
            return PilotVerification(
                kind=observation.kind,
                observation_key=observation.observation_key,
                ticker=observation.ticker,
                anchor_group=observation.anchor_group,
                security_id=security_id,
                anchor_date=None,
                status="MISSING_CANONICAL_PRICE",
                message=(
                    "No adjusted, non-fallback, single-provider canonical BACKTEST "
                    "price selection covers the anchor year."
                ),
            )

        bars = self._bars_for_selection(selection)
        anchor = self._first_session_in_year(bars, year)
        if anchor is None:
            return PilotVerification(
                kind=observation.kind,
                observation_key=observation.observation_key,
                ticker=observation.ticker,
                anchor_group=observation.anchor_group,
                security_id=security_id,
                anchor_date=None,
                status="MISSING_CANONICAL_PRICE",
                source=str(selection["source"]),
                source_symbol=str(selection["source_symbol"]),
                message="Canonical BACKTEST series has no completed session in the anchor year.",
            )

        outcome = self.engine.compute(
            security_id=security_id,
            as_of_date_requested=anchor,
            bars=bars,
        )
        self.backtests.save_forward_outcome(outcome)

        common = dict(
            kind=observation.kind,
            observation_key=observation.observation_key,
            ticker=observation.ticker,
            anchor_group=observation.anchor_group,
            security_id=security_id,
            anchor_date=anchor.isoformat(),
            outcome_status=outcome.outcome_status,
            fm252=outcome.fm252,
            outcome_class=outcome.outcome_class,
            source=str(selection["source"]),
            source_symbol=str(selection["source_symbol"]),
        )

        if outcome.outcome_status != "READY" or outcome.fm252 is None:
            return PilotVerification(
                **common,
                status="PARTIAL_OR_CENSORED",
                message="A complete next-252-session adjusted-close path is not available.",
            )

        if observation.kind == "WINNER":
            if outcome.fm252 >= 10.0:
                return PilotVerification(**common, status="VERIFIED_WINNER")
            return PilotVerification(
                **common,
                status="REJECT_NON_10X_WINNER",
                message="Frozen winner event does not satisfy canonical FM252 >= 10 at this calendar anchor.",
            )

        if outcome.fm252 >= 10.0:
            return PilotVerification(
                **common,
                status="REJECT_TRUE_10X",
                message="Provisional control touched/closed >=10x on the canonical 252-session path.",
            )
        return PilotVerification(**common, status="VALID_CONTROL")

    def verify_all(self, observations: list[PilotObservation]) -> tuple[list[PilotVerification], PilotVerificationSummary]:
        rows = [self.verify_one(item) for item in observations]
        counts = {status: sum(row.status == status for row in rows) for status in {
            "VERIFIED_WINNER",
            "VALID_CONTROL",
            "REJECT_TRUE_10X",
            "REJECT_NON_10X_WINNER",
            "MISSING_CANONICAL_PRICE",
            "UNRESOLVED_IDENTITY",
            "UNRESOLVED_ANCHOR",
            "PARTIAL_OR_CENSORED",
        }}
        summary = PilotVerificationSummary(
            total=len(rows),
            verified_winners=counts["VERIFIED_WINNER"],
            valid_controls=counts["VALID_CONTROL"],
            rejected_true_10x_controls=counts["REJECT_TRUE_10X"],
            rejected_non_10x_winners=counts["REJECT_NON_10X_WINNER"],
            missing_canonical_price=counts["MISSING_CANONICAL_PRICE"],
            unresolved_identity=counts["UNRESOLVED_IDENTITY"],
            unresolved_anchor=counts["UNRESOLVED_ANCHOR"],
            partial_or_censored=counts["PARTIAL_OR_CENSORED"],
        )
        return rows, summary
