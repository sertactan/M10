"""Frozen-source S8 / S10 calculation primitives and pinned offline evidence.

Research-only. This tool has no SEC/FRED network client, never updates a DB,
and does not invent FFO, dated SIC cohorts, future CFO or missing values.
"""
from __future__ import annotations

from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import pstdev, stdev
from collections.abc import Mapping, Sequence
import zipfile

from app.scoring_v8_s8_s10 import TARGETS, audit_payload, fiscal_ends, _annual, _record_key

FROZEN_SOURCE_SHA256 = "53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794"
SOURCE_LOCATION = (Path.home() / ".codex/plugins/cache/created-by-me-remote/"
                   "meridyen-equity-research/0.28.1/skills/meridyen-equity-research/"
                   "references/models/S1_S2_S14_CANONICAL_SOURCE.md")
FRED_SERIES = "A001RD3A086NBEA"
FRED_URL = "https://fred.stlouisfed.org/data/A001RD3A086NBEA"
FRED_SNAPSHOT = "BEA_FRED_ANNUAL_2017_EQ_100_OBSERVED_2026_09_30"
# Explicitly transcribed from the official BEA/FRED *current revised* table,
# not a byte-pinned first-release/vintage dataset: NO historical PIT status.
ANNUAL_FRED_CURRENT_REVISED = {1968: 18.246, 2023: 122.361, 2024: 125.496}
FROZEN_LINES = {"S8": "1325-1442", "S10": "1486-1544"}
DEFAULT_MIN_PEERS = 20


def verify_frozen_source(path: Path = SOURCE_LOCATION) -> str:
    """Hash the original plugin bundle; no substitute contract permitted."""
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("FROZEN_ORIGINAL_SOURCE_MISSING")
    h = sha256(path.read_bytes()).hexdigest()
    if h != FROZEN_SOURCE_SHA256:
        raise ValueError("FROZEN_ORIGINAL_SOURCE_SHA256_MISMATCH")
    return h


def gnp_size(total_assets_dollars: float, balance_year: int) -> dict:
    """Ohlson original SIZE: ln(assets / GNP index), preceding-year convention.

    Rescale annual BEA 2017=100 observations to 1968=100. This is a *revised*
    2026 diagnostic, never an as-of-2024 or as-of-2025 vintage declaration.
    """
    if not math.isfinite(total_assets_dollars) or total_assets_dollars <= 0:
        raise ValueError("SIZE assets must be positive dollars")
    baseline = ANNUAL_FRED_CURRENT_REVISED[1968]
    prior_year = balance_year - 1
    if prior_year not in ANNUAL_FRED_CURRENT_REVISED:
        raise ValueError("GNP_PRECEDING_YEAR_OBSERVATION_UNAVAILABLE")
    current = ANNUAL_FRED_CURRENT_REVISED[prior_year]
    index_1968 = 100 * current / baseline
    return {
        "SIZE": math.log(total_assets_dollars / index_1968),
        "assets_dollars": total_assets_dollars,
        "gnp_previous_calendar_year": prior_year,
        "gnp_2017_base": current, "gnp_1968_2017_base": baseline,
        "gnp_rebased_1968_eq_100": index_1968,
        "fred_series": FRED_SERIES, "source": FRED_URL,
        "snapshot": FRED_SNAPSHOT, "raw_fred_response_hash": None,
        "historical_as_of_vintage_verified": False,
        "source_status": "OFFICIAL_WEB_VALUES_TRANSCRIBED_CURRENT_REVISED_RESEARCH_ONLY",
    }


def _required_number(value: object) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("Missing numerical accounting input")
    f = float(value)
    if not math.isfinite(f):
        raise ValueError("Nonfinite accounting input")
    return f


