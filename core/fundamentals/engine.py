from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from core.contracts.entities import Security
from data.repositories.fundamental_repository import FundamentalRepository


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

    def __init__(self, repository: FundamentalRepository, providers: dict[str, object]) -> None:
        self.repository = repository
        self.providers = providers

    async def sync_security(
        self,
        security: Security,
        *,
        provider_mode: str = "AUTO",
        include_estimates: bool = True,
        include_metrics: bool = True,
    ) -> FundamentalSyncResult:
        mode = provider_mode.upper()
        selected = self.REGULATORY_PRIORITY if mode == "AUTO" else (mode,)
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
            for name in selected:
                provider = self.providers.get(name)
                if provider is None or getattr(provider, "configured", True) is False:
                    continue
                try:
                    if not await provider.validate_symbol(security):
                        continue
                    filings = list(await provider.get_filings(security))
                    facts = list(await provider.get_facts(security))
                    filings_loaded += self.repository.save_filings(filings)
                    facts_loaded += self.repository.save_facts(facts)

                    if include_estimates and name == "FINNHUB":
                        estimates = list(await provider.get_estimates(security))
                        estimates_loaded += self.repository.save_estimates(estimates)

                    if include_metrics and name in {"FINNHUB", "FMP"}:
                        metrics = list(await provider.get_company_metrics(security))
                        kpis_loaded += self.repository.save_guidance_kpis(metrics)

                    used.append(name)
                except Exception as exc:
                    errors.append(f"{name}: {exc}")
                    if name == "SEC_EDGAR" and mode == "SEC_EDGAR":
                        raise

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
