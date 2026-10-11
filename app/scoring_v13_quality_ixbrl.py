"""Inspect sealed original INOD filing iXBRL without assigning absent values."""
from __future__ import annotations

from hashlib import sha256
from html.parser import HTMLParser
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re


WATCH = re.compile(r"inventor|preferredstock|shortterminvest|longterminvest|marketablesecur|debtcurrent|debtnoncurrent", re.I)
PINS = {
    "0001104659-26-020655": ("2d5dd7f964d0239ea18a982f24e077d1b8e0f08baa73fd28dd66f539d9befba2",
        "https://www.sec.gov/Archives/edgar/data/903651/000110465926020655/inod-20251231x10k.htm"),
    "0001410578-25-000194": ("a2c0241be84173898a65f43480a16346704f6d61786e3ab4feff61886d973031",
        "https://www.sec.gov/Archives/edgar/data/903651/000141057825000194/inod-20241231x10k.htm"),
}


class _Facts(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict] = []
        self.current: dict | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "ix:nonfraction":
            return
        data = dict(attrs)
        name = data.get("name") or ""
        if WATCH.search(name):
            self.current = {"name": name, "context": data.get("contextref"),
                            "unit": data.get("unitref"), "scale": data.get("scale"),
                            "nil": data.get("xs:nil"), "format": data.get("format"),
                            "sign": data.get("sign"), "id": data.get("id"), "text": ""}

    def handle_data(self, data: str) -> None:
        if self.current is not None:
            self.current["text"] += data

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "ix:nonfraction" and self.current is not None:
            self.current["text"] = " ".join(self.current["text"].split())
            self.rows.append(self.current)
            self.current = None


def _monetary_candidate(row: dict) -> dict | None:
    """Decode an explicit USD iXBRL numeric fact, retaining lexical caveats."""
    if row["name"] != "us-gaap:OtherShortTermInvestments" or row["nil"] is not None:
        return None
    if not row.get("unit", "").startswith("Unit_Standard_USD"):
        return None
    try:
        raw = Decimal(row["text"].replace(",", ""))
        scale = int(row["scale"] or "0")
        if not -18 <= scale <= 18:
            return None
        value = raw * (Decimal(10) ** scale)
        if row.get("sign") == "-":
            value = -value
    except (InvalidOperation, ValueError):
        return None
    context = row.get("context") or ""
    m = re.fullmatch(r"As_Of_(\d{1,2})_(\d{1,2})_(\d{4})_[^\s]+", context)
    if not m:
        return None
    month, day, year = map(int, m.groups())
    return {"period_end": f"{year:04d}-{month:02d}-{day:02d}",
            "value_usd": str(value), "original_text": row["text"],
            "scale": scale, "context": context, "fact_id": row.get("id"),
            "classification_accepted": False}


def inspect_filing(body_path: Path, receipt_path: Path) -> dict:
    body = body_path.read_bytes()
    receipt = json.loads(receipt_path.read_bytes())
    digest = sha256(body).hexdigest()
    if digest != receipt.get("sha256") or len(body) != receipt.get("bytes"):
        raise ValueError("original filing body seal mismatch")
    accession = receipt.get("accession")
    if (receipt.get("form") != "10-K" or accession not in PINS or
            digest != PINS[accession][0] or receipt.get("source_ref") != PINS[accession][1] or
            accession.replace("-", "") not in body_path.name or "inod" not in body_path.name.lower()):
        raise ValueError("wrong filing identity")
    parser = _Facts()
    parser.feed(body.decode("utf-8"))
    tags = sorted({row["name"] for row in parser.rows})
    candidates = [value for row in parser.rows if (value := _monetary_candidate(row)) is not None]
    return {"accession": receipt["accession"], "body_sha256": digest,
            "source_ref": receipt["source_ref"],
            "watched_fact_rows": parser.rows, "watched_tags": tags,
            "short_term_investment_monetary_candidates": candidates,
            "inventory_tag_absent": not any("inventor" in tag.lower() for tag in tags),
            "inventory_value_inferred_zero": False,
            "accounting_classification_accepted": False}
