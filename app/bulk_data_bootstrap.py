from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import httpx

from app.bootstrap import AppContainer
from core.fundamentals.metrics import XBRL_CANONICAL_ALIASES
from data.providers.sec_access import resolve_sec_user_agent
from data.providers.sec_edgar_fundamentals import SECEdgarFundamentalsProvider
from data.providers.stooq_price import StooqPriceProvider
from data.repositories.fundamental_repository import FundamentalRepository
from data.repositories.price_repository import PriceRepository
from data.repositories.security_repository import SecurityRepository
from data.storage.parquet_price_store import ParquetPriceStore


SEC_COMPANYFACTS_ZIP = (
    "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip"
)
STOOQ_BULK_PAGE = "https://stooq.com/db/h/"


@dataclass(frozen=True)
class BulkBootstrapResult:
    sec_securities: int = 0
    sec_facts: int = 0
    stooq_series: int = 0
    stooq_bars: int = 0


def _canonical_metric_names() -> set[str]:
    return set(XBRL_CANONICAL_ALIASES)


def _download(
    url: str,
    destination: Path,
    *,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 180.0,
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(destination.suffix + ".part")
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        with client.stream("GET", url, headers=headers or {}) as response:
            response.raise_for_status()
            with tmp.open("wb") as handle:
                for chunk in response.iter_bytes(1024 * 1024):
                    if chunk:
                        handle.write(chunk)
    tmp.replace(destination)
    return destination


def discover_stooq_us_daily_ascii_url(html: str, *, base_url: str = STOOQ_BULK_PAGE) -> str:
    hrefs = re.findall(r"""href\s*=\s*["']([^"']+\.zip(?:\?[^"']*)?)["']""", html, flags=re.I)
    if not hrefs:
        raise RuntimeError("Stooq bulk page contains no ZIP links")

    def rank(href: str) -> tuple[int, int, str]:
        low = href.lower()
        score = 0
        if "us" in low:
            score += 10
        if "txt" in low or "ascii" in low:
            score += 6
        if "daily" in low or "/d/" in low:
            score += 4
        if re.search(r"(?:^|[/_-])2[_-]?us", low):
            score += 8
        return (-score, len(href), href)

    best = sorted(hrefs, key=rank)[0]
    if "us" not in best.lower():
        raise RuntimeError("Could not identify a U.S. Stooq bulk ZIP")
    return urljoin(base_url, best)


def download_stooq_us_daily_ascii(destination: Path) -> Path:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/154.0.0.0 Safari/537.36"
        )
    }
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        response = client.get(STOOQ_BULK_PAGE, headers=headers)
        response.raise_for_status()
        url = discover_stooq_us_daily_ascii_url(response.text)
    return _download(url, destination, headers=headers, timeout_seconds=300.0)


def import_sec_companyfacts_zip(app: AppContainer, zip_path: str | Path) -> tuple[int, int]:
    path = Path(zip_path)
    if not path.exists():
        raise FileNotFoundError(path)

    rows = app.sqlite.connection.execute(
        """
        SELECT security_id,cik
        FROM security_master
        WHERE cik IS NOT NULL AND cik<>''
        """
    ).fetchall()
    cik_to_security: dict[str, str] = {}
    for row in rows:
        digits = "".join(ch for ch in str(row["cik"]) if ch.isdigit())
        if digits:
            cik_to_security[digits.zfill(10)] = str(row["security_id"])

    canonical = _canonical_metric_names()
    repository = FundamentalRepository(app.sqlite)
    retrieved_at = datetime.now(timezone.utc)
    securities = 0
    facts_saved = 0

    with zipfile.ZipFile(path) as archive:
        for member in archive.namelist():
            name = Path(member).name
            match = re.fullmatch(r"CIK(\d{10})\.json", name, flags=re.I)
            if not match:
                continue
            cik = match.group(1)
            security_id = cik_to_security.get(cik)
            if security_id is None:
                continue
            with archive.open(member) as handle:
                payload = json.load(handle)

            parsed = SECEdgarFundamentalsProvider.parse_companyfacts_payload(
                security_id,
                cik,
                payload,
                filing_map={},
                retrieved_at=retrieved_at,
                companyfacts_url=(
                    f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
                ),
            )
            facts = [row for row in parsed if row.metric_name in canonical]
            if not facts:
                continue
            facts_saved += repository.save_facts(facts)
            securities += 1

    return securities, facts_saved


