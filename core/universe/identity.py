from __future__ import annotations

import re
import uuid

from core.contracts.enums import Exchange
from core.universe.models import UniverseRecord


NAMESPACE = uuid.UUID("5ec2dc9b-8e3d-4a87-9e9d-e8ab430a763d")

MIC_TO_EXCHANGE = {
    "XNAS": Exchange.NASDAQ,
    "XNYS": Exchange.NYSE,
    "XASE": Exchange.AMEX,
    "OTCM": Exchange.OTC,
    "BATS": Exchange.CBOE,
}

SEC_EXCHANGE_TO_EXCHANGE = {
    "nasdaq": Exchange.NASDAQ,
    "nasdaq global select market": Exchange.NASDAQ,
    "nasdaq global market": Exchange.NASDAQ,
    "nasdaq capital market": Exchange.NASDAQ,
    "nyse": Exchange.NYSE,
    "new york stock exchange": Exchange.NYSE,
    "nyse american": Exchange.AMEX,
    "nyse american llc": Exchange.AMEX,
    "amex": Exchange.AMEX,
    "otc": Exchange.OTC,
    "cboe": Exchange.CBOE,
}

EXCHANGE_TO_MIC = {
    Exchange.NASDAQ: "XNAS",
    Exchange.NYSE: "XNYS",
    Exchange.AMEX: "XASE",
    Exchange.OTC: "OTCM",
    Exchange.CBOE: "BATS",
}


def normalize_ticker(value: str) -> str:
    return value.strip().upper().replace(" ", "")


def normalize_cik(value: str | int | None) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    digits = re.sub(r"\D", "", str(value))
    if not digits:
        return None
    return digits.zfill(10)


def normalize_name(value: str) -> str:
    text = re.sub(r"[^A-Z0-9]+", " ", value.upper()).strip()
    return re.sub(r"\s+", " ", text)


def exchange_from_mic(mic: str | None) -> Exchange | None:
    if not mic:
        return None
    return MIC_TO_EXCHANGE.get(mic.strip().upper())


def exchange_from_sec_name(value: str | None) -> Exchange | None:
    if not value:
        return None
    return SEC_EXCHANGE_TO_EXCHANGE.get(value.strip().lower())


def stable_security_key(record: UniverseRecord) -> str:
    if record.share_class_figi:
        return f"SCFIGI:{record.share_class_figi.strip().upper()}"
    if record.composite_figi:
        return f"CFIGI:{record.composite_figi.strip().upper()}"
    cik = normalize_cik(record.cik)
    if cik:
        return f"CIKNAME:{cik}:{record.exchange.value}:{normalize_name(record.name)}"
    return (
        f"LISTING:{record.exchange.value}:"
        f"{normalize_ticker(record.ticker)}:{normalize_name(record.name)}"
    )


def stable_security_id(record: UniverseRecord) -> str:
    return "SEC_" + uuid.uuid5(NAMESPACE, stable_security_key(record)).hex.upper()