def ohlson_components(*, assets: float, liabilities: float, ca: float, cl: float,
                      net_income: float, prior_net_income: float,
                      ffo: float | None, balance_year: int) -> dict:
    """Exact frozen Ohlson nine-factor logits; FFO absent -> score remains N/A."""
    a, l, ca, cl, ni, old_ni = map(_required_number,
                                  (assets, liabilities, ca, cl, net_income, prior_net_income))
    if a <= 0 or l <= 0 or ca <= 0:
        raise ValueError("Unusable original denominator: assets/liabilities/current assets")
    index = gnp_size(a, balance_year)
    denom = abs(ni) + abs(old_ni)
    if denom == 0:
        return {"status": "SPEC_EDGE_CASE_CHIN_ZERO_DENOMINATOR",
                "score": None, "size": index}
    x = {"SIZE": index["SIZE"], "TLTA": l/a, "WCTA": (ca-cl)/a, "CLCA": cl/ca,
         "OENEG": int(l > a), "NITA": ni/a,
         "INTWO": int(ni < 0 and old_ni < 0),
         "CHIN": (ni-old_ni)/denom}
    if ffo is None:
        return {"status": "MISSING_ORIGINAL_FFO", "score": None,
                "numeric_frozen_ohlson_components": x, "FUTL": None,
                "size": index,
                "required": ["original filing-backed FundsFromOperations",
                             "Altman Z issuer class + inputs",
                             "historical GNP vintage for canonical replay"]}
    x["FUTL"] = _required_number(ffo) / l
    linear = (-1.32 - .407*x["SIZE"] + 6.03*x["TLTA"] - 1.43*x["WCTA"]
              + .0757*x["CLCA"] - 1.72*x["OENEG"] - 2.37*x["NITA"]
              - 1.83*x["FUTL"] + .285*x["INTWO"] - .521*x["CHIN"])
    probability = 1 / (1 + math.exp(-linear)) if linear >= 0 else math.exp(linear)/(1+math.exp(linear))
    return {"status": "OHLSON_NUMERIC_DIAGNOSTIC_ONLY", "score": None,
            "frozen_O": linear, "frozen_O_Q": 100*(1-probability),
            "numeric_frozen_ohlson_components": x, "size": index,
            "requires_for_S8": ["Altman Z score", "historically admissible inputs"]}


def _exact_gaap_value(gaap: Mapping, tag: str, year: int, end: str | None,
                      flow: bool, accession: str | None = None) -> dict:
    if not end:
        return {"status": "FISCAL_END_UNVERIFIED", "tag": tag}
    rows = gaap.get(tag, {}).get("units", {}).get("USD", [])
    found = [r for r in rows if isinstance(r, dict)
             and _annual(r, year=year, end=end, flow=flow, accession=accession)]
    unique = {json.dumps(row, sort_keys=True, separators=(",", ":")): row for row in found}
    if len(unique) != 1:
        return {"status": "ABSENT_OR_AMBIGUOUS_ORIGINAL_10K_FACT", "tag": tag,
                "matched_rows": len(unique), "year": year}
    row = next(iter(unique.values()))
    return {"status": "EXACT_ORIGINAL_10K_FACT_RESEARCH", "value": row["val"], "unit": "USD",
            "tag": tag, "year": year, "end": end, "accession": row.get("accn"),
            "filed": row.get("filed"), "record_sha256": _record_key(row),
            "public_availability_verified": False}


def crmd_receivables(gaap: Mapping, ends: Mapping) -> dict:
    """Targeted source records; 2021 alternate tag is real, 2022/23 N/A."""
    tags = ("AccountsReceivableNetCurrent", "AccountsReceivableNet",
            "OtherReceivablesNetCurrent", "IncreaseDecreaseInReceivables")
    found = {}
    for year in (2021, 2022, 2023):
        end = ends.get(year)
        found[str(year)] = {
            tag: _exact_gaap_value(gaap, tag, year, end,
                                   flow=tag.startswith("IncreaseDecrease"))
            for tag in tags
        }
    return {
        "years": found, "FY2021_net_receivables_fallback":
        found["2021"]["AccountsReceivableNet"],
        "FY2022_2023_receivables_verified": False,
        "accounting_equivalence_to_current_tag_verified": False,
        "note": "Cash-flow change in receivables is not a verified balance-sheet receivable amount.",
    }


def tca_change(*, ca_t: float, ca_previous: float,
               cash_t: float, cash_previous: float,
               cl_t: float, cl_previous: float,
               st_debt_t: float, st_debt_previous: float) -> float:
    """Original Dechow-Dichev TCA delta, no plug or zero-default for debt."""
    values = [_required_number(v) for v in (ca_t, ca_previous, cash_t,
              cash_previous, cl_t, cl_previous, st_debt_t, st_debt_previous)]
    return ((values[0] - values[1]) - (values[2] - values[3])
            - (values[4] - values[5]) + (values[6] - values[7]))


def dd_row(*, tca: float, assets_t: float, assets_previous: float,
           cfo_previous: float, cfo_current: float, cfo_next: float) -> tuple[float, ...]:
    """One authentic regression design row; average assets per frozen preference."""
    values = [_required_number(x) for x in
              (tca, assets_t, assets_previous, cfo_previous, cfo_current, cfo_next)]
    denom = (values[1] + values[2]) / 2
    if denom <= 0:
        raise ValueError("DD average assets not positive")
    return (1.0, values[3]/denom, values[4]/denom, values[5]/denom, values[0]/denom)


