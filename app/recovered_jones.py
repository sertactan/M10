"""Source-pinned S11 Modified Jones, independent and read-only.

The original S1–S14 specification (SHA below, lines 1550–1623) defines
TA = NI - CFO; industry-year OLS on 1/assets_previous,
delta_revenue/assets_previous, PPE/assets_previous; a receivables-adjusted
NDA; DA = TA/assets_previous - NDA; and an explicit absolute fallback
S11 = 100 * max(0, 1 - abs(DA)/0.20).

An evidenced industry-year cohort of >=20 other issuers is REQUIRED even for
the fallback, because coefficients cannot be inferred without actual peers.
No percentile-ranking convention is invented; the source's explicitly
published absolute fallback is identified as the normalization method.
Companyfacts provenance hashes are metadata, not cryptographic verification
of bytes; retrieved/accepted times never certify first-public dissemination.
All calculations are research-only, never historical PIT/canonical acceptance.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import math
import re
from collections.abc import Mapping, Sequence
from urllib.parse import urlsplit

VERSION = "S11_MODIFIED_JONES_SOURCE_RECOVERED_V1_RESEARCH"
CONTRACT = "S1_S2_S14_CANONICAL_SOURCE.md"
CONTRACT_SHA256 = "53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794"
CONTRACT_LINES = (1550, 1623)
MIN_OTHER_PEERS = 20
MAX_FISCAL_END_GAP_DAYS = 45
_HASH = re.compile(r"[a-fA-F0-9]{64}\Z")
_FORMS = {"10-K", "10-K/A"}
_ALIASES = {
    "NET_INCOME_T": ("NET_INCOME",),
    "CFO_T": ("OPERATING_CASH_FLOW",),
    "REVENUE_T": ("REVENUE",),
    "REVENUE_PREVIOUS": ("REVENUE",),
    "RECEIVABLES_T": ("ACCOUNTS_RECEIVABLE_NET", "RECEIVABLES_NET"),
    "RECEIVABLES_PREVIOUS": ("ACCOUNTS_RECEIVABLE_NET", "RECEIVABLES_NET"),
    "PPE_T": ("PPE_NET", "PROPERTY_PLANT_EQUIPMENT_NET"),
    "ASSETS_PREVIOUS": ("ASSETS", "TOTAL_ASSETS"),
}
_SIC = re.compile(r"\d{4}\Z")
_NAICS = re.compile(r"\d{6}\Z")


def _instant(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, OverflowError):
        return None


def _date(value):
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def _sec_url(value):
    if not isinstance(value, str):
        return False
    try:
        parts = urlsplit(value)
        return parts.scheme == "https" and parts.netloc.lower() in {
            "data.sec.gov", "www.sec.gov", "sec.gov"
        } and bool(parts.path.strip("/"))
    except ValueError:
        return False


def _issuer_sec_url(value, cik, *, industry=False):
    """Match SEC source's issuer CIK to observation identity."""
    if not _sec_url(value):
        return False
    parts = urlsplit(value)
    if parts.netloc.lower() == "data.sec.gov":
        expected = (f"/submissions/CIK{cik}.json" if industry
                    else f"/api/xbrl/companyfacts/CIK{cik}.json")
        return parts.path == expected and not parts.query and not parts.fragment
    if industry:
        return False
    return (parts.netloc.lower() in {"sec.gov", "www.sec.gov"}
            and parts.path.startswith(f"/Archives/edgar/data/{int(cik)}/")
            and not parts.query and not parts.fragment)


def _hash(value):
    return isinstance(value, str) and bool(_HASH.fullmatch(value))


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                            separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _audit(row):
    return {k: row.get(k) for k in (
        "metric", "value", "unit", "period_start", "period_end", "period_kind",
        "source", "source_ref", "form_type", "accession", "filing_date",
        "accepted_at", "available_at", "evidence_hash"
    )}


def _one(facts, key, kind, end, start, at, sid, cik):
    matches = [
        r for r in facts if isinstance(r, Mapping) and r.get("metric") in _ALIASES[key]
        and r.get("period_kind") == kind and r.get("period_end") == end
        and (kind == "INSTANT" or start is None or r.get("period_start") == start)
    ]
    if not matches:
        return None, key + "_EXACT_PERIOD_MISSING"
    # Selecting one of multiple filings/restatements silently could change OLS.
    if len(matches) != 1:
        return None, key + "_AMBIGUOUS_RESTATEMENT_OR_ALIAS"
    row = matches[0]
    accepted, available = _instant(row.get("accepted_at")), _instant(row.get("available_at"))
    filed = _date(row.get("filing_date"))
    value = row.get("value")
    if (type(value) not in (float, int) or not math.isfinite(value)
            or row.get("unit") != "USD" or row.get("source") != "SEC_EDGAR"
            or row.get("form_type") not in _FORMS
            or not row.get("accession")
            or not _issuer_sec_url(row.get("source_ref"), cik)
            or row.get("security_id") != sid
            or not _hash(row.get("evidence_hash"))
            or not accepted or not available or accepted > available or available > at
            or not filed or filed > accepted.date() or _date(end) > filed
            or (kind == "INSTANT" and row.get("period_start") not in (None, ""))
            or (kind == "ANNUAL" and _date(row.get("period_start")) is None)):
        return None, key + "_SOURCE_TIME_HASH_INVALID"
    return row, None


