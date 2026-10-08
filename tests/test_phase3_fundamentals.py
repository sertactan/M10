from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from core.contracts.entities import Security
from core.contracts.enums import Exchange
from core.fundamentals.models import (
    EstimateRow,
    FactFamily,
    FilingRecord,
    FundamentalFactRow,
    FundamentalQualityStatus,
    FundamentalValidationStatus,
    GuidanceKPI,
    PeriodKind,
)
from core.fundamentals.snapshot import FundamentalSnapshotService
from data.database.sqlite_store import SQLiteStore
from data.providers.company_ir import CompanyInvestorRelationsProvider
from data.providers.finnhub_fundamentals import FinnhubFundamentalsProvider
from data.providers.fmp_fundamentals import FMPFundamentalsProvider
from data.providers.sec_edgar_fundamentals import SECEdgarFundamentalsProvider
from data.providers.simfin_fundamentals import SimFinFundamentalsProvider
from data.repositories.fundamental_repository import FundamentalRepository


ROOT = Path(__file__).resolve().parents[1]
SECURITY = Security(
    security_id="SEC_TEST",
    ticker="TEST",
    name="Test Corp",
    exchange=Exchange.NASDAQ,
    cik="0000123456",
)
MAY1 = datetime(2025, 5, 1, 20, 0, tzinfo=timezone.utc)
JUN1 = datetime(2025, 6, 1, 20, 0, tzinfo=timezone.utc)