def _solve4(matrix: list[list[float]], vector: list[float]) -> tuple[float, ...]:
    augmented = [list(matrix[i]) + [vector[i]] for i in range(4)]
    for k in range(4):
        row = max(range(k, 4), key=lambda j: abs(augmented[j][k]))
        scale = max(1.0, *(abs(x) for r in augmented for x in r[:4]))
        if abs(augmented[row][k]) <= 1e-12 * scale:
            raise ValueError("DD_REGRESSION_SINGULAR_DESIGN")
        augmented[row], augmented[k] = augmented[k], augmented[row]
        pivot = augmented[k][k]
        for j in range(k+1, 4):
            factor = augmented[j][k] / pivot
            for z in range(k, 5):
                augmented[j][z] -= factor * augmented[k][z]
    beta = [0.0] * 4
    for k in range(3, -1, -1):
        beta[k] = (augmented[k][4] - sum(augmented[k][j]*beta[j]
                   for j in range(k+1, 4))) / augmented[k][k]
    return tuple(beta)


def dd_year_regression(peer_rows: Sequence[Mapping], target_row: Mapping,
                       *, min_peers: int = DEFAULT_MIN_PEERS) -> dict:
    """Frozen one-year industry/regime OLS with explicit dated panel evidence.

    Accepted cohort includes at least 20 independent *other* firms. Design rows
    contain six amounts used by dd_row and evidence of annual SIC membership,
    original filing, and same accounting regime. No S11 cohort substitution.
    """
    required = ("ticker", "sic", "accounting_regime", "fiscal_year",
                "membership_source_hash", "original_10k_source_hash",
                "dated_membership_verified", "original_10k_verified",
                "tca", "assets_t", "assets_previous",
                "cfo_previous", "cfo_current", "cfo_next")
    if any(k not in target_row for k in required):
        return {"status": "TARGET_DD_PANEL_INPUT_MISSING", "score": None}
    eligible = []
    seen = set()
    for peer in peer_rows:
        if not all(k in peer for k in required):
            continue
        if (peer["ticker"] == target_row["ticker"]
                or peer["fiscal_year"] != target_row["fiscal_year"]
                or peer["sic"] != target_row["sic"]
                or peer["accounting_regime"] != target_row["accounting_regime"]
                or not peer["dated_membership_verified"] or not peer["original_10k_verified"]
                or not peer["membership_source_hash"] or not peer["original_10k_source_hash"]):
            continue
        if peer["ticker"] in seen:
            raise ValueError("DUPLICATE_DD_PEER_IDENTITY")
        seen.add(peer["ticker"])
        eligible.append(peer)
    if len(eligible) < min_peers:
        return {"status": "HISTORICAL_INDUSTRY_YEAR_PEER_PANEL_MISSING",
                "peer_count": len(eligible), "minimum": min_peers, "score": None}
    try:
        xys = [dd_row(**{key: r[key] for key in
                         ("tca", "assets_t", "assets_previous",
                          "cfo_previous", "cfo_current", "cfo_next")}) for r in eligible]
        target = dd_row(**{key: target_row[key] for key in
                           ("tca", "assets_t", "assets_previous",
                            "cfo_previous", "cfo_current", "cfo_next")})
        xtx = [[sum(r[i]*r[j] for r in xys) for j in range(4)] for i in range(4)]
        xty = [sum(r[i]*r[4] for r in xys) for i in range(4)]
        beta = _solve4(xtx, xty)
    except (ValueError, ZeroDivisionError, OverflowError) as error:
        return {"status": "DD_REGRESSION_INPUT_OR_RANK_FAILURE",
                "reason": str(error), "peer_count": len(eligible), "score": None}
    residual = target[4]-sum(target[i]*beta[i] for i in range(4))
    return {"status": "FROZEN_YEAR_REGRESSION_RESEARCH_DIAGNOSTIC",
            "peer_count": len(eligible), "minimum": min_peers, "beta": beta,
            "target_residual": residual, "target_fiscal_year": target_row["fiscal_year"],
            "historical_pit_accepted": False, "score": None}