def _observation(source, at):
    """Return a fully aligned company-year observation or specific blockers."""
    if not isinstance(source, Mapping):
        return None, ["ISSUER_METADATA_MISSING"]
    sid, industry = source.get("security_id"), source.get("industry")
    if not isinstance(sid, str) or not sid.strip():
        return None, ["SECURITY_ID_MISSING"]
    raw_cik = str(source.get("cik", ""))
    if not re.fullmatch(r"\d{1,10}", raw_cik) or int(raw_cik) <= 0:
        return None, ["SEC_CIK_IDENTITY_MISSING"]
    cik = raw_cik.zfill(10)
    start, end = _date(source.get("period_start")), _date(source.get("period_end"))
    fy = source.get("fiscal_year")
    if (not start or not end or type(fy) is not int or fy != end.year
            or not 330 <= (end - start).days + 1 <= 400 or end > at.date()):
        return None, ["VALID_ANNUAL_FISCAL_YEAR_WINDOW"]
    prior_end = start - timedelta(days=1)
    if not isinstance(industry, Mapping):
        return None, ["DATED_INDUSTRY_CLASSIFICATION"]
    scheme, code = industry.get("scheme"), industry.get("code")
    available = _instant(industry.get("available_at"))
    effective = _date(industry.get("effective_on"))
    if (not isinstance(scheme, str) or scheme not in {"SIC", "NAICS"}
            or not isinstance(code, str)
            or not (_SIC if scheme == "SIC" else _NAICS).fullmatch(code)
            or industry.get("source") != "SEC_EDGAR"
            or not _issuer_sec_url(industry.get("source_ref"), cik, industry=True)
            or not _hash(industry.get("evidence_hash"))
            or not available or available > at or not effective or effective > end):
        return None, ["DATED_INDUSTRY_CLASSIFICATION"]
    facts = source.get("facts")
    if not isinstance(facts, list):
        return None, ["SEC_ANNUAL_FACTS_MISSING"]
    refs, blockers = {}, []
    requirements = {
        "NET_INCOME_T": ("ANNUAL", end.isoformat(), start.isoformat()),
        "CFO_T": ("ANNUAL", end.isoformat(), start.isoformat()),
        "REVENUE_T": ("ANNUAL", end.isoformat(), start.isoformat()),
        "REVENUE_PREVIOUS": ("ANNUAL", prior_end.isoformat(), None),
        "RECEIVABLES_T": ("INSTANT", end.isoformat(), None),
        "RECEIVABLES_PREVIOUS": ("INSTANT", prior_end.isoformat(), None),
        "PPE_T": ("INSTANT", end.isoformat(), None),
        "ASSETS_PREVIOUS": ("INSTANT", prior_end.isoformat(), None),
    }
    for key, (kind, period_end, period_start) in requirements.items():
        row, error = _one(facts, key, kind, period_end, period_start, at, sid, cik)
        if error:
            blockers.append(error)
        else:
            refs[key] = row
    if blockers:
        return None, blockers
    previous_start = _date(refs["REVENUE_PREVIOUS"]["period_start"])
    if not previous_start or not 330 <= (prior_end - previous_start).days + 1 <= 400:
        return None, ["CONTIGUOUS_PREVIOUS_ANNUAL_REVENUE_WINDOW"]
    if any(row.get("security_id") not in (None, sid)
           for row in refs.values()):
        return None, ["MIXED_SECURITY_FACTS"]
    prev_assets = float(refs["ASSETS_PREVIOUS"]["value"])
    if prev_assets <= 0:
        return None, ["POSITIVE_PRIOR_TOTAL_ASSETS_REQUIRED"]
    values = {k: float(v["value"]) for k, v in refs.items()}
    delta_rev = values["REVENUE_T"] - values["REVENUE_PREVIOUS"]
    delta_rec = values["RECEIVABLES_T"] - values["RECEIVABLES_PREVIOUS"]
    scaled_accrual = (values["NET_INCOME_T"] - values["CFO_T"]) / prev_assets
    predictors = [1.0 / prev_assets, delta_rev / prev_assets, values["PPE_T"] / prev_assets]
    if not all(math.isfinite(x) for x in (*predictors, scaled_accrual, delta_rec / prev_assets)):
        return None, ["FINITE_JONES_PREDICTORS_REQUIRED"]
    return {
        "security_id": sid, "cik": cik, "fiscal_year": fy, "period_start": start.isoformat(),
        "period_end": end.isoformat(), "previous_end": prior_end.isoformat(),
        "industry": {"scheme": scheme, "code": code, "source": "SEC_EDGAR",
                     "source_ref": industry["source_ref"],
                     "evidence_hash": industry["evidence_hash"].lower(),
                     "available_at": available.isoformat(), "effective_on": effective.isoformat()},
        "facts": {key: _audit(refs[key]) for key in requirements},
        "x": predictors, "y": scaled_accrual, "delta_receivables_scaled": delta_rec / prev_assets,
        "previous_assets": prev_assets,
    }, []


