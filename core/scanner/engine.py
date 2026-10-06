from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from core.scanner.contracts import (
    ScanCandidate,
    ScanMode,
    ScanProgress,
    ScanRow,
    ScanSummary,
)
from core.scanner.production import CandidateSource, SecurityScorer


ProgressCallback = Callable[[ScanProgress], None]


class MarketScanner:
    """Batch scanner over the canonical US universe.

    The scanner itself does not fetch provider data and does not contain model
    formulas. Candidate universe and model scoring are injected canonical layers.
    """

    ALLOWED_EXCHANGES = {"NASDAQ", "NYSE", "AMEX"}

    def __init__(
        self,
        candidates: CandidateSource,
        scorer: SecurityScorer,
        *,
        batch_size: int = 500,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be >=1")
        self.candidates = candidates
        self.scorer = scorer
        self.batch_size = batch_size

    def scan_current(
        self,
        *,
        as_of: datetime,
        on_progress: ProgressCallback | None = None,
    ) -> tuple[list[ScanRow], ScanSummary]:
        return self._scan(
            candidates=self.candidates.current(),
            as_of=as_of,
            mode=ScanMode.CURRENT,
            on_progress=on_progress,
        )

    def scan_historical(
        self,
        *,
        as_of: datetime,
        on_progress: ProgressCallback | None = None,
    ) -> tuple[list[ScanRow], ScanSummary]:
        return self._scan(
            candidates=self.candidates.historical(as_of),
            as_of=as_of,
            mode=ScanMode.HISTORICAL,
            on_progress=on_progress,
        )

    def _scan(
        self,
        *,
        candidates: list[ScanCandidate],
        as_of: datetime,
        mode: ScanMode,
        on_progress: ProgressCallback | None,
    ) -> tuple[list[ScanRow], ScanSummary]:
        if as_of.tzinfo is None:
            raise ValueError("scan as_of must be timezone-aware")

        invalid = sorted({c.exchange for c in candidates if c.exchange not in self.ALLOWED_EXCHANGES})
        if invalid:
            raise ValueError(f"US scanner received unsupported exchanges: {invalid}")

        rows: list[ScanRow] = []
        total = len(candidates)
        for offset in range(0, total, self.batch_size):
            batch = candidates[offset : offset + self.batch_size]
            for candidate in batch:
                v12, v14 = self.scorer.score(candidate, as_of)
                rows.append(
                    ScanRow(
                        security_id=candidate.security_id,
                        ticker=candidate.ticker,
                        exchange=candidate.exchange,
                        as_of=as_of,
                        mode=mode,
                        v12_score=v12.score,
                        v12_status=v12.status,
                        v12_route=v12.primary_route,
                        v12_destination=getattr(v12, "verdict", None),
                        v14_score=v14.score,
                        v14_status=v14.status,
                        v14_route=v14.primary_route,
                        v14_destination=v14.primary_magnitude,
                        delisted=(not candidate.active) or bool(candidate.delisted_date),
                        metadata={
                            "v12_confidence": getattr(v12, "confidence", None),
                            "v14_confidence": getattr(v14, "confidence", None),
                        },
                    )
                )
                if on_progress is not None:
                    on_progress(
                        ScanProgress(
                            completed=len(rows),
                            total=total,
                            last_ticker=candidate.ticker,
                        )
                    )

        return rows, self._summary(rows, mode=mode, as_of=as_of)

    @staticmethod
    def _summary(rows: list[ScanRow], *, mode: ScanMode, as_of: datetime) -> ScanSummary:
        return ScanSummary(
            mode=mode,
            as_of=as_of,
            total=len(rows),
            nasdaq=sum(1 for r in rows if r.exchange == "NASDAQ"),
            nyse=sum(1 for r in rows if r.exchange == "NYSE"),
            amex=sum(1 for r in rows if r.exchange == "AMEX"),
            delisted=sum(1 for r in rows if r.delisted),
            v12_scored=sum(1 for r in rows if r.v12_score is not None),
            v14_scored=sum(1 for r in rows if r.v14_score is not None),
        )