def _store(tmp_path: Path) -> tuple[SQLiteStore, FundamentalRepository]:
    store = SQLiteStore(tmp_path / "op.db")
    store.initialize(ROOT / "data" / "database" / "schema.sql")
    now = datetime.now(timezone.utc).isoformat()
    store.connection.execute(
        """
        INSERT INTO security_master
        (security_id,ticker,name,exchange,market,cik,active,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        ("SEC_TEST","TEST","Test Corp","NASDAQ","US","0000123456",1,now,now),
    )
    store.connection.commit()
    return store, FundamentalRepository(store)


def _fact(
    *,
    value: float,
    source: str,
    available_at: datetime,
    metric: str = "REVENUE",
    period_end: date = date(2025, 3, 31),
    period_start: date | None = date(2025, 1, 1),
    kind: PeriodKind = PeriodKind.QUARTER,
    unit: str = "USD",
    accession: str | None = None,
    accepted_at: datetime | None = None,
    quality: FundamentalQualityStatus | None = None,
) -> FundamentalFactRow:
    if quality is None:
        quality = (
            FundamentalQualityStatus.AUTHORITATIVE
            if source == "SEC_EDGAR"
            else FundamentalQualityStatus.SECONDARY
        )
    return FundamentalFactRow(
        security_id="SEC_TEST",
        metric_name=metric,
        provider_metric_name=metric,
        value=value,
        unit=unit,
        period_start=period_start,
        period_end=period_end,
        period_kind=kind,
        filing_date=available_at.date(),
        accepted_at=accepted_at,
        available_at=available_at,
        source=source,
        source_document=f"https://example.com/{source}/{metric}",
        accession_number=accession,
        retrieved_at=available_at,
        quality_status=quality,
        validation_status=(
            FundamentalValidationStatus.SEC_CANONICAL
            if source == "SEC_EDGAR"
            else FundamentalValidationStatus.NOT_CHECKED
        ),
        family=FactFamily.REGULATORY if source == "SEC_EDGAR" else FactFamily.NORMALIZED,
    )


def test_sec_submissions_parser_preserves_acceptance_accession_and_amendment() -> None:
    payload = {
        "filings": {
            "recent": {
                "accessionNumber": ["0000123456-25-000001", "0000123456-25-000002"],
                "filingDate": ["2025-05-01", "2025-05-20"],
                "reportDate": ["2025-03-31", "2025-03-31"],
                "acceptanceDateTime": [
                    "2025-05-01T20:15:30.000Z",
                    "2025-05-20T21:10:00.000Z",
                ],
                "form": ["10-Q", "10-Q/A"],
                "primaryDocument": ["q1.htm", "q1a.htm"],
            }
        }
    }
    rows = SECEdgarFundamentalsProvider.parse_submissions_payload(
        "SEC_TEST","0000123456",payload,
        retrieved_at=datetime(2025,5,21,tzinfo=timezone.utc),
    )
    assert len(rows) == 2
    assert rows[0].accepted_at == datetime(2025,5,1,20,15,30,tzinfo=timezone.utc)
    assert rows[0].accession_number == "0000123456-25-000001"
    assert rows[1].is_amendment is True
    assert "/000012345625000001/q1.htm" in (rows[0].source_document or "")


def test_sec_companyfacts_join_uses_acceptance_timestamp_and_required_lineage() -> None:
    filing = FilingRecord(
        security_id="SEC_TEST",source="SEC_EDGAR",cik="0000123456",form_type="10-Q",
        filing_date=date(2025,5,1),accepted_at=MAY1,
        accession_number="0000123456-25-000001",
        source_document="https://www.sec.gov/Archives/example.htm",
        primary_document="q1.htm",period_end=date(2025,3,31),
        retrieved_at=JUN1,
    )
    payload = {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [{
                            "start":"2025-01-01","end":"2025-03-31","val":100.0,
                            "accn":"0000123456-25-000001","fy":2025,"fp":"Q1",
                            "form":"10-Q","filed":"2025-05-01","frame":"CY2025Q1"
                        }]
                    }
                }
            }
        }
    }
    facts = SECEdgarFundamentalsProvider.parse_companyfacts_payload(
        "SEC_TEST","0000123456",payload,
        filing_map={filing.accession_number: filing},
        retrieved_at=JUN1,
        companyfacts_url="https://data.sec.gov/api/xbrl/companyfacts/CIK0000123456.json",
    )
    assert len(facts) == 1
    fact = facts[0]
    assert fact.metric_name == "REVENUE"
    assert fact.value == 100.0
    assert fact.accepted_at == MAY1
    assert fact.available_at == MAY1
    assert fact.period_kind is PeriodKind.QUARTER
    assert fact.source == "SEC_EDGAR"
    assert fact.source_document.endswith("example.htm")
    assert fact.validation_status is FundamentalValidationStatus.SEC_CANONICAL


def test_future_sec_restatement_does_not_leak_into_earlier_snapshot(tmp_path: Path) -> None:
    store, repo = _store(tmp_path)
    repo.save_facts([
        _fact(value=100, source="SEC_EDGAR", available_at=MAY1, accepted_at=MAY1, accession="A1"),
        _fact(value=110, source="SEC_EDGAR", available_at=JUN1, accepted_at=JUN1, accession="A2"),
    ])
    may = repo.canonical_facts_as_of(
        "SEC_TEST", datetime(2025,5,15,23,59,tzinfo=timezone.utc)
    )
    june = repo.canonical_facts_as_of(
        "SEC_TEST", datetime(2025,6,15,23,59,tzinfo=timezone.utc)
    )
    assert [x["value"] for x in may if x["metric_name"]=="REVENUE"] == [100.0]
    assert [x["value"] for x in june if x["metric_name"]=="REVENUE"] == [110.0]
    store.close()


def test_secondary_never_overwrites_sec_fact(tmp_path: Path) -> None:
    store, repo = _store(tmp_path)
    repo.save_facts([
        _fact(value=100, source="SEC_EDGAR", available_at=MAY1, accepted_at=MAY1),
        _fact(value=150, source="FINNHUB", available_at=JUN1),
    ])
    rows = repo.canonical_facts_as_of(
        "SEC_TEST", datetime(2025,6,15,23,59,tzinfo=timezone.utc)
    )
    revenue = [x for x in rows if x["metric_name"]=="REVENUE"]
    assert len(revenue) == 1
    assert revenue[0]["source"] == "SEC_EDGAR"
    assert revenue[0]["value"] == 100.0
    store.close()


def test_secondary_validation_marks_close_without_modifying_sec(tmp_path: Path) -> None:
    store, repo = _store(tmp_path)
    repo.save_facts([
        _fact(value=100, source="SEC_EDGAR", available_at=MAY1, accepted_at=MAY1),
        _fact(value=101, source="FINNHUB", available_at=JUN1, period_start=None),
    ])
    assert repo.validate_against_sec("SEC_TEST") == 1
    sec = store.connection.execute(
        "SELECT validation_status,value FROM fundamental_facts_source WHERE source='SEC_EDGAR'"
    ).fetchone()
    secondary = store.connection.execute(
        "SELECT validation_status FROM fundamental_facts_source WHERE source='FINNHUB'"
    ).fetchone()
    assert sec["validation_status"] == "SEC_CANONICAL"
    assert sec["value"] == 100.0
    assert secondary["validation_status"] == "CLOSE"
    store.close()


def test_finnhub_estimate_parser_is_estimate_family_and_current_timestamped() -> None:
    payload = {"data":[{"period":"2025-06-30","avg":120,"low":100,"high":140,"numberAnalysts":12}]}
    rows = FinnhubFundamentalsProvider.parse_estimates(
        "SEC_TEST",payload,metric_name="REVENUE_ESTIMATE",unit="USD",
        source_document="https://finnhub.io/api/v1/stock/revenue-estimate",
        retrieved_at=JUN1,
    )
    assert len(rows) == 1
    assert rows[0].available_at == JUN1
    assert rows[0].validation_status is FundamentalValidationStatus.ESTIMATE_ONLY
    assert rows[0].analyst_count == 12


def test_estimate_does_not_exist_before_its_available_at(tmp_path: Path) -> None:
    store, repo = _store(tmp_path)
    repo.save_estimates([EstimateRow(
        security_id="SEC_TEST",metric_name="REVENUE_ESTIMATE",
        period_end=date(2025,6,30),value=120,unit="USD",low=100,high=140,
        analyst_count=12,source="FINNHUB",
        source_document="https://finnhub.io/example",retrieved_at=JUN1,
        available_at=JUN1,quality_status=FundamentalQualityStatus.SECONDARY,
        validation_status=FundamentalValidationStatus.ESTIMATE_ONLY,
    )])
    assert repo.estimates_as_of("SEC_TEST", datetime(2025,5,31,23,59,tzinfo=timezone.utc)) == []
    assert len(repo.estimates_as_of("SEC_TEST", datetime(2025,6,2,tzinfo=timezone.utc))) == 1
    store.close()


def test_simfin_publish_date_becomes_pit_available_at() -> None:
    frame = pd.DataFrame([{
        "Ticker":"TEST","Report Date":"2025-03-31","Publish Date":"2025-05-07",
        "Fiscal Year":2025,"Fiscal Period":"Q1","Revenue":100.0,"Net Income":10.0,
    }])
    rows = SimFinFundamentalsProvider.parse_frame(
        "SEC_TEST",frame,retrieved_at=JUN1,source_document="simfin.csv"
    )
    revenue = next(x for x in rows if x.metric_name=="REVENUE")
    assert revenue.available_at == datetime(2025,5,7,0,0,tzinfo=timezone.utc)
    assert revenue.quality_status is FundamentalQualityStatus.BOOTSTRAP


def test_fmp_accepted_date_is_used_when_present() -> None:
    rows = FMPFundamentalsProvider.parse_statements(
        "SEC_TEST",
        [{
            "date":"2025-03-31","fillingDate":"2025-05-01",
            "acceptedDate":"2025-05-01T20:15:30+00:00","period":"Q1",
            "calendarYear":"2025","revenue":100.0,"netIncome":10.0,
        }],
        statement_type="INCOME",retrieved_at=JUN1,
        source_document="https://financialmodelingprep.com/stable/income-statement",
    )
    revenue = next(x for x in rows if x.metric_name=="REVENUE")
    assert revenue.accepted_at == datetime(2025,5,1,20,15,30,tzinfo=timezone.utc)
    assert revenue.available_at == revenue.accepted_at
    assert revenue.source == "FMP"


def test_ir_provider_requires_https_and_preserves_official_provenance() -> None:
    provider = CompanyInvestorRelationsProvider()
    with pytest.raises(ValueError):
        provider.ingest_structured(
            SECURITY,
            [{"metric_name":"GUIDANCE_REVENUE","value_low":100,"value_high":120,
              "available_at":"2025-05-01T20:00:00Z","source_document":"http://example.com/x.pdf"}],
            retrieved_at=JUN1,
        )
    rows = provider.ingest_structured(
        SECURITY,
        [{"metric_name":"GUIDANCE_REVENUE","value_low":100,"value_high":120,
          "period_end":"2025-06-30","available_at":"2025-05-01T20:00:00Z",
          "source_document":"https://investor.example.com/q1-release.pdf"}],
        retrieved_at=JUN1,
    )
    assert rows[0].source == "COMPANY_IR"
    assert rows[0].quality_status is FundamentalQualityStatus.OFFICIAL_IR
    assert rows[0].validation_status is FundamentalValidationStatus.GUIDANCE_ONLY


def test_guidance_precedence_sec_then_ir_then_secondary(tmp_path: Path) -> None:
    store, repo = _store(tmp_path)
    common = dict(
        security_id="SEC_TEST",metric_name="GUIDANCE_REVENUE",
        period_end=date(2025,6,30),retrieved_at=JUN1,available_at=MAY1,
        quality_status=FundamentalQualityStatus.OFFICIAL_IR,
        validation_status=FundamentalValidationStatus.GUIDANCE_ONLY,
    )
    repo.save_guidance_kpis([
        GuidanceKPI(source="FINNHUB",source_document="https://finnhub.io/x",value=90,**common),
        GuidanceKPI(source="COMPANY_IR",source_document="https://investor.example.com/x",value=100,**common),
        GuidanceKPI(source="SEC_EDGAR",source_document="https://sec.gov/x",value=110,**common),
    ])
    rows=repo.canonical_guidance_as_of("SEC_TEST",datetime(2025,5,2,tzinfo=timezone.utc))
    assert len(rows)==1
    assert rows[0]["source"]=="SEC_EDGAR"
    assert rows[0]["value"]==110.0
    store.close()


def test_snapshot_ttm_requires_four_separate_quarters_and_derives_fcf(tmp_path: Path) -> None:
    store, repo = _store(tmp_path)
    facts=[]
    quarter_ends=[date(2024,6,30),date(2024,9,30),date(2024,12,31),date(2025,3,31)]
    for i,end in enumerate(quarter_ends, start=1):
        start=date(end.year if end.month>3 else end.year-1, {6:4,9:7,12:10,3:1}[end.month], 1)
        facts.extend([
            _fact(value=100*i,source="SEC_EDGAR",available_at=MAY1,accepted_at=MAY1,
                  metric="REVENUE",period_end=end,period_start=start),
            _fact(value=20*i,source="SEC_EDGAR",available_at=MAY1,accepted_at=MAY1,
                  metric="OPERATING_CASH_FLOW",period_end=end,period_start=start),
            _fact(value=5*i,source="SEC_EDGAR",available_at=MAY1,accepted_at=MAY1,
                  metric="CAPEX",period_end=end,period_start=start),
        ])
    repo.save_facts(facts)
    snapshot=FundamentalSnapshotService(repo).snapshot_as_of(
        "SEC_TEST",datetime(2025,5,2,tzinfo=timezone.utc)
    )
    assert snapshot.ttm["REVENUE"] == 1000.0
    assert snapshot.ttm["OPERATING_CASH_FLOW"] == 200.0
    assert snapshot.ttm["CAPEX"] == 50.0
    assert snapshot.ttm["FREE_CASH_FLOW"] == 150.0
    store.close()


def test_phase3_schema_contains_required_lineage_columns(tmp_path: Path) -> None:
    store, _ = _store(tmp_path)
    cols={r["name"] for r in store.connection.execute("PRAGMA table_info(fundamental_facts_source)")}
    required={
        "metric_name","value","period_end","filing_date","accepted_at",
        "source","source_document","accession_number","retrieved_at",
        "quality_status","validation_status","available_at",
    }
    assert required <= cols
    tables={r[0] for r in store.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {
        "filing_records_source","fundamental_facts_source",
        "fundamental_estimates_source","company_kpi_guidance_source",
        "fundamental_validation_results","fundamental_sync_runs",
    } <= tables
    store.close()


def test_future_dated_sec_period_never_leaks_into_historical_snapshot(tmp_path: Path) -> None:
    """SEC files can carry future outlier period_end (e.g. 2039).

    A backdated available_at must NOT turn that value into an as-of input;
    the original archived observation must stay untouched for provenance.
    """
    store, repo = _store(tmp_path)
    repo.save_facts([
        _fact(value=100, source="SEC_EDGAR", available_at=MAY1,
              accepted_at=MAY1, period_end=date(2025,3,31)),
        _fact(value=999999, source="SEC_EDGAR", available_at=MAY1,
              accepted_at=MAY1, period_end=date(2039,8,31),
              period_start=date(2039,1,1), accession="FUTURE_PERIOD"),
    ])
    rows = repo.source_facts_as_of(
        "SEC_TEST", datetime(2025,5,15,23,59,tzinfo=timezone.utc))
    assert [r["value"] for r in rows] == [100]
    canonical = repo.canonical_facts_as_of(
        "SEC_TEST", datetime(2025,5,15,23,59,tzinfo=timezone.utc))
    assert [r["value"] for r in canonical] == [100]
    assert store.connection.execute(
        "SELECT COUNT(*) FROM fundamental_facts_source"
    ).fetchone()[0] == 2
    later = repo.source_facts_as_of(
        "SEC_TEST", datetime(2040,1,1,tzinfo=timezone.utc))
    assert len(later) == 2
    store.close()


def test_fiscal_period_guard_uses_utc_asof_date(tmp_path: Path) -> None:
    """A positive timezone offset must not allow tomorrow's period at UTC dusk."""
    from datetime import timedelta
    store, repo = _store(tmp_path)
    repo.save_facts([
        _fact(value=100, source="SEC_EDGAR",
              available_at=datetime(2025,5,15,tzinfo=timezone.utc),
              period_start=None, period_end=date(2025,5,16))
    ])
    local_asof = datetime(2025,5,16,1,0, tzinfo=timezone(timedelta(hours=9)))
    assert repo.source_facts_as_of("SEC_TEST", local_asof) == []
    store.close()