def _ols_no_intercept(peers):
    """Column-normalized modified Gram-Schmidt QR, with rank failure closed."""
    n = len(peers)
    columns = [[item["x"][j] for item in peers] for j in range(3)]
    scalers = [math.sqrt(sum(v * v for v in col)) for col in columns]
    if any(not math.isfinite(s) or s <= 0 for s in scalers):
        return None
    columns = [[v / s for v in col] for col, s in zip(columns, scalers)]
    q, r = [], [[0.0] * 3 for _ in range(3)]
    for j in range(3):
        v = columns[j][:]
        # Reorthogonalize to avoid spurious rank on nearly collinear peers.
        for _ in range(2):
            for i in range(j):
                projection = sum(a * b for a, b in zip(q[i], v))
                r[i][j] += projection
                v = [value - projection * basis for value, basis in zip(v, q[i])]
        norm = math.sqrt(sum(value * value for value in v))
        if not math.isfinite(norm) or norm <= 1e-10:
            return None
        r[j][j] = norm
        q.append([value / norm for value in v])
    y = [item["y"] for item in peers]
    scaled_beta = [0.0] * 3
    projections = [sum(value * basis for value, basis in zip(y, qj)) for qj in q]
    for j in (2, 1, 0):
        scaled_beta[j] = (projections[j] -
                          sum(r[j][k] * scaled_beta[k] for k in range(j + 1, 3))) / r[j][j]
    coefficients = [v / s for v, s in zip(scaled_beta, scalers)]
    residuals = [item["y"] - sum(b * x for b, x in zip(coefficients, item["x"]))
                 for item in peers]
    rmse = math.sqrt(sum(e * e for e in residuals) / (n - 3))
    if not all(math.isfinite(v) for v in (*coefficients, rmse)):
        return None
    return coefficients, rmse


def _result(at, blockers, *, score=None, period=None, components=None,
            target=None, peers=(), excluded=()):
    components = components or {}
    evidence = {
        "contract": CONTRACT, "contract_sha256": CONTRACT_SHA256,
        "contract_lines": list(CONTRACT_LINES),
        "model_formula": "OLS_NO_INTERCEPT_1_OVER_PREV_ASSETS_DELTA_REV_PPE",
        "minimum_independent_peers": MIN_OTHER_PEERS,
        "max_fiscal_end_gap_days": MAX_FISCAL_END_GAP_DAYS,
        "target": target, "eligible_peers": list(peers), "excluded_peers": list(excluded),
        "historical_pit_accepted": False, "source_content_hashes_verified": False,
        "time_semantics": "RESEARCH_SOURCE_AVAILABLE_AT_NOT_VERIFIED_FIRST_PUBLIC_DISSEMINATION",
    }
    envelope = {"score": score, "as_of": at.isoformat(), "components": components,
                "missing": sorted(set(blockers)), "evidence": evidence, "version": VERSION}
    return {"score": score,
            "status": "VERIFIED_DONE" if score is not None else "DATA_MISSING",
            "scope": "RESEARCH_ONLY_NOT_CANONICAL_PIT", "canonical_accepted": False,
            "version": VERSION, "as_of": at.isoformat(), "period": period,
            "missing": sorted(set(blockers)), "components": components,
            "evidence": evidence, "evidence_hash": _digest(envelope)}


