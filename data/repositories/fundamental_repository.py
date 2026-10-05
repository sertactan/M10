from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Iterable

from core.fundamentals.models import (
    EstimateRow,
    FilingRecord,
    FundamentalFactRow,
    GuidanceKPI,
)
from core.fundamentals.policy import FundamentalPrecedencePolicy
from data.database.sqlite_store import SQLiteStore


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc).isoformat()


class FundamentalRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self.policy = FundamentalPrecedencePolicy()

    def save_filings(self, filings: Iterable[FilingRecord]) -> int:
        count = 0
        for f in filings:
            filing_id = str(uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"filing|{f.security_id}|{f.source}|{f.accession_number}|{f.form_type}|{f.filing_date}",
            ))
            self.store.connection.execute(
                """
                INSERT INTO filing_records_source (
                    filing_id,security_id,source,cik,form_type,period_end,filing_date,
                    accepted_at,accession_number,source_document,primary_document,
                    is_amendment,retrieved_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(filing_id) DO UPDATE SET
                    accepted_at=COALESCE(excluded.accepted_at,filing_records_source.accepted_at),
                    source_document=COALESCE(excluded.source_document,filing_records_source.source_document),
                    primary_document=COALESCE(excluded.primary_document,filing_records_source.primary_document),
                    retrieved_at=excluded.retrieved_at
                """,
                (
                    filing_id,f.security_id,f.source,f.cik,f.form_type,
                    f.period_end.isoformat() if f.period_end else None,
                    f.filing_date.isoformat(),_iso(f.accepted_at),f.accession_number,
                    f.source_document,f.primary_document,1 if f.is_amendment else 0,
                    _iso(f.retrieved_at),
                ),
            )
            count += 1
        self.store.connection.commit()
        return count

    def save_facts(self, facts: Iterable[FundamentalFactRow]) -> int:
        count = 0
        for f in facts:
            identity = "|".join([
                f.security_id,
                f.source,
                f.metric_name,
                f.provider_metric_name,
                f.unit,
                f.period_start.isoformat() if f.period_start else "",
                f.period_end.isoformat(),
                f.period_kind.value,
                f.accession_number or "",
                f.form_type or "",
                repr(f.value),
                _iso(f.available_at) or "",
            ])
            fact_id = str(uuid.uuid5(uuid.NAMESPACE_URL, identity))
            self.store.connection.execute(
                """
                INSERT INTO fundamental_facts_source (
                    fact_id,security_id,metric_name,provider_metric_name,value,unit,
                    period_start,period_end,period_kind,filing_date,accepted_at,available_at,
                    source,source_document,accession_number,retrieved_at,quality_status,
                    validation_status,family,form_type,fiscal_year,fiscal_period,taxonomy,
                    frame,statement_type,is_amendment,raw_payload_hash
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(fact_id) DO UPDATE SET
                    retrieved_at=excluded.retrieved_at,
                    source_document=excluded.source_document,
                    quality_status=excluded.quality_status,
                    validation_status=CASE
                        WHEN fundamental_facts_source.source='SEC_EDGAR'
                        THEN fundamental_facts_source.validation_status
                        ELSE excluded.validation_status
                    END
                """,
                (
                    fact_id,f.security_id,f.metric_name,f.provider_metric_name,f.value,f.unit,
                    f.period_start.isoformat() if f.period_start else None,
                    f.period_end.isoformat(),f.period_kind.value,
                    f.filing_date.isoformat() if f.filing_date else None,
                    _iso(f.accepted_at),_iso(f.available_at),f.source,f.source_document,
                    f.accession_number,_iso(f.retrieved_at),f.quality_status.value,
                    f.validation_status.value,f.family.value,f.form_type,f.fiscal_year,
                    f.fiscal_period,f.taxonomy,f.frame,f.statement_type,
                    1 if f.is_amendment else 0,f.raw_payload_hash,
                ),
            )
            count += 1
        self.store.connection.commit()
        return count

    def save_estimates(self, rows: Iterable[EstimateRow]) -> int:
        count = 0
        for r in rows:
            estimate_id = str(uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"estimate|{r.security_id}|{r.source}|{r.metric_name}|{r.period_end}|{r.available_at.isoformat()}",
            ))
            self.store.connection.execute(
                """
                INSERT INTO fundamental_estimates_source (
                    estimate_id,security_id,metric_name,period_end,value,unit,low,high,
                    analyst_count,source,source_document,available_at,retrieved_at,
                    quality_status,validation_status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(estimate_id) DO UPDATE SET
                    value=excluded.value,low=excluded.low,high=excluded.high,
                    analyst_count=excluded.analyst_count,retrieved_at=excluded.retrieved_at
                """,
                (
                    estimate_id,r.security_id,r.metric_name,r.period_end.isoformat(),r.value,
                    r.unit,r.low,r.high,r.analyst_count,r.source,r.source_document,
                    _iso(r.available_at),_iso(r.retrieved_at),r.quality_status.value,
                    r.validation_status.value,
                ),
            )
            count += 1
        self.store.connection.commit()
        return count

    def save_guidance_kpis(self, rows: Iterable[GuidanceKPI]) -> int:
        count = 0
        for r in rows:
            record_id = str(uuid.uuid5(
                uuid.NAMESPACE_URL,
                "|".join([
                    "kpi",r.security_id,r.source,r.metric_name,
                    r.period_end.isoformat() if r.period_end else "",
                    r.source_document,r.available_at.isoformat(),
                    repr(r.value),repr(r.value_low),repr(r.value_high),r.text_value or "",
                ]),
            ))
            self.store.connection.execute(
                """
                INSERT INTO company_kpi_guidance_source (
                    record_id,security_id,metric_name,period_end,value,value_low,value_high,
                    unit,text_value,source,source_document,accession_number,available_at,
                    retrieved_at,quality_status,validation_status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(record_id) DO UPDATE SET
                    retrieved_at=excluded.retrieved_at,
                    validation_status=excluded.validation_status
                """,
                (
                    record_id,r.security_id,r.metric_name,
                    r.period_end.isoformat() if r.period_end else None,r.value,r.value_low,
                    r.value_high,r.unit,r.text_value,r.source,r.source_document,
                    r.accession_number,_iso(r.available_at),_iso(r.retrieved_at),
                    r.quality_status.value,r.validation_status.value,
                ),
            )
            count += 1
        self.store.connection.commit()
        return count

    def source_facts_as_of(
        self, security_id: str, as_of: datetime, metric_name: str | None = None
    ) -> list[dict]:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        params: list[object] = [security_id, _iso(as_of)]
        metric_sql = ""
        if metric_name:
            metric_sql = " AND metric_name=?"
            params.append(metric_name)
        rows = self.store.connection.execute(
            f"""
            SELECT * FROM fundamental_facts_source
            WHERE security_id=? AND available_at<=? {metric_sql}
            ORDER BY metric_name,period_end,period_kind,source,available_at
            """,
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def canonical_facts_as_of(self, security_id: str, as_of: datetime) -> list[dict]:
        rows = self.source_facts_as_of(security_id, as_of)
        groups: dict[tuple, list[dict]] = {}
        for r in rows:
            key = (
                r["metric_name"],r["period_start"] or "",r["period_end"],
                r["period_kind"],r["unit"],
            )
            groups.setdefault(key, []).append(r)

        out: list[dict] = []
        for candidates in groups.values():
            sec = [x for x in candidates if x["source"] == "SEC_EDGAR"]
            if sec:
                winner = max(sec, key=lambda x: (x["available_at"], x["retrieved_at"]))
            else:
                priority = {"FINNHUB": 2, "SIMFIN": 3, "FMP": 4, "COMPANY_IR": 5}
                winner = min(
                    candidates,
                    key=lambda x: (
                        priority.get(x["source"], 999),
                        -datetime.fromisoformat(x["available_at"]).timestamp(),
                    ),
                )
            out.append(winner)
        return sorted(out, key=lambda x: (x["metric_name"], x["period_end"], x["period_kind"]))

    def validate_against_sec(self, security_id: str) -> int:
        rows = self.store.connection.execute(
            """
            SELECT * FROM fundamental_facts_source
            WHERE security_id=?
            ORDER BY metric_name,period_end,period_kind,unit,available_at
            """,
            (security_id,),
        ).fetchall()
        groups: dict[tuple, list[dict]] = {}
        for row in rows:
            d = dict(row)
            key=(d["metric_name"],d["period_start"] or "",d["period_end"],d["period_kind"],d["unit"])
            groups.setdefault(key,[]).append(d)

        updates=0
        for candidates in groups.values():
            sec=[x for x in candidates if x["source"]=="SEC_EDGAR"]
            if not sec:
                continue
            authoritative=max(sec,key=lambda x:x["available_at"])
            sec_val=float(authoritative["value"])
            for row in candidates:
                if row["source"]=="SEC_EDGAR":
                    continue
                value=float(row["value"])
                if authoritative["unit"] != row["unit"]:
                    status="CONFLICT"
                else:
                    scale=max(abs(sec_val),abs(value),1e-12)
                    rel=abs(value-sec_val)/scale
                    status="MATCH" if rel<=0.001 else ("CLOSE" if rel<=0.02 else "MISMATCH")
                self.store.connection.execute(
                    "UPDATE fundamental_facts_source SET validation_status=? WHERE fact_id=?",
                    (status,row["fact_id"]),
                )
                self.store.connection.execute(
                    """
                    INSERT INTO fundamental_validation_results (
                        validation_id,security_id,metric_name,period_end,period_kind,unit,
                        sec_fact_id,secondary_fact_id,secondary_source,relative_difference,
                        status,created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        str(uuid.uuid4()),security_id,row["metric_name"],row["period_end"],
                        row["period_kind"],row["unit"],authoritative["fact_id"],row["fact_id"],
                        row["source"],
                        abs(value-sec_val)/max(abs(sec_val),abs(value),1e-12),
                        status,datetime.now(timezone.utc).isoformat(),
                    ),
                )
                updates+=1
        self.store.connection.commit()
        return updates

    def estimates_as_of(self, security_id: str, as_of: datetime) -> list[dict]:
        rows=self.store.connection.execute(
            """
            SELECT * FROM fundamental_estimates_source
            WHERE security_id=? AND available_at<=?
            ORDER BY metric_name,period_end,available_at
            """,
            (security_id,_iso(as_of)),
        ).fetchall()
        return [dict(r) for r in rows]

    def guidance_as_of(self, security_id: str, as_of: datetime) -> list[dict]:
        rows=self.store.connection.execute(
            """
            SELECT * FROM company_kpi_guidance_source
            WHERE security_id=? AND available_at<=?
            ORDER BY metric_name,period_end,available_at
            """,
            (security_id,_iso(as_of)),
        ).fetchall()
        return [dict(r) for r in rows]
