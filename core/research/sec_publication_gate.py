"""SEC EDGAR acceptance timestamp versus actual public dissemination/PIT usability.

An EDGAR index's Accepted timestamp establishes a lower bound for public
availability; it does NOT prove actual dissemination or a vendor ingestion
timestamp. Never substitute financial statement period-end for available_at.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

@dataclass(frozen=True)
class SECFileAcceptance:
    ticker: str
    cik: str
    accession: str
    form: str
    reported_period_end: str
    sec_index_accepted_et: str
    sec_index_url: str

    @property
    def sec_accepted_at_utc(self) -> datetime:
        local = datetime.fromisoformat(self.sec_index_accepted_et)
        if local.utcoffset() is None:
            raise ValueError("SEC acceptance must have an explicit UTC offset")
        return local.astimezone(timezone.utc)

    def usable_for_model(
        self, *, observed_public_dissemination_at: datetime | None,
        feature_available_at: datetime | None, decision_at: datetime,
    ) -> bool:
        """Fail closed until independent real publication and feature clocks exist."""
        clocks = (observed_public_dissemination_at, feature_available_at, decision_at)
        if any(x is None or x.tzinfo is None or x.utcoffset() is None
               for x in clocks):
            return False
        disseminated, available, decision = (
            x.astimezone(timezone.utc) for x in clocks
        )
        return (
            self.sec_accepted_at_utc <= disseminated
            <= available <= decision
        )

# Exactly three explicitly SEC-index-observed historical accession acceptance
# stamps. This is NOT a complete issuer or financial disclosure event feed.
OBSERVED_ACCEPTANCES: tuple[SECFileAcceptance, ...] = (
    SECFileAcceptance(
        ticker="HUYA",cik="0001728190",accession="0001410578-25-000781",
        form="20-F",reported_period_end="2024-12-31",
        sec_index_accepted_et="2025-04-17T06:43:22-04:00",
        sec_index_url="https://www.sec.gov/Archives/edgar/data/1728190/000141057825000781/0001410578-25-000781-index.htm"),
    SECFileAcceptance(
        ticker="TDG",cik="0001260221",accession="0001260221-24-000083",
        form="10-K",reported_period_end="2024-09-30",
        sec_index_accepted_et="2024-11-07T16:05:07-05:00",
        sec_index_url="https://www.sec.gov/Archives/edgar/data/1260221/000126022124000083/0001260221-24-000083-index.htm"),
    SECFileAcceptance(
        ticker="B",cik="0000009984",accession="0000009984-24-000130",
        form="8-K",reported_period_end="2024-10-25",
        sec_index_accepted_et="2024-10-25T06:47:43-04:00",
        sec_index_url="https://www.sec.gov/Archives/edgar/data/9984/000000998424000130/0000009984-24-000130-index.htm"),
)
