from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from core.historical.s16_evidence import (
    S16AttentionRecord,
    S16FeatureEvidenceRecord,
    S16ShortInterestRecord,
)
from core.historical.s16_reconstruction import (
    DIRECT_EVIDENCE_FEATURES,
    S16HistoricalFeatureReconstructor,
    S16RawHistoricalObservation,
)
from data.database.sqlite_store import SQLiteStore
from data.providers.sec_edgar_fundamentals import SECEdgarFundamentalsProvider
from data.repositories.s16_evidence_repository import S16EvidenceRepository


def _seed_security(store: SQLiteStore) -> None:
    now = datetime.now(timezone.utc).isoformat()
    store.connection.execute(
        """
        INSERT INTO security_master (
            security_id,ticker,name,exchange,market,active,created_at,updated_at,
            security_type,source_scope,source_priority
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "SEC_TEST","TEST","Test Corp","NASDAQ","US",1,now,now,
            "CS","CANONICAL",1,
        ),
    )
    store.connection.commit()


def test_s16_phase3_schema_and_pit_short_interest(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "phase3.db")
    store.initialize()
    _seed_security(store)
    tables = {
        row[0]
        for row in store.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert {
        "s16_short_interest_source",
        "s16_attention_source",
        "s16_feature_evidence_source",
    } <= tables

    repo = S16EvidenceRepository(store)
    available = datetime(2024, 1, 18, 12, tzinfo=timezone.utc)
    repo.save_short_interest(S16ShortInterestRecord(
        security_id="SEC_TEST",
        ticker="TEST",
        settlement_date=date(2024, 1, 15),
        short_interest=1_000_000,
        avg_daily_volume=250_000,
        float_shares=5_000_000,
        days_to_cover=4.0,
        available_at=available,
        source="TEST_ARCHIVE",
        source_ref="test://short/1",
        quality_status="TEST",
    ))
    assert repo.latest_short_interest_as_of(
        "SEC_TEST", datetime(2024, 1, 18, 11, tzinfo=timezone.utc)
    ) is None
    row = repo.latest_short_interest_as_of(
        "SEC_TEST", datetime(2024, 1, 18, 13, tzinfo=timezone.utc)
    )
    assert row is not None
    assert float(row["short_interest"]) == 1_000_000


def test_s16_reconstruction_is_complete_only_with_real_external_evidence(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "recon.db")
    store.initialize()
    _seed_security(store)
    repo = S16EvidenceRepository(store)

    as_of = datetime(2024, 2, 1, 23, 59, tzinfo=timezone.utc)
    repo.save_short_interest(S16ShortInterestRecord(
        security_id="SEC_TEST",
        ticker="TEST",
        settlement_date=date(2024, 1, 31),
        short_interest=1_500_000,
        avg_daily_volume=250_000,
        float_shares=5_000_000,
        days_to_cover=6.0,
        available_at=datetime(2024, 2, 1, 12, tzinfo=timezone.utc),
        source="TEST_ARCHIVE",
        source_ref="test://short/2",
        quality_status="TEST",
    ))

    for channel in ("SOCIAL", "NEWS"):
        for days_ago in range(2, 22):
            observed = as_of - timedelta(days=days_ago)
            repo.save_attention(S16AttentionRecord(
                security_id="SEC_TEST",
                ticker="TEST",
                channel=channel,
                observed_at=observed,
                available_at=observed,
                mentions=10.0,
                unique_authors=8.0,
                sentiment=0.1,
                source="TEST_ARCHIVE",
                source_ref=f"test://{channel}/{days_ago}",
                quality_status="TEST",
            ))
        recent = as_of - timedelta(hours=2)
        repo.save_attention(S16AttentionRecord(
            security_id="SEC_TEST",
            ticker="TEST",
            channel=channel,
            observed_at=recent,
            available_at=recent,
            mentions=100.0,
            unique_authors=50.0,
            sentiment=0.5,
            source="TEST_ARCHIVE",
            source_ref=f"test://{channel}/recent",
            quality_status="TEST",
        ))

    values = {
        "ownership_lock": 70.0,
        "catalyst": 85.0,
        "regime_sympathy": 65.0,
        "catalyst_proximity": 75.0,
        "theme": 60.0,
        "dilution_risk": 0.20,
        "manipulation_risk": 0.10,
    }
    assert set(values) == DIRECT_EVIDENCE_FEATURES
    for key, value in values.items():
        observed = as_of - timedelta(hours=3)
        repo.save_feature_evidence(S16FeatureEvidenceRecord(
            security_id="SEC_TEST",
            ticker="TEST",
            feature_key=key,
            observed_at=observed,
            available_at=observed,
            value=value,
            source="TEST_ARCHIVE",
            source_ref=f"test://feature/{key}",
            quality_status="TEST",
        ))

    raw = S16RawHistoricalObservation(
        security_id="SEC_TEST",
        ticker="TEST",
        as_of=as_of,
        float_shares=5_000_000,
        price=2.0,
        last_volume=2_000_000,
        avg_volume20=250_000,
        volatility10=0.03,
        volatility20=0.05,
        volatility60=0.08,
        return_1d=0.20,
        momentum5=0.30,
        momentum20=0.10,
        supply_kind="FREE_FLOAT",
        source_quality="PIT_EXACT",
    )
    snapshot = S16HistoricalFeatureReconstructor(repo).reconstruct_batch([raw])[0]
    assert snapshot.score_ready is True
    assert snapshot.missing == ()
    assert snapshot.features["market_cap_scarcity"] == 50.0
    assert snapshot.features["short_pressure"] == 50.0
    assert snapshot.features["social_velocity"] == 50.0
    assert snapshot.features["news_velocity"] == 50.0
    assert snapshot.features["catalyst"] == 85.0


def test_sec_s16_event_forms_are_filings_not_xbrl_facts() -> None:
    submissions = {
        "filings": {
            "recent": {
                "form": ["S-3", "8-K"],
                "filingDate": ["2024-01-10", "2024-01-11"],
                "acceptanceDateTime": ["2024-01-10T14:00:00Z", "2024-01-11T15:00:00Z"],
                "accessionNumber": ["0000000000-24-000001", "0000000000-24-000002"],
                "primaryDocument": ["s3.htm", "8k.htm"],
                "reportDate": ["", "2024-01-11"],
            }
        }
    }
    filings = SECEdgarFundamentalsProvider.parse_submissions_payload(
        "SEC_TEST",
        "0000000001",
        submissions,
        retrieved_at=datetime(2024, 1, 12, tzinfo=timezone.utc),
    )
    assert [item.form_type for item in filings] == ["S-3", "8-K"]

    companyfacts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "val": 123,
                                "end": "2024-01-10",
                                "filed": "2024-01-10",
                                "form": "S-3",
                                "accn": "0000000000-24-000001",
                            },
                            {
                                "val": 456,
                                "end": "2024-01-11",
                                "filed": "2024-01-11",
                                "form": "8-K",
                                "accn": "0000000000-24-000002",
                            },
                        ]
                    }
                }
            }
        }
    }
    filing_map = {item.accession_number: item for item in filings if item.accession_number}
    facts = SECEdgarFundamentalsProvider.parse_companyfacts_payload(
        "SEC_TEST",
        "0000000001",
        companyfacts,
        filing_map=filing_map,
        retrieved_at=datetime(2024, 1, 12, tzinfo=timezone.utc),
        companyfacts_url="https://data.sec.gov/test",
    )
    assert len(facts) == 1
    assert facts[0].form_type == "8-K"
