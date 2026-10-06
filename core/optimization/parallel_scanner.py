from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from math import ceil
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

        def score_candidate(
            scorer: ClosableSecurityScorer,
            candidate: ScanCandidate,
        ) -> ScanRow:
            v12, v14 = scorer.score(candidate, as_of)
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
                    "dna60": getattr(v12, "components", {}).get("DNA60"),
                    "v12_missing": tuple(getattr(v12, "missing_requirements", ()) or ()),
                },
            )

        if not candidates:
            return [], self._summary([], mode=mode, as_of=as_of)

        # Each worker owns one scorer/database context for its entire chunk.
        # The scorer is also closed inside that same worker thread. This keeps
        # SQLite's default check_same_thread safety intact and prevents the
        # desktop scanner from closing worker-owned connections on the parent
        # QRunnable thread.
        worker_count = min(self.workers, len(candidates))
        chunk_size = ceil(len(candidates) / worker_count)
        chunks = [
            candidates[start:start + chunk_size]
            for start in range(0, len(candidates), chunk_size)
        ]

        def score_chunk(chunk: list[ScanCandidate]) -> list[ScanRow]:
            scorer = self.scorer_factory()
            try:
                return [score_candidate(scorer, candidate) for candidate in chunk]
            finally:
                scorer.close()

        rows: list[ScanRow] = []
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            for chunk_rows in executor.map(score_chunk, chunks):
                for row in chunk_rows:
                    rows.append(row)
                    if on_progress is not None:
                        on_progress(
                            ScanProgress(
                                completed=len(rows),
                                total=len(candidates),
                                last_ticker=row.ticker,
                            )
                        )

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
            v12_scored=sum(1 for row in rows if row.v12_score is not None),
            v14_scored=sum(1 for row in rows if row.v14_score is not None),
        )