def compute_s11(target: Mapping | None, peers: Sequence | None, at: datetime) -> dict:
    """Return original normalized S11 if 20+ complete, dated same-industry FY peers exist.

    Each observation must specify security_id, cik, fiscal_year, period_start/end,
    industry={scheme:'SIC'|'NAICS',code,effective_on,available_at,source,
    source_ref,evidence_hash}, facts=[recovered SEC row dictionaries].
    Requires 8 exact fiscal concept/window facts per issuer; the target is never
    included in the peer OLS. Excluded peer reasons are auditable.
    """
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("S11 as_of must be timezone-aware")
    at = at.astimezone(timezone.utc)
    sample, missing = _observation(target, at)
    if sample is None:
        return _result(at, missing or ["TARGET_S11_FACTS_MISSING"])
    end = _date(sample["period_end"])
    if peers is None or not isinstance(peers, Sequence) or isinstance(peers, (str, bytes)):
        return _result(at, ["DATED_INDUSTRY_YEAR_PEERS_MISSING"], target=sample,
                       period=sample["period_end"])
    admitted, excluded, seen, seen_cik = [], [], set(), set()
    duplicate_peer = False
    for index, candidate in enumerate(peers):
        obs, why = _observation(candidate, at)
        sid = candidate.get("security_id") if isinstance(candidate, Mapping) else None
        candidate_cik = (str(candidate.get("cik", "")).zfill(10)
                         if isinstance(candidate, Mapping) else "")
        if (not isinstance(sid, str) or not sid.strip()
                or sid == sample["security_id"] or sid in seen
                or candidate_cik == sample["cik"] or candidate_cik in seen_cik):
            duplicate_peer = True
            excluded.append({"input_index": index, "security_id": sid,
                             "missing": ["NON_UNIQUE_OR_TARGET_PEER_IDENTITY"]})
            continue
        seen.add(sid)
        seen_cik.add(candidate_cik)
        if why:
            excluded.append({"input_index": index, "security_id": sid, "missing": why})
            continue
        assert obs is not None
        if (obs["industry"]["scheme"], obs["industry"]["code"]) != (
            sample["industry"]["scheme"], sample["industry"]["code"]
        ) or obs["fiscal_year"] != sample["fiscal_year"] or abs(
            (_date(obs["period_end"]) - end).days
        ) > MAX_FISCAL_END_GAP_DAYS:
            excluded.append({"input_index": index, "security_id": sid,
                             "missing": ["INDUSTRY_YEAR_OR_FISCAL_END_MISMATCH"]})
            continue
        admitted.append(obs)
    admitted.sort(key=lambda x: x["security_id"])
    excluded.sort(key=lambda x: x["input_index"])
    if duplicate_peer:
        missing.append("DUPLICATE_OR_TARGET_INCLUDED_IN_PEERS")
    if len(admitted) < MIN_OTHER_PEERS:
        missing.append("ELIGIBLE_INDUSTRY_YEAR_PEERS_LT_20")
    if missing:
        return _result(at, missing, target=sample, peers=admitted,
                       excluded=excluded, period=sample["period_end"],
                       components={"eligible_peer_count": len(admitted),
                                   "excluded_peer_count": len(excluded)})
    regression = _ols_no_intercept(admitted)
    if regression is None:
        return _result(at, ["INDUSTRY_YEAR_OLS_RANK_OR_FINITE_FAILURE"],
                       target=sample, peers=admitted, excluded=excluded,
                       period=sample["period_end"],
                       components={"eligible_peer_count": len(admitted)})
    (a1, a2, a3), rmse = regression
    x1, x2, x3 = sample["x"]
    nda = a1 * x1 + a2 * (x2 - sample["delta_receivables_scaled"]) + a3 * x3
    da = sample["y"] - nda
    if not all(math.isfinite(v) for v in (nda, da)):
        return _result(at, ["FINITE_DISCRETIONARY_ACCRUAL_REQUIRED"],
                       target=sample, peers=admitted, excluded=excluded,
                       period=sample["period_end"])
    score = 100.0 * max(0.0, 1.0 - abs(da) / .20)
    components = {
        "eligible_peer_count": len(admitted), "excluded_peer_count": len(excluded),
        "OLS_coefficients": {"alpha1": a1, "alpha2": a2, "alpha3": a3},
        "OLS_residual_rmse": rmse, "OLS_intercept": None, "OLS_rank": 3,
        "total_accrual_scaled": sample["y"], "delta_receivables_scaled": sample["delta_receivables_scaled"],
        "modified_jones_nda": nda, "discretionary_accrual": da,
        "discretionary_accrual_sign": (
            "INCOME_INCREASING" if da > 0 else "INCOME_DECREASING" if da < 0 else "ZERO"),
        "MJRisk_absolute_da": abs(da),
        "normalization": "ORIGINAL_ABSOLUTE_FALLBACK_100_MAX_0_1_MINUS_ABS_DA_OVER_0_20",
        "peer_percentile_applied": False,
    }
    return _result(at, [], score=score, period=sample["period_end"],
                   target=sample, peers=admitted, excluded=excluded, components=components)


calculate_jones = compute_s11
