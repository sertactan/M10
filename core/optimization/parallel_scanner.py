from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Lock, local
from typing import Protocol

from core.scanner.contracts import ScanCandidate, ScanMode, ScanProgress, ScanRow, ScanSummary
from core.scanner.production import CandidateSource, SecurityScorer


ProgressCallback = Callable[[ScanProgress], None]


class ClosableSecurityScorer(SecurityScorer, Protocol):
    def close(self) -> None: ...


class ParallelMarketScanner:
    """Parallel scanner with one scorer/database context per worker thread.

    executor.map preserves candidate ordering, so results remain deterministic.
    Financial/model semantics are untouched; only independent candidate scoring
    is executed concurrently.
    """

    ALLOWED_EXCHANGES = {"NASDAQ", "NYSE", "AMEX"}

    def __init__(
        self,
        candidates: CandidateSource,
        scorer_factory: Callable[[], ClosableSecurityScorer],
        *,
        workers: int,
        batch_size: int = 500,
    ) -> None:
        if workers < 1:
            raise ValueError("workers must be >=1")
        if batch_size < 1:
            raise ValueError("batch_size must be >=1")
        self.candidates = candidates
        self.scorer_factory = scorer_factory
        self.workers = workers
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
        invalid = sorted(
            {c.exchange for c in candidates if c.exchange not in self.ALLOWED_EXCHANGES}
        )
        if invalid:
            raise ValueError(f"US scanner received unsupported exchanges: {invalid}")

        thread_state = local()
        workers: list[ClosableSecurityScorer] = []
        workers_lock = Lock()

        def scorer_for_thread() -> ClosableSecurityScorer:
            scorer = getattr(thread_state, "scorer", None)
            if scorer is None:
                scorer = self.scorer_factory()
                thread_state.scorer = scorer
                with workers_lock:
                    workers.append(scorer)
            return scorer

        def score_candidate(candidate: ScanCandidate) -> ScanRow:
            v12, v14 = scorer_for_thread().score(candidate, as_of)
            return ScanRow(
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

        rows: list[ScanRow] = []
        try:
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                for row in executor.map(score_candidate, candidates):
                    rows.append(row)
                    if on_progress is not None:
                        on_progress(
                            ScanProgress(
                                completed=len(rows),
                                total=len(candidates),
                                last_ticker=row.ticker,
                            )
                        )
        finally:
            for scorer in workers:
                scorer.close()

        return rows, self._summary(rows, mode=mode, as_of=as_of)

    @staticmethod
    def _summary(
        rows: list[ScanRow],
        *,
        mode: ScanMode,
        as_of: datetime,
    ) -> ScanSummary:
        return ScanSummary(
            mode=mode,
            as_of=as_of,
            total=len(rows),
            nasdaq=sum(1 for row in rows if row.exchange == "NASDAQ"),
            nyse=sum(1 for row in rows if row.exchange == "NYSE"),
            amex=sum(1 for row in rows if row.exchange == "AMEX"),
            delisted=sum(1 for row in rows if row.delisted),
        )