def ensure_sec_companyfacts_bulk(
    app: AppContainer,
    *,
    minimum_coverage_ratio: float = 0.70,
) -> tuple[int, int]:
    universe = app.sqlite.connection.execute(
        """
        SELECT COUNT(*) AS n
        FROM security_master
        WHERE market='US' AND exchange IN ('NASDAQ','NYSE','AMEX') AND active=1
        """
    ).fetchone()
    total = int(universe["n"] or 0)
    if total <= 0:
        return 0, 0

    covered = app.sqlite.connection.execute(
        """
        SELECT COUNT(DISTINCT f.security_id) AS n
        FROM fundamental_facts_source f
        JOIN security_master s ON s.security_id=f.security_id
        WHERE f.source='SEC_EDGAR'
          AND s.market='US'
          AND s.exchange IN ('NASDAQ','NYSE','AMEX')
          AND s.active=1
        """
    ).fetchone()
    current = int(covered["n"] or 0)
    if current / total >= minimum_coverage_ratio:
        return current, 0

    bulk_dir = app.resolve_data_path("bulk/sec")
    zip_path = bulk_dir / "companyfacts.zip"
    marker = bulk_dir / "companyfacts-import.json"

    # A successful import can be reused. The regular per-security SEC mirror and
    # background sync remain responsible for incremental freshness.
    if marker.exists() and zip_path.exists():
        try:
            payload = json.loads(marker.read_text(encoding="utf-8"))
            if int(payload.get("securities", 0)) / total >= minimum_coverage_ratio:
                return int(payload.get("securities", 0)), 0
        except Exception:
            pass

    user_agent = resolve_sec_user_agent()
    _download(
        SEC_COMPANYFACTS_ZIP,
        zip_path,
        headers={
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
        },
        timeout_seconds=300.0,
    )
    securities, facts = import_sec_companyfacts_zip(app, zip_path)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json.dumps(
            {
                "imported_at": datetime.now(timezone.utc).isoformat(),
                "securities": securities,
                "facts": facts,
                "source": SEC_COMPANYFACTS_ZIP,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return securities, facts


def import_stooq_bulk_for_scanner(app: AppContainer, zip_path: str | Path) -> tuple[int, int]:
    security_repo = SecurityRepository(app.sqlite)
    price_repo = PriceRepository(
        app.sqlite,
        ParquetPriceStore(app.resolve_data_path(app.app_config.database.parquet_root)),
    )
    provider = StooqPriceProvider()
    series_count = 0
    bars_count = 0

    for group in provider.iter_bulk_zip_series(
        zip_path,
        security_lookup=lambda ticker: security_repo.lookup_security_id(ticker=ticker),
    ):
        if not group:
            continue
        descriptor = price_repo.save_series(group)
        # Stooq stays BOOTSTRAP/RAW_ONLY. This selection is only for current
        # scanner/visualization support and is never authoritative backtest data.
        price_repo.select_series(
            security_id=descriptor.security_id,
            start=descriptor.start_date,
            end=descriptor.end_date,
            source=descriptor.source,
            source_symbol=descriptor.source_symbol,
            purpose="SCANNER_BOOTSTRAP",
            reason="Stooq bulk raw-only scanner bootstrap; not authoritative backtest evidence",
        )
        series_count += 1
        bars_count += len(group)

    return series_count, bars_count