def dd_five_year_quality(regressions: Sequence[Mapping]) -> dict:
    """Five independent years; explicit population/sample sigma ambiguity."""
    years = [r.get("target_fiscal_year") for r in regressions]
    if (len(regressions) != 5 or any(r.get("status") !=
            "FROZEN_YEAR_REGRESSION_RESEARCH_DIAGNOSTIC" for r in regressions)
            or any(type(y) is not int for y in years)
            or sorted(years) != list(range(min(years), min(years)+5))):
        return {"status": "FIVE_CONSECUTIVE_DD_RESIDUAL_YEARS_NOT_VERIFIED", "score": None}
    xs = [_required_number(r["target_residual"]) for r in regressions]
    return {"status": "DD_SIGMA_RESEARCH_DIAGNOSTIC_ONLY",
            "residual_years": sorted(years), "sigma_population": pstdev(xs),
            "sigma_sample": stdev(xs),
            "S10": None, "blocker": "PIT historical peer DD_AQ distribution and frozen percentile/tie policy"}


def audit_bulk(archive: Path, contract: Path = SOURCE_LOCATION) -> dict:
    """Reuse five immutable V8 issuer pins; real numeric subcomponents only."""
    sha = verify_frozen_source(contract)
    archive = Path(archive)
    if archive.is_symlink() or not archive.is_file():
        raise ValueError("SEC pinned Companyfacts bulk archive unavailable")
    stocks = {}
    with zipfile.ZipFile(archive) as source:
        for ticker, config in TARGETS.items():
            member = source.getinfo(f"CIK{config['cik']}.json")
            if member.file_size > 40_000_000:
                raise ValueError("SEC_MEMBER_EXCEEDS_LIMIT")
            raw = source.read(member)
            v8 = audit_payload(ticker, raw)  # independently checks pinned CIK/SHA
            gaap = json.loads(raw)["facts"]["us-gaap"]
            ends = fiscal_ends(gaap, config["fy_end"])
            s8 = {}
            for year in (2024, 2025):
                end = ends[year]
                accession = config["accession"] if year == 2025 else None
                needed = {
                    key: _exact_gaap_value(gaap, tag, year, end, is_flow, accession)
                    for key, tag, is_flow in (
                        ("assets", "Assets", False), ("liabilities", "Liabilities", False),
                        ("ca", "AssetsCurrent", False), ("cl", "LiabilitiesCurrent", False),
                        ("ni", "NetIncomeLoss", True))
                }
                prior = _exact_gaap_value(gaap, "NetIncomeLoss", year-1,
                                           ends[year-1], True)
                needed["prior_ni"] = prior
                vals = {name: r["value"] for name, r in needed.items()
                        if r["status"] == "EXACT_ORIGINAL_10K_FACT_RESEARCH"}
                if len(vals) == len(needed):
                    preview = ohlson_components(
                        assets=vals["assets"], liabilities=vals["liabilities"],
                        ca=vals["ca"], cl=vals["cl"], net_income=vals["ni"],
                        prior_net_income=vals["prior_ni"], ffo=None,
                        balance_year=year)
                else:
                    preview = {"status": "MISSING_EXACT_SOURCE_ACCOUNTING_FACT",
                               "score": None, "missing": sorted(set(needed)-set(vals))}
                s8[str(year)] = {"source_facts": needed, "ohlson": preview,
                                 "S8": None, "accepted": False}
            s10 = {"S10": None, "status": "HISTORICAL_DD_PANEL_NOT_EVIDENCED",
                   "original_regression": "TCA/A = alpha + beta1*CFO(t-1)/A + beta2*CFO(t)/A + beta3*CFO(t+1)/A",
                   "min_independent_peers_preferred": 20,
                   "five_consecutive_residual_years_verified": 0,
                   "dated_industry_accounting_regime_panels_verified": 0,
                   "new_source_exact_inventory_counts": v8["s10"]["annual_fact_inventory"],
                   "future_CFO_2026_FY_available_asof_2026_10_11": False}
            if ticker == "CRMD":
                s10["crmd_targeted_receivables"] = crmd_receivables(gaap, ends)
            stocks[ticker] = {
                "companyfacts_sha256": config["sha256"], "source_cik": config["cik"],
                "fy_ends": ends, "S8": {"score": None, "years": s8},
                "S10": s10, "canonical_PIT": False, "complete_research_score": False}
    return {"schema": "M10_SCORING_V9_S8_S10_FROZEN_IMPLEMENTATION_V1",
            "frozen_source_sha256": sha, "frozen_source_lines": FROZEN_LINES,
            "pinned_V8_members_revalidated": len(stocks),
            "gnp_research_series": FRED_SERIES, "gnp_snapshot": FRED_SNAPSHOT,
            "gnp_historical_vintage_verified": False, "network_requests": 0,
            "new_complete_research_scores": 0, "canonical_PIT": 0,
            "stocks": stocks}
