"""M10 V10 original frozen S10: SEC-proven annual panel and four-beta DD OLS.

Never recycles Jones S11 cohorts or treats the absence of an XBRL tag as zero.
No S10 score without five original year×SIC×accounting-regime regressions,
audited next-year CFO for every firm, peer five-year AQ and frozen percentile
convention. Research diagnostics do not promote PIT.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
from html.parser import HTMLParser
import json
import math
import re
from pathlib import Path
from typing import Mapping, Sequence
import zipfile

from app.scoring_v8_s8_s10 import TARGETS, fiscal_ends, _annual, _record_key
from app.scoring_v9_s8_s10 import SOURCE_LOCATION, verify_frozen_source

FROZEN_S10_SHA256 = "53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794"
SOURCE_LINES = "1486-1546"
CRMD_10K = {
    2022: {
        "url": ("https://www.sec.gov/Archives/edgar/data/1410098/"
                "000121390023024310/f10k2022_cormedixinc.htm"),
        "sha256": "fe732c01dfb628975779efdb1cfab07faa52f80e9e2a86b2422184870b02ed84",
        "accession": "0001213900-23-024310", "filed": "2023-03-30",
    },
    2023: {
        "url": ("https://www.sec.gov/Archives/edgar/data/1410098/"
                "000121390024021585/ea0201177-10k_cormedix.htm"),
        "sha256": "e4996595c8bec4deec5e1e504dc4cb19035cc218ebc7e97bb8f383c4b361e807",
        "accession": "0001213900-24-021585", "filed": "2024-03-12",
    },
}
_NUMERIC_KEYS = ("tca", "assets_t", "assets_previous",
                 "cfo_previous", "cfo_current", "cfo_next")


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, value: str) -> None:
        if value.strip():
            self.parts.append(value)


def _visible(raw: bytes) -> str:
    parser = _VisibleText()
    parser.feed(raw.decode("utf-8", "replace"))
    return " ".join(" ".join(parser.parts).split())


def _balance_excerpt(body: bytes, first_year: int, revenue_year: int) -> str:
    plain = _visible(body)
    # Must be audited balance-sheet body, not table of contents or narrative.
    candidates = [
        plain[m.start():m.start()+3700]
        for m in re.finditer(r"CONSOLIDATED\s+BALANCE\s+SHEETS", plain, flags=re.I)
    ]
    for excerpt in candidates:
        if (re.search(r"December\s+31,\s*" + str(first_year), excerpt, re.I)
                and re.search(r"Current\s+assets\s+Cash", excerpt, re.I)
                and re.search(r"TOTAL\s+ASSETS", excerpt, re.I)
                and re.search(r"TOTAL\s+LIABILITIES", excerpt, re.I)):
            return excerpt
    raise ValueError("CRMD_FY"+str(revenue_year)+"_AUDITED_CONSOLIDATED_BS_NOT_PROVEN")


def prove_crmd_receivables(body22: bytes, body23: bytes) -> dict:
    """Audited FY2022 reported dash and FY2023 exhaustive no-AR balance sheet."""
    for year, body in ((2022, body22), (2023, body23)):
        if sha256(body).hexdigest() != CRMD_10K[year]["sha256"]:
            raise ValueError(f"CRMD_FY{year}_ORIGINAL_10K_SHA256_CHANGED")
        plain = _visible(body)
        if "cormedix" not in plain.lower() or "FORM" not in plain or "10-K" not in plain:
            raise ValueError(f"CRMD_FY{year}_10K_IDENTITY_MISSING")
    old = _balance_excerpt(body22, 2022, 2022)
    new = _balance_excerpt(body23, 2023, 2023)
    if not re.search(r"Trade\s+receivables,\s*net\s+[-\u2014]\s+45,368", old, re.I):
        raise ValueError("CRMD_2022_AR_DASH_VS_2021_45368_NOT_FOUND")
    if not re.search(r"Total\s+current\s+assets\s+59,551,175\s+66,468,829", old, re.I):
        raise ValueError("CRMD_2022_AUDITED_CURRENT_ASSETS_NOT_FOUND")
    if not re.search(r"Total\s+current\s+assets\s+79,450,400\s+59,551,175", new, re.I):
        raise ValueError("CRMD_2023_AUDITED_CURRENT_ASSETS_NOT_FOUND")
    # FY2023 audited current-asset categories reconcile, but NO explicit AR
    # line exists. Per frozen source evidence policy never turn an absent tag
    # into a numeric AR=0 even when the balance sheet appears exhaustive.
    amounts = (43642684, 77453, 32388130, 2106345, 353574, 882214)
    if "trade receivables" in new.lower():
        raise ValueError("CRMD_2023_UNEXPECTED_RECEIVABLE_ROW")
    if sum(amounts) != 79450400:
        raise ValueError("CRMD_2023_CURRENT_ASSETS_ARITHMETIC_NOT_RECONCILED")
    for amount in amounts:
        if f"{amount:,}" not in new:
            raise ValueError("CRMD_2023_CURRENT_ASSETS_COMPONENT_MISSING:"+str(amount))
    # Borrowing-zero is SEPARATE from A/R: all FY2021–23 current liabilities
    # are itemized, with no loan/note/short-term debt residual.
    if not re.search(
        r"Accounts payable\s+\$?\s*2,202,149\s+\$?\s*2,209,552"
        r"\s+Accrued expenses\s+3,973,941\s+3,014,156"
        r"\s+Operating lease liabilities, short-term\s+134,801\s+121,368"
        r"\s+Total current liabilities\s+6,310,891\s+5,345,076", old, re.I):
        raise ValueError("CRMD_2022_2021_CURRENT_DEBT_ZERO_NOT_PROVEN")
    if not re.search(
        r"Accounts payable\s+\$?\s*4,279,679\s+\$?\s*2,202,149"
        r"\s+Accrued expenses\s+6,970,217\s+3,973,941"
        r"\s+Operating lease liabilities, short-term\s+150,619\s+134,801"
        r"\s+Total current liabilities\s+11,400,515\s+6,310,891", new, re.I):
        raise ValueError("CRMD_2023_2022_CURRENT_DEBT_ZERO_NOT_PROVEN")
    if ((2202149+3973941+134801)!=6310891 or
            (2209552+3014156+121368)!=5345076 or
            (4279679+6970217+150619)!=11400515):
        raise ValueError("CRMD_AUDITED_CURRENT_LIABILITIES_ARITHMETIC_FAILED")
    return {
        "2021": {"receivables_USD": "45368", "source_fy": 2022,
                 "proof": "FY2022_ORIGINAL_10K_COMPARATIVE_REPORTED_45368"},
        "2022": {"receivables_USD": "0", "source_fy": 2022,
                 "proof": "FY2022_ORIGINAL_10K_BALANCE_SHEET_EXPLICIT_DASH"},
        "2023": {"receivables_USD": None, "source_fy": 2023,
                 "proof": "FY2023_AUDITED_BS_OMITS_AR_NUMERIC_ROW_NOT_EQUIVALENT_TO_ZERO",
                 "total_current_assets_reconciles": True,
                 "numeric_AR_value_verified": False},
        "short_term_borrowing_zero_supported_2021_2023": True,
        "zero_debt_scope": "ORIGINAL_CRMD_BALANCE_SHEETS_NO_LOAN_OR_NOTE_CURRENT_ROWS",
        "current_assets_FY2023_reconciliation_USD": str(sum(amounts)),
        "sources": {
            str(y): {"accession": CRMD_10K[y]["accession"],
                     "url": CRMD_10K[y]["url"],
                     "sha256": CRMD_10K[y]["sha256"]}
            for y in (2022, 2023)
        },
        "cash_flow_receivables_change_is_not_balance_receivables": True,
    }


def _year_end(gaap: Mapping, fiscal_anchor: str, year: int) -> str | None:
    if year in range(2021, 2026):
        return fiscal_ends(gaap, fiscal_anchor).get(year)
    anchor = date.fromisoformat(fiscal_anchor)
    hits = set()
    for row in gaap.get("Assets", {}).get("units", {}).get("USD", []):
        try:
            end = date.fromisoformat(row["end"])
        except (KeyError, ValueError, TypeError):
            continue
        if (end.year == year and
                abs((end - date(year, anchor.month, min(anchor.day, 28))).days) <= 45
                and _annual(row, year=year, end=end.isoformat(),
                            flow=False, accession=None)):
            hits.add(end.isoformat())
    return next(iter(hits)) if len(hits) == 1 else None


def _original_accession(gaap: Mapping, *, year: int, end: str | None) -> str | None:
    if end is None:
        return None
    rows = gaap.get("Assets", {}).get("units", {}).get("USD", [])
    hits = {r["accn"] for r in rows if
            _annual(r, year=year, end=end, flow=False, accession=None)
            and r.get("accn")}
    return next(iter(hits)) if len(hits) == 1 else None


def _original_fact(gaap: Mapping, tag: str, *, year: int, end: str | None,
                   accession: str | None, flow: bool) -> dict:
    if not end or not accession:
        return {"status": "ORIGINAL_10K_FISCAL_PERIOD_OR_ACCESSION_NOT_FOUND", "tag": tag}
    rows = gaap.get(tag, {}).get("units", {}).get("USD", [])
    matches = [r for r in rows if _annual(
        r, year=year, end=end, flow=flow, accession=accession)]
    unique = {json.dumps(r, sort_keys=True, separators=(",", ":")): r for r in matches}
    if len(unique) != 1:
        return {"status": "SEC_EXACT_USD_FACT_MISSING_OR_AMBIGUOUS",
                "tag": tag, "matched": len(unique),
                "year": year, "accession": accession}
    row = next(iter(unique.values()))
    return {"status": "SOURCE_EXACT", "tag": tag, "year": year,
            "USD": str(row["val"]), "unit": "USD", "end": end,
            "accession": accession, "filed": row["filed"],
            "record_sha256": _record_key(row)}


def issuer_annual_inventory(ticker: str, raw: bytes,
                            *, crmd_zero_evidence: dict | None = None,
                            years: Sequence[int] = tuple(range(2020, 2027))) -> dict:
    """Immutable member pin and original FY 10-K accession for all required rows."""
    if ticker not in TARGETS or sha256(raw).hexdigest() != TARGETS[ticker]["sha256"]:
        raise ValueError("S10_ORIGINAL_PINNED_COMPANYFACTS_MISMATCH:"+ticker)
    payload = json.loads(raw)
    cfg = TARGETS[ticker]
    if str(payload["cik"]).zfill(10) != cfg["cik"]:
        raise ValueError("S10_CIK_MISMATCH")
    gaap = payload["facts"]["us-gaap"]
    annual = {}
    for year in years:
        end = _year_end(gaap, cfg["fy_end"], year)
        accession = _original_accession(gaap, year=year, end=end)
        rows = {key: _original_fact(gaap, tag, year=year, end=end,
                                    accession=accession, flow=flow)
                for key, tag, flow in (
                    ("assets", "Assets", False),
                    ("current_assets", "AssetsCurrent", False),
                    ("cash_equivalents", "CashAndCashEquivalentsAtCarryingValue", False),
                    ("current_liabilities", "LiabilitiesCurrent", False),
                    ("cfo", "NetCashProvidedByUsedInOperatingActivities", True))}
        debt = {tag: _original_fact(gaap, tag, year=year, end=end,
                                    accession=accession, flow=False)
                for tag in ("ShortTermBorrowings",
                            "ShortTermDebtCurrent",
                            "LongTermDebtCurrent")}
        positive = [name for name,r in debt.items() if r["status"] == "SOURCE_EXACT"]
        if (ticker == "CRMD" and crmd_zero_evidence and year in (2021, 2022, 2023)
              and crmd_zero_evidence.get("short_term_borrowing_zero_supported_2021_2023")):
            debt_result = {"status": "AUDITED_BS_EXHAUSTIVE_ZERO_PROOF",
                           "value_USD": "0",
                           "proof": crmd_zero_evidence[str(year)]["proof"]}
        elif positive:
            # A bare US-GAAP debt tag is not proof that other current
            # interest-bearing borrowing classes do not exist. Do not use
            # a single current note concept as exhaustive short-term debt.
            debt_result = {"status": "DEBT_TAGS_PRESENT_TOTAL_CLASSIFICATION_UNPROVEN",
                           "candidate_tags": positive, "value_USD": None}
        else:
            debt_result = {"status": "MISSING_NONOVERLAPPING_SHORT_TERM_DEBT_PROOF",
                           "value_USD": None}
        annual[year] = {"fy": year, "end": end, "accession": accession,
                        "facts": rows, "short_term_debt": debt_result}
    return {"ticker": ticker, "cik": cfg["cik"],
            "companyfacts_sha256": sha256(raw).hexdigest(),
            "annual": annual}


def tca_dd_design(inventory: Mapping, fiscal_year: int) -> dict:
    """Calculate a *real* target row when every adjacent original fact exists."""
    series = inventory["annual"]
    missing = []
    for y in (fiscal_year-1, fiscal_year, fiscal_year+1):
        if y not in series or not series[y]["accession"]:
            missing.append(f"FY{y}:ORIGINAL_10K_NOT_EVIDENCED")
    if missing:
        return {"status": "MISSING_SOURCE_BOUNDED_ANNUAL_INPUTS",
                "year": fiscal_year, "missing": missing, "row": None}
    amounts = {}
    for y in (fiscal_year-1, fiscal_year):
        for name in ("current_assets", "cash_equivalents", "current_liabilities", "assets"):
            evidence = series[y]["facts"][name]
            if evidence["status"] != "SOURCE_EXACT":
                missing.append(f"FY{y}:{name}:{evidence['status']}")
            else:
                amounts[(y,name)] = Decimal(evidence["USD"])
        debt = series[y]["short_term_debt"]
        if debt.get("value_USD") is None:
            missing.append(f"FY{y}:SHORT_TERM_DEBT:{debt['status']}")
        else:
            amounts[(y,"short_term_debt")] = Decimal(debt["value_USD"])
    for y in (fiscal_year-1, fiscal_year, fiscal_year+1):
        evidence = series[y]["facts"]["cfo"]
        if evidence["status"] != "SOURCE_EXACT":
            missing.append(f"FY{y}:CFO:{evidence['status']}")
        else:
            amounts[(y,"cfo")] = Decimal(evidence["USD"])
    if missing:
        return {"status": "MISSING_SOURCE_BOUNDED_ANNUAL_INPUTS",
                "year": fiscal_year, "missing": sorted(set(missing)), "row": None}
    t, p = fiscal_year, fiscal_year-1
    tca = ((amounts[t,"current_assets"]-amounts[p,"current_assets"])
           -(amounts[t,"cash_equivalents"]-amounts[p,"cash_equivalents"])
           -(amounts[t,"current_liabilities"]-amounts[p,"current_liabilities"])
           +(amounts[t,"short_term_debt"]-amounts[p,"short_term_debt"]))
    denominator = (amounts[t,"assets"]+amounts[p,"assets"])/2
    if denominator <= 0:
        return {"status": "NONPOSITIVE_FROZEN_AVERAGE_ASSETS",
                "year": fiscal_year, "row": None}
    row = {"ticker": inventory["ticker"], "fiscal_year": fiscal_year,
           "tca": str(tca), "assets_t": str(amounts[t,"assets"]),
           "assets_previous": str(amounts[p,"assets"]),
           "cfo_previous": str(amounts[p,"cfo"]),
           "cfo_current": str(amounts[t,"cfo"]),
           "cfo_next": str(amounts[t+1,"cfo"]),
           "normalized": {
               "tca_over_average_assets": str(tca/denominator),
               "cfo_previous": str(amounts[p,"cfo"]/denominator),
               "cfo_current": str(amounts[t,"cfo"]/denominator),
               "cfo_next": str(amounts[t+1,"cfo"]/denominator)},
           "original_accessions": {str(y): series[y]["accession"]
                                   for y in (p,t,t+1)},
           "source_companyfacts_sha256": inventory["companyfacts_sha256"],
           "peer_eligible": False,
           "reason_not_peer_eligible": "DATED_ISSUER_YEAR_SIC_AND_REGIME_NOT_ATTACHED"}
    return {"status": "REAL_ORIGINAL_SEC_ANNUAL_TCA_DESIGN_DIAGNOSTIC",
            "year": t, "row": row, "score": None}


def sic_from_original_10k_header(raw: bytes, *, cik: str, accession: str,
                                 report_date: str) -> dict:
    """Strict original EDGAR SGML header, never current SEC SIC snapshot."""
    head = raw[:250_000].decode("latin-1", "replace").split("</SEC-HEADER>",1)[0]
    patterns = (
        r"ACCESSION NUMBER:\s*(\d{10}-\d{2}-\d{6})",
        r"CONFORMED PERIOD OF REPORT:\s*(\d{8})",
        r"CONFORMED SUBMISSION TYPE:\s*(10-K)\b",
        r"CENTRAL INDEX KEY:\s*(\d{1,10})",
        r"STANDARD INDUSTRIAL CLASSIFICATION:[^\r\n]*\[(\d{4})\]")
    matches = [re.search(p, head) for p in patterns]
    if (not all(matches)
            or matches[0].group(1) != accession
            or matches[1].group(1) != report_date.replace("-","")
            or str(matches[3].group(1)).zfill(10) != str(cik).zfill(10)):
        raise ValueError("S10_FY_ORIGINAL_EDGAR_HEADER_SIC_UNVERIFIED")
    return {"sic": matches[4].group(1), "cik": str(cik).zfill(10),
            "accession": accession, "fiscal_end": report_date,
            "header_sha256": sha256(raw).hexdigest(),
            "historical_classification_verified": True}


def independent_four_beta_decimal(rows: Sequence[Mapping]) -> dict:
    """Four coefficient full-rank Decimal OLS; independent of V9 float OLS."""
    if len(rows) < 20:
        raise ValueError("S10_OLS_UNDER_20_INDEPENDENT_PEERS")
    with localcontext() as ctx:
        ctx.prec = 65
        design = []
        for r in rows:
            amount = [Decimal(str(r[k])) for k in _NUMERIC_KEYS]
            denominator = (amount[1]+amount[2])/2
            if denominator <= 0 or not all(x.is_finite() for x in amount):
                raise ValueError("S10_NONFINITE_OR_NONPOSITIVE_DENOMINATOR")
            design.append(([Decimal(1),amount[3]/denominator,
                            amount[4]/denominator,amount[5]/denominator],
                           amount[0]/denominator))
        A = [[sum((x[i]*x[j] for x,y in design),Decimal(0))
              for j in range(4)] for i in range(4)]
        b = [sum((x[i]*y for x,y in design),Decimal(0)) for i in range(4)]
        # Partial pivoting with a scale gate rejects near-singular designs.
        scale = max(abs(z) for line in A for z in line)
        for i in range(4):
            pivot_index = max(range(i,4),key=lambda k:abs(A[k][i]))
            if abs(A[pivot_index][i]) <= scale*Decimal("1e-25"):
                raise ValueError("S10_RANK_DEFICIENT_FOUR_BETA_OLS")
            A[i],A[pivot_index] = A[pivot_index],A[i]
            b[i],b[pivot_index] = b[pivot_index],b[i]
            for j in range(i+1,4):
                factor = A[j][i]/A[i][i]
                for k in range(i,4):
                    A[j][k] -= factor*A[i][k]
                b[j] -= factor*b[i]
        beta=[Decimal(0)]*4
        for i in range(3,-1,-1):
            beta[i]=(b[i]-sum((A[i][j]*beta[j]
                                  for j in range(i+1,4)),Decimal(0)))/A[i][i]
        return {"beta": tuple(str(x) for x in beta), "peer_count": len(rows),
                "method": "INDEPENDENT_DECIMAL_65_PRECISION_4_BETA_OLS"}


def _peer_full_original_replay(peer: Mapping, year: int) -> dict:
    """Reperform a proposed peer's six DD values from ORIGINAL SEC evidence.

    Rejects bare peer booleans, supplied numerics and old S11 roster strings.
    Currently accepts the most conservative explicit current-borrowing
    classes (short-term borrowing + current LTD) proven independently in the
    same original 10-K. All other classifications stay unavailable.
    """
    raw = peer.get("source_companyfacts_raw")
    body = peer.get("original_10k_body_raw")
    receipt = peer.get("official_10k_receipt")
    headers = peer.get("fy_header_raw")
    if (not isinstance(raw, bytes) or not isinstance(body, bytes)
            or not isinstance(headers, bytes) or not isinstance(receipt, dict)):
        raise ValueError("S10_PEER_ORIGINAL_RAW_SEC_SOURCES_REQUIRED")
    if (sha256(raw).hexdigest() != peer.get("source_companyfacts_sha256")
            or sha256(body).hexdigest() != receipt.get("sha256")
            or receipt.get("http_status") not in (200,206)):
        raise ValueError("S10_PEER_ORIGINAL_SEC_HASH_MISMATCH")
    cik = str(peer["cik"]).zfill(10)
    accession = peer["original_accessions"][str(year)]
    url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
           f"{accession.replace('-','')}/{peer['primary_document']}")
    if receipt.get("url") != url:
        raise ValueError("S10_PEER_BODY_URL_OR_ACCESSION_MISMATCH")
    membership = sic_from_original_10k_header(
        headers, cik=cik, accession=accession, report_date=peer["fiscal_end"])
    if membership["sic"] != peer["historical_sic"]:
        raise ValueError("S10_PEER_SIC_NOT_HISTORICALLY_PROVEN")
    original_body = _visible(body)
    if not re.search(r"generally accepted in the United States of America",
                     original_body, re.I):
        raise ValueError("S10_PEER_US_GAAP_ORIGINAL_AUDITED_REGIME_MISSING")
    obj = json.loads(raw)
    if str(obj.get("cik")).zfill(10) != cik:
        raise ValueError("S10_PEER_COMPANYFACTS_CIK_MISMATCH")
    gaap=obj["facts"]["us-gaap"]
    collected={}
    for y in (year-1, year, year+1):
        accession_y=peer["original_accessions"][str(y)]
        end_y=peer["annual_fiscal_ends"][str(y)]
        expected = _original_accession(gaap, year=y, end=end_y)
        if expected != accession_y:
            raise ValueError("S10_PEER_ORIGINAL_ANNUAL_ACCESSION_NOT_PROVEN")
        for name,tag,flow in (
            ("assets","Assets",False),("current_assets","AssetsCurrent",False),
            ("cash","CashAndCashEquivalentsAtCarryingValue",False),
            ("current_liabilities","LiabilitiesCurrent",False),
            ("cfo","NetCashProvidedByUsedInOperatingActivities",True),
            ("short_term","ShortTermBorrowings",False),
            ("current_debt","LongTermDebtCurrent",False)):
            record=_original_fact(gaap,tag,year=y,end=end_y,
                                  accession=accession_y,flow=flow)
            if record["status"] == "SOURCE_EXACT":
                collected[y,name] = Decimal(record["USD"])
            elif name in (("short_term","current_debt")
                           if y != year+1 else
                           ("assets","current_assets","cash","current_liabilities",
                            "short_term","current_debt")):
                continue
            else:
                raise ValueError(f"S10_PEER_FY{y}_{tag}_RAW_SOURCE_MISSING")
    # Both distinct borrowing classes must be separately present for both
    # years, then reconciled to the actual audited line descriptions.
    for y in (year-1,year):
        for name in ("short_term","current_debt"):
            if (y,name) not in collected:
                raise ValueError("S10_PEER_SHORT_DEBT_SOURCE_OR_ZERO_PROOF_MISSING")
            value=collected[y,name]
            if value < 0 or str(int(value)) not in original_body.replace(",",""):
                raise ValueError("S10_PEER_DEBT_NOT_RECONCILED_TO_OFFICIAL_BODY")
    p,t=year-1,year
    tca=((collected[t,"current_assets"]-collected[p,"current_assets"])
         -(collected[t,"cash"]-collected[p,"cash"])
         -(collected[t,"current_liabilities"]-collected[p,"current_liabilities"])
         +(collected[t,"short_term"]+collected[t,"current_debt"]
           -collected[p,"short_term"]-collected[p,"current_debt"]))
    output = {
        "tca": str(tca), "assets_t": str(collected[t,"assets"]),
        "assets_previous": str(collected[p,"assets"]),
        "cfo_previous": str(collected[p,"cfo"]),
        "cfo_current": str(collected[t,"cfo"]),
        "cfo_next": str(collected[t+1,"cfo"])}
    try:
        matched = all(Decimal(str(peer[k])).is_finite()
                      and Decimal(str(peer[k])) == Decimal(output[k])
                      for k in _NUMERIC_KEYS)
    except (InvalidOperation, TypeError, KeyError, ValueError):
        matched = False
    if not matched:
        raise ValueError("S10_PROPOSED_PEER_NUMBERS_DO_NOT_MATCH_ORIGINAL_SEC")
    return {**output, "cik":cik, "ticker":peer["ticker"],
            "header_sha256":membership["header_sha256"],
            "official_10k_body_sha256":sha256(body).hexdigest()}


def verified_cohort_regression(target: Mapping, peers: Sequence[Mapping],
                               *, required_sic: str, year: int,
                               accounting_regime: str = "US_GAAP") -> dict:
    """Fail-closed annual cohort; requires real header + accession evidence.

    Each peer must carry its raw Companyfacts, original 10-K body/URL receipt,
    original fiscal-year SGML header SIC, and the original surrounding annual
    accessions. All claimed DD numbers are recomputed from those raw sources.
    Merely declared flags, invented rows and reused S11 rosters are ineligible.
    """
    eligible = []
    seen = set()
    for peer in peers:
        if (peer.get("fiscal_year") != year
                or peer.get("historical_sic") != required_sic
                or peer.get("accounting_regime") != accounting_regime
                or not peer.get("source_companyfacts_raw")
                or not peer.get("fy_header_raw")
                or not peer.get("original_10k_body_raw")):
            continue
        try:
            recalculated = _peer_full_original_replay(peer, year)
        except (ValueError,KeyError,TypeError,InvalidOperation):
            continue
        if peer.get("ticker") == target.get("ticker"):
            continue
        if peer["cik"] in seen:
            raise ValueError("S10_DUPLICATE_ELIGIBLE_PEER_CIK")
        seen.add(peer["cik"])
        eligible.append(recalculated)
    if len(eligible) < 20:
        return {"status": "S10_MINIMUM_REAL_DATED_PEERS_NOT_MET",
                "eligible": len(eligible), "minimum": 20, "beta": None,
                "score": None, "candidate_count": len(peers)}
    if any(name not in target for name in _NUMERIC_KEYS):
        return {"status": "S10_TARGET_ORIGINAL_DD_VALUES_MISSING", "score": None}
    result = independent_four_beta_decimal(eligible)
    beta = [Decimal(x) for x in result["beta"]]
    den=(Decimal(str(target["assets_t"]))+Decimal(str(target["assets_previous"])))/2
    if den <= 0:
        raise ValueError("S10_TARGET_AVERAGE_ASSETS_INVALID")
    xv=(Decimal(1),Decimal(str(target["cfo_previous"]))/den,
        Decimal(str(target["cfo_current"]))/den,Decimal(str(target["cfo_next"]))/den)
    resid=Decimal(str(target["tca"]))/den-sum(
        (x*b for x,b in zip(xv,beta)),Decimal(0))
    # Numerically independent legacy float four-coefficient solver agrees
    # with the new high-precision Decimal re-performance, or fail closed.
    from app.scoring_v9_s8_s10 import dd_year_regression
    pseudo_target = {**{k:float(target[k]) for k in _NUMERIC_KEYS},
                     "ticker":target["ticker"], "sic":required_sic,
                     "accounting_regime":accounting_regime,"fiscal_year":year,
                     "membership_source_hash":target["membership_source_hash"],
                     "original_10k_source_hash":target["original_10k_source_hash"],
                     "dated_membership_verified":True,"original_10k_verified":True}
    pseudo_peers=[{**{k:float(p[k]) for k in _NUMERIC_KEYS},
        "ticker":p["cik"],"sic":required_sic,
        "accounting_regime":accounting_regime,"fiscal_year":year,
        "membership_source_hash":p["header_sha256"],
        "original_10k_source_hash":p["official_10k_body_sha256"],
        "dated_membership_verified":True,"original_10k_verified":True}
        for p in eligible]
    reference=dd_year_regression(pseudo_peers,pseudo_target)
    if (reference["status"]!="FROZEN_YEAR_REGRESSION_RESEARCH_DIAGNOSTIC"
            or max(abs(float(a)-float(b))
                   for a,b in zip(beta,reference["beta"])) > 1e-6
            or abs(float(resid)-reference["target_residual"]) > 1e-6):
        raise ValueError("S10_INDEPENDENT_FLOAT_VS_DECIMAL_OLS_MISMATCH")
    return {"status": "S10_ONE_REAL_ANNUAL_PEER_REGRESSION_DIAGNOSTIC",
            "fiscal_year":year, "sic":required_sic,
            "eligible":len(eligible), "beta":result["beta"],
            "target_residual":str(resid), "independent_v9_beta":reference["beta"],
            "score":None}


def full_s10_gate(yearly: Sequence[Mapping], comparable_peer_aq: Sequence[Mapping],
                  *, accepted_percentile_rule: str | None = None) -> dict:
    """The frozen text omits tie-policy; never silently choose a percentile."""
    if (len(yearly)!=5
            or any(y.get("status")!="S10_ONE_REAL_ANNUAL_PEER_REGRESSION_DIAGNOSTIC"
                   for y in yearly)
            or len({y.get("fiscal_year") for y in yearly})!=5):
        return {"status":"S10_FIVE_VERIFIED_INDUSTRY_REGRESSIONS_MISSING",
                "score":None}
    years=sorted(y["fiscal_year"] for y in yearly)
    if years!=list(range(years[0],years[0]+5)):
        return {"status":"S10_NONCONSECUTIVE_RESIDUAL_FISCAL_YEARS","score":None}
    if len(comparable_peer_aq)<20:
        return {"status":"S10_FIVE_YEAR_PEER_AQ_DISTRIBUTION_MISSING","score":None}
    if accepted_percentile_rule is None:
        return {"status":"S10_FROZEN_SIGMA_AND_PERCENTILE_TIE_RULE_UNSPECIFIED",
                "score":None,
                "note":"No full canonical/research score absent original convention"}
    return {"status":"S10_PERCENTILE_METHOD_NOT_IN_ORIGINAL_CONTRACT",
            "score":None}


def audit_original_archive(archive: Path, *, crmd_body22: bytes,
                           crmd_body23: bytes) -> dict:
    verify_frozen_source()
    crmd_proof=prove_crmd_receivables(crmd_body22,crmd_body23)
    stocks={}
    with zipfile.ZipFile(archive) as z:
        for ticker,cfg in TARGETS.items():
            member=z.getinfo(f"CIK{cfg['cik']}.json")
            if member.file_size>40_000_000:
                raise ValueError("S10_ZIP_SEC_MEMBER_LIMIT_EXCEEDED")
            raw=z.read(member)
            inventory=issuer_annual_inventory(
                ticker,raw,crmd_zero_evidence=crmd_proof if ticker=="CRMD" else None)
            years={str(year):tca_dd_design(inventory,year) for year in range(2021,2026)}
            stocks[ticker]={
                "companyfacts_sha256":inventory["companyfacts_sha256"],
                "years":years,
                "original_fiscal_accessions": {
                    str(y):inventory["annual"][y]["accession"] for y in range(2020,2027)},
                "periods":{str(y):inventory["annual"][y]["end"] for y in range(2020,2027)},
                "annual_shortterm_debt_source_status":{
                    str(y):inventory["annual"][y]["short_term_debt"]["status"]
                    for y in range(2021,2026)},
                "verified_five_year_sic_regime_panels":0,
                "full_S10_score":None,
                "missing":[
                    "FROZEN_S10_HISTORICAL_FIVE_DISTINCT_INDUSTRY_ACCOUNTING_REGIME_PANELS",
                    "FROZEN_S10_VERIFIED_PEER_FIVE_YEAR_DD_AQ_DISTRIBUTION",
                    "FROZEN_ORIGINAL_SIGMA_AND_PERCENTILE_TIE_METHOD_NOT_STATED",
                    "FY2025_NEEDS_FY2026_AUDITED_FULL_YEAR_CFO_FOR_ALL_PANEL_MEMBERS"],
                "PIT_accepted":False}
    return {"schema":"MERIDYEN_M10_V10_S10_OFFLINE_REAL_SOURCES_V1",
            "original_frozen_sha256":FROZEN_S10_SHA256,
            "original_frozen_lines":SOURCE_LINES,
            "original_crmd_receivables_2022_2023":crmd_proof,
            "frozen_s10_cohort_key":"ORIGINAL_SEC_YEAR_SIC_x_FILING_ACCOUNTING_REGIME",
            "new_full_research_scores":0, "historical_canonical_PIT_accepted":0,
            "network_requests_for_replay":0,
            "stocks":stocks}
