from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter

from core.contracts.entities import Security
from data.repositories.fundamental_repository import FundamentalRepository
from data.repositories.provider_health_repository import ProviderHealthRepository


@dataclass(frozen=True)
class _ProviderSyncOutcome:
    provider: str
    filings_loaded: int = 0
    facts_loaded: int = 0
    estimates_loaded: int = 0
    kpis_loaded: int = 0
    error: Exception | None = None


@dataclass(frozen=True)
class FundamentalSyncResult:
    security_id: str
    ticker: str
    provider_mode: str
    filings_loaded: int
    facts_loaded: int
    estimates_loaded: int
    kpis_loaded: int
    validations_run: int
    providers_used: tuple[str, ...]


class FundamentalEngine:
    REGULATORY_PRIORITY = ("SEC_EDGAR", "FINNHUB", "SIMFIN", "FMP")

    def __init__(
        self,
        repository: FundamentalRepository,
        providers: dict[str, object],
        health: ProviderHealthRepository | None = None,
        provider_concurrency_limits: dict[str, int] | None = None,
        default_provider_concurrency: int = 2,
    ) -> None:
        self.repository = repository
        self.providers = providers
        self.health = health
        self.default_provider_concurrency = max(1, int(default_provider_concurrency))
        self.provider_concurrency_limits = {
            name.upper(): max(1, int(limit))
            for name, limit in (provider_concurrency_limits or {}).items()
        }
        self._provider_semaphores: dict[str, asyncio.Semaphore] = {}

    def _provider_order(self, mode: str) -> tuple[str, ...]:
        selected = self.REGULATORY_PRIORITY if mode == "AUTO" else (mode,)
        if self.health is None or mode != "AUTO":
            return selected
        # SEC remains authoritative for canonical regulatory facts. Dynamic
        # health ranking only reorders the enrichment/fallback providers.
        if "SEC_EDGAR" not in selected:
            return self.health.rank(selected)
        secondary = tuple(name for name in selected if name != "SEC_EDGAR")
        return ("SEC_EDGAR",) + self.health.rank(secondary)

    def _provider_semaphore(self, name: str) -> asyncio.Semaphore:
        key = name.upper()
        semaphore = self._provider_semaphores.get(key)
        if semaphore is None:
            limit = self.provider_concurrency_limits.get(
                key, self.default_provider_concurrency
            )
            semaphore = asyncio.Semaphore(limit)
            self._provider_semaphores[key] = semaphore
        return semaphore

    async def _sync_one_provider(
        self,
        name: str,
        security: Security,
        *,
        include_estimates: bool,
        include_metrics: bool,
    ) -> _ProviderSyncOutcome:
        provider = self.providers[name]
        async with self._provider_semaphore(name):
            provider_started = perf_counter()
            try:
                if not await provider.validate_symbol(security):
                    raise RuntimeError("symbol validation failed")

                filings = list(await provider.get_filings(security))
                facts = list(await provider.get_facts(security))
                filings_loaded = self.repository.save_filings(filings)
                facts_loaded = self.repository.save_facts(facts)

                estimates_loaded = 0
                if include_estimates and name == "FINNHUB":
                    estimates = list(await provider.get_estimates(security))
                    estimates_loaded = self.repository.save_estimates(estimates)

                kpis_loaded = 0
                if include_metrics and name in {"FINNHUB", "FMP"}:
                    metrics = list(await provider.get_company_metrics(security))
                    kpis_loaded = self.repository.save_guidance_kpis(metrics)

                if self.health is not None:
                    self.health.record_success(
                        name,
                        latency_ms=(perf_counter() - provider_started) * 1000.0,
                    )
                return _ProviderSyncOutcome(
                    provider=name,
                    filings_loaded=filings_loaded,
                    facts_loaded=facts_loaded,
                    estimates_loaded=estimates_loaded,
                    kpis_loaded=kpis_loaded,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self.health is not None:
                    text = str(exc)
                    self.health.record_failure(
                        name,
                        latency_ms=(perf_counter() - provider_started) * 1000.0,
                        rate_limited=("429" in text or "rate limit" in text.lower()),
                        message=text[:500],
                    )
                return _ProviderSyncOutcome(provider=name, error=exc)

    async def sync_security(
        self,
        security: Security,
        *,
        provider_mode: str = "AUTO",
        include_estimates: bool = True,
        include_metrics: bool = True,
    ) -> FundamentalSyncResult:
        mode = provider_mode.upper()
        selected = self._provider_order(mode)
        started = datetime.now(timezone.utc)
        sync_id = str(uuid.uuid4())
        self.repository.store.connection.execute(
            """
            INSERT INTO fundamental_sync_runs (
                sync_id,security_id,ticker,provider_mode,started_at,status
            ) VALUES (?,?,?,?,?,?)
            """,
            (sync_id,security.security_id,security.ticker,mode,started.isoformat(),"RUNNING"),
        )
        self.repository.store.connection.commit()

        filings_loaded=facts_loaded=estimates_loaded=kpis_loaded=0
        used: list[str] = []
        errors: list[str] = []

        try:
            eligible: list[str] = []
            for name in selected:
                provider = self.providers.get(name)
                if provider is None or getattr(provider, "configured", True) is False:
                    continue
                if self.health is not None and not self.health.can_attempt(name):
                    errors.append(f"{name}: circuit open")
                    continue
                eligible.append(name)

            def consume(outcome: _ProviderSyncOutcome) -> None:
                nonlocal filings_loaded, facts_loaded, estimates_loaded, kpis_loaded
                if outcome.error is not None:
                    errors.append(f"{outcome.provider}: {outcome.error}")
                    return
                filings_loaded += outcome.filings_loaded
                facts_loaded += outcome.facts_loaded
                estimates_loaded += outcome.estimates_loaded
                kpis_loaded += outcome.kpis_loaded
                used.append(outcome.provider)

            if mode == "AUTO" and "SEC_EDGAR" in eligible:
                # SEC is authoritative and completes before enrichment providers
                # begin. Parallelism is only used among secondary/enrichment
                # providers, so canonical regulatory precedence cannot change.
                sec_outcome = await self._sync_one_provider(
                    "SEC_EDGAR",
                    security,
                    include_estimates=include_estimates,
                    include_metrics=include_metrics,
                )
                consume(sec_outcome)
                eligible = [name for name in eligible if name != "SEC_EDGAR"]

            if mode == "AUTO":
                outcomes = await asyncio.gather(
                    *(
                        self._sync_one_provider(
                            name,
                            security,
                            include_estimates=include_estimates,
                            include_metrics=include_metrics,
                        )
                        for name in eligible
                    )
                )
                for outcome in outcomes:
                    consume(outcome)
            else:
                for name in eligible:
                    outcome = await self._sync_one_provider(
                        name,
                        security,
                        include_estimates=include_estimates,
                        include_metrics=include_metrics,
                    )
                    consume(outcome)
                    if (
                        name == "SEC_EDGAR"
                        and mode == "SEC_EDGAR"
                        and outcome.error is not None
                    ):
                        raise outcome.error

            validations = self.repository.validate_against_sec(security.security_id)
            status = "SUCCESS" if used else "NO_PROVIDER_DATA"
            if errors and used:
                status = "PARTIAL"
            self.repository.store.connection.execute(
                """
                UPDATE fundamental_sync_runs SET
                    filings_loaded=?,facts_loaded=?,estimates_loaded=?,kpis_loaded=?,
                    validations_run=?,completed_at=?,status=?,message=?
                WHERE sync_id=?
                """,
                (
                    filings_loaded,facts_loaded,estimates_loaded,kpis_loaded,validations,
                    datetime.now(timezone.utc).isoformat(),status,
                    "; ".join(errors) if errors else None,sync_id,
                ),
            )
            self.repository.store.connection.commit()
            if not used:
                raise RuntimeError(
                    "No fundamental provider produced data. " +
                    ("; ".join(errors) if errors else "Check provider configuration.")
                )
            return FundamentalSyncResult(
                security_id=security.security_id,
                ticker=security.ticker,
                provider_mode=mode,
                filings_loaded=filings_loaded,
                facts_loaded=facts_loaded,
                estimates_loaded=estimates_loaded,
                kpis_loaded=kpis_loaded,
                validations_run=validations,
                providers_used=tuple(used),
            )
        except Exception as exc:
            self.repository.store.connection.execute(
                """
                UPDATE fundamental_sync_runs
                SET completed_at=?,status='ERROR',message=?
                WHERE sync_id=?
                """,
                (datetime.now(timezone.utc).isoformat(),str(exc),sync_id),
            )
            self.repository.store.connection.commit()
            raise
