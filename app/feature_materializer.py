from __future__ import annotations

from datetime import date, datetime, time, timezone
from statistics import median

from app.bootstrap import AppContainer
from core.fundamentals.snapshot import FundamentalSnapshotService
from core.features.wf_raw_metrics import (
    exact_period_per_share_series,
    latest_cagr,
    latest_growth,
)
from core.scoring.math import accel_score, piecewise_score, pos_score, wa
from data.repositories.fundamental_repository import FundamentalRepository
from data.repositories.model_feature_repository import ModelFeatureRepository
from data.storage.parquet_price_store import ParquetPriceStore


GROWTH_KNOTS = (
    (0.00, 0.0),
    (0.10, 25.0),
    (0.20, 50.0),
    (0.30, 75.0),
    (0.50, 100.0),
)


def _safe_div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return float(a) / float(b)


def _growth(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None or prior <= 0:
        return None
    return float(current) / float(prior) - 1.0


def _cagr(current: float | None, prior: float | None, years: int) -> float | None:
    if current is None or prior is None or current <= 0 or prior <= 0 or years <= 0:
        return None
    return (float(current) / float(prior)) ** (1.0 / years) - 1.0


def _metric_series(
    facts: list[dict],
    metric: str,
    *,
    period_kinds: set[str] | None = None,
) -> list[dict]:
    rows = [
        row for row in facts
        if row["metric_name"] == metric
        and (period_kinds is None or row["period_kind"] in period_kinds)
    ]
    dedup: dict[str, dict] = {}
    for row in rows:
        key = str(row["period_end"])
        current = dedup.get(key)
        if current is None or row["available_at"] > current["available_at"]:
            dedup[key] = row
    return sorted(dedup.values(), key=lambda row: row["period_end"])


def _annual_series(facts: list[dict], metric: str) -> list[dict]:
    return _metric_series(facts, metric, period_kinds={"ANNUAL"})


def _annual_fcf(facts: list[dict]) -> list[tuple[str, float, str]]:
    ocf = {row["period_end"]: row for row in _annual_series(facts, "OPERATING_CASH_FLOW")}
    capex = {row["period_end"]: row for row in _annual_series(facts, "CAPEX")}
    out: list[tuple[str, float, str]] = []
    for period in sorted(set(ocf) & set(capex)):
        value = float(ocf[period]["value"]) - abs(float(capex[period]["value"]))
        available = max(str(ocf[period]["available_at"]), str(capex[period]["available_at"]))
        out.append((period, value, available))
    return out


def _margin(num: float | None, revenue: float | None) -> float | None:
    ratio = _safe_div(num, revenue)
    return ratio if ratio is not None else None


def _score_growth(value: float | None) -> float | None:
    return None if value is None else piecewise_score(value, GROWTH_KNOTS)


def _dilution_quality(cagr: float | None) -> float | None:
    if cagr is None:
        return None
    pct = cagr * 100.0
    if pct <= 0:
        return 100.0
    if pct <= 2:
        return 100.0 - 5.0 * pct
    if pct <= 5:
        return 90.0 - (pct - 2.0) * (20.0 / 3.0)
    if pct <= 8:
        return 70.0 - (pct - 5.0) * (25.0 / 3.0)
    if pct <= 12:
        return 45.0 - (pct - 8.0) * (25.0 / 4.0)
    return 0.0


class CanonicalFeatureMaterializer:
    """Materialize only deterministic, evidenced S15.3 inputs.

    Missing qualitative, analyst, catalyst, TAM, options or cohort evidence stays
    absent. No synthetic 50s/defaults are written.
    """

    VERSION = "canonical-materializer-v3-wf2-raw-evidence"

    def __init__(self, app: AppContainer) -> None:
        self.app = app
        self.fundamentals = FundamentalRepository(app.sqlite)
        self.features = ModelFeatureRepository(app.sqlite)

    def _price_frame(self, security_id: str, as_of_date: date):
        selection = self.app.sqlite.connection.execute(
            """
            SELECT * FROM canonical_price_selection
            WHERE security_id=? AND start_date<=? AND end_date>=?
            ORDER BY selected_at DESC LIMIT 1
            """,
            (security_id, as_of_date.isoformat(), as_of_date.isoformat()),
        ).fetchone()
        if selection is None:
            selection = self.app.sqlite.connection.execute(
                """
                SELECT * FROM canonical_price_selection
                WHERE security_id=? AND start_date<=? AND end_date<?
                ORDER BY end_date DESC, selected_at DESC LIMIT 1
                """,
                (security_id, as_of_date.isoformat(), as_of_date.isoformat()),
            ).fetchone()
        if selection is None:
            return None, None
        store = ParquetPriceStore(
            self.app.resolve_data_path(self.app.app_config.database.parquet_root)
        )
        start = date.fromisoformat(selection["start_date"])
        end = min(as_of_date, date.fromisoformat(selection["end_date"]))
        frame = store.read_bars(
            security_id=security_id,
            source=selection["source"],
            source_symbol=selection["source_symbol"],
            start_date=start,
            end_date=end,
        )
        if frame.empty:
            return None, None
        return frame.sort_values("trade_date"), dict(selection)

    def materialize(self, row, *, as_of_date: date) -> int:
        as_of = datetime.combine(as_of_date, time.max, tzinfo=timezone.utc)
        security_id = str(row["security_id"])
        facts = self.fundamentals.canonical_facts_as_of(security_id, as_of)
        snapshot = FundamentalSnapshotService(self.fundamentals).snapshot_as_of(
            security_id, as_of
        )
        frame, selection = self._price_frame(security_id, as_of_date)

        values: dict[str, tuple[float, dict]] = {}

        def put(key: str, value: float | None, **evidence) -> None:
            if value is None:
                return
            values[key] = (float(value), evidence)

        # Market state.
        if frame is not None:
            latest = frame.iloc[-1]
            price = float(latest["adjusted_close"])
            put("RAW_CURRENT_PRICE", price, source=selection["source"], trade_date=str(latest["trade_date"])[:10])
            recent20 = frame.tail(20)
            if len(recent20) >= 5:
                dollar = [float(r["adjusted_close"]) * float(r["volume"]) for _, r in recent20.iterrows()]
                put("MEDIAN_DOLLAR_VOLUME_20", median(dollar), source=selection["source"])
            if len(frame) >= 120:
                avg20 = float(frame.tail(20)["volume"].mean())
                avg120 = float(frame.tail(120)["volume"].mean())
                if avg120 > 0:
                    turn_ratio = avg20 / avg120
                    turnacc = pos_score(turn_ratio, 1.0, 3.0)
                    put("TURNACC", turnacc, ratio=turn_ratio)
                    put("VOLACC", turnacc, ratio=turn_ratio)
                    put("DOLLAR_VOLUME_ACCEL", turnacc, ratio=turn_ratio)
            if len(frame) >= 200:
                sma200 = float(frame.tail(200)["adjusted_close"].mean())
                if sma200 > 0:
                    p200 = pos_score(price / sma200 - 1.0, 0.20, 1.00)
                    put("PIR_EXT", p200, p200=p200, note="PIR EXT currently evidenced by P200 leg only")

        # Fundamental annual histories.
        rev = _annual_series(facts, "REVENUE")
        op = _annual_series(facts, "OPERATING_INCOME")
        gp = _annual_series(facts, "GROSS_PROFIT")
        ni = _annual_series(facts, "NET_INCOME")
        shares = _metric_series(facts, "SHARES_OUTSTANDING")
        eps = _annual_series(facts, "DILUTED_EPS")
        fcf = _annual_fcf(facts)

        # WF2 raw evidence: the canonical sources define RPS/FPS concepts, but
        # their final 0-100 normalization is not frozen. Persist conservative
        # raw evidence only; never promote these raw rows to F52/F53 scores.
        rps_points = exact_period_per_share_series(rev, shares)
        fcf_rows = [{"period_end": p, "value": v} for p, v, _available in fcf]
        fps_points = exact_period_per_share_series(fcf_rows, shares)
        if rps_points:
            put(
                "RAW_REVENUE_PER_SHARE",
                rps_points[-1].value,
                period_end=rps_points[-1].period_end,
                rule="exact-period revenue / shares; no cross-period share proxy",
            )
            put(
                "RAW_RPS_GROWTH_1Y",
                latest_growth(rps_points),
                periods=[p.period_end for p in rps_points[-2:]],
            )
            put(
                "RAW_RPS_CAGR_3Y",
                latest_cagr(rps_points, 3),
                periods=[p.period_end for p in rps_points[-4:]],
            )
        if fps_points:
            put(
                "RAW_FCF_PER_SHARE",
                fps_points[-1].value,
                period_end=fps_points[-1].period_end,
                rule="exact-period FCF / shares; no cross-period share proxy",
            )
            put(
                "RAW_FPS_GROWTH_1Y",
                latest_growth(fps_points),
                periods=[p.period_end for p in fps_points[-2:]],
            )
            put(
                "RAW_FPS_CAGR_3Y",
                latest_cagr(fps_points, 3),
                periods=[p.period_end for p in fps_points[-4:]],
            )

        rev_vals = [float(x["value"]) for x in rev]
        rev_1y = _growth(rev_vals[-1], rev_vals[-2]) if len(rev_vals) >= 2 else None
        rev_3y = _cagr(rev_vals[-1], rev_vals[-4], 3) if len(rev_vals) >= 4 else None
        rev_5y = _cagr(rev_vals[-1], rev_vals[-6], 5) if len(rev_vals) >= 6 else None

        d01 = wa({
            "1Y": (0.35, _score_growth(rev_1y)),
            "3Y": (0.35, _score_growth(rev_3y)),
            "Forward": (0.30, None),
        })
        put("D01", d01, revenue_growth_1y=rev_1y, revenue_cagr_3y=rev_3y)

        if len(rev_vals) >= 3:
            prior_growth = _growth(rev_vals[-2], rev_vals[-3])
            if rev_1y is not None and prior_growth is not None:
                ga = accel_score((rev_1y - prior_growth) * 100.0, 20.0)
                put("D03", ga, recent_growth=rev_1y, prior_growth=prior_growth)
                put("GA_ROUTER", ga, recent_growth=rev_1y, prior_growth=prior_growth)
                put("GROWACC", ga, recent_growth=rev_1y, prior_growth=prior_growth)

        # Growth persistence: only known legs are used; N/A weights renormalize.
        gp_score = wa({
            "G1Y": (0.20, _score_growth(rev_1y)),
            "G3Y": (0.20, _score_growth(rev_3y)),
            "G5Y": (0.15, _score_growth(rev_5y)),
            "GForward": (0.20, None),
            "Structure": (0.15, None),
            "DecelerationQuality": (0.10, values.get("D03", (None, {}))[0]),
        })
        put("F51_GP", gp_score, revenue_growth_1y=rev_1y, revenue_cagr_3y=rev_3y, revenue_cagr_5y=rev_5y)
        put("SG", gp_score, source="F51_GP")

        # EPS growth when both comparison values are positive.
        eps_vals = [float(x["value"]) for x in eps]
        eps_1y = _growth(eps_vals[-1], eps_vals[-2]) if len(eps_vals) >= 2 else None
        eps_3y = _cagr(eps_vals[-1], eps_vals[-4], 3) if len(eps_vals) >= 4 else None
        d02 = wa({
            "1Y": (0.35, _score_growth(eps_1y)),
            "3Y": (0.35, _score_growth(eps_3y)),
            "Forward": (0.30, None),
        })
        put("D02", d02, eps_growth_1y=eps_1y, eps_cagr_3y=eps_3y)

        # Operating leverage and margin inflection use exact S15.3 normalization.
        if len(rev_vals) >= 2 and len(op) >= 2:
            op_vals = [float(x["value"]) for x in op]
            op_growth = _growth(op_vals[-1], op_vals[-2])
            if op_growth is not None and rev_1y is not None:
                ol_q = pos_score((op_growth - rev_1y) * 100.0, 0.0, 60.0)
                put("OL_Q", ol_q, operating_income_growth=op_growth, revenue_growth=rev_1y)
                put("OL_ROUTER", ol_q, source="OL_Q")
                put("D05", ol_q, canonical="Operating Leverage", source="OL_Q")

        def latest_margin_delta(series: list[dict]) -> float | None:
            if len(series) < 2 or len(rev) < 2:
                return None
            metric = {x["period_end"]: float(x["value"]) for x in series}
            revenue = {x["period_end"]: float(x["value"]) for x in rev}
            common = sorted(set(metric) & set(revenue))
            if len(common) < 2:
                return None
            a, b = common[-2], common[-1]
            old = _margin(metric[a], revenue[a])
            new = _margin(metric[b], revenue[b])
            if old is None or new is None:
                return None
            return (new - old) * 100.0

        om_delta = latest_margin_delta(op)
        gm_delta = latest_margin_delta(gp)
        fcf_map = {p: v for p, v, _ in fcf}
        rev_map = {x["period_end"]: float(x["value"]) for x in rev}
        fcf_common = sorted(set(fcf_map) & set(rev_map))
        fcf_margin = None
        fcf_margin_delta = None
        if fcf_common:
            p = fcf_common[-1]
            fcf_margin = _safe_div(fcf_map[p], rev_map[p])
        if len(fcf_common) >= 2:
            p0, p1 = fcf_common[-2], fcf_common[-1]
            old = _safe_div(fcf_map[p0], rev_map[p0])
            new = _safe_div(fcf_map[p1], rev_map[p1])
            if old is not None and new is not None:
                fcf_margin_delta = (new - old) * 100.0

        om_q = pos_score(om_delta, 0.0, 15.0) if om_delta is not None else None
        gm_q = pos_score(gm_delta, 0.0, 10.0) if gm_delta is not None else None
        fcfm_q = pos_score(fcf_margin_delta, 0.0, 15.0) if fcf_margin_delta is not None else None
        mi_q = wa({"OM": (0.40, om_q), "GM": (0.30, gm_q), "FCFM": (0.30, fcfm_q)})
        put("MI_Q", mi_q, operating_margin_delta_pp=om_delta, gross_margin_delta_pp=gm_delta, fcf_margin_delta_pp=fcf_margin_delta)
        put("MI_ROUTER", mi_q, source="MI_Q")
        put("D06", mi_q, canonical="Margin Expansion", source="MI_Q")

        fcf_level_q = pos_score(fcf_margin * 100.0, -10.0, 20.0) if fcf_margin is not None else None
        fcf_change_q = pos_score(fcf_margin_delta, 0.0, 20.0) if fcf_margin_delta is not None else None
        fcfi_q = wa({"Level": (0.50, fcf_level_q), "Change": (0.50, fcf_change_q)})
        put("FCFI_Q", fcfi_q, fcf_margin=fcf_margin, fcf_margin_delta_pp=fcf_margin_delta)

        if eps_1y is not None and rev_1y is not None:
            epsl_q = pos_score((eps_1y - rev_1y) * 100.0, 0.0, 80.0)
            put("EPSL_Q", epsl_q, eps_growth=eps_1y, revenue_growth=rev_1y)

        profitacc = wa({"MI": (0.5, mi_q), "FCFI": (0.5, fcfi_q)})
        put("PROFACC", profitacc, source="MI_Q+FCFI_Q")

        # Cross-zero rubric from canonical S15.3 spec.
        fcf_vals = [x[1] for x in fcf]
        crosszero = None
        if len(fcf_vals) >= 3 and fcf_vals[-1] > 0 and fcf_vals[-2] > 0 and fcf_vals[-3] <= 0:
            crosszero = 100.0
        elif len(fcf_vals) >= 2 and fcf_vals[-1] > 0 and fcf_vals[-2] <= 0:
            crosszero = 80.0
        elif len(fcf_vals) >= 2 and fcf_vals[-1] < 0 and fcf_vals[-2] < 0 and abs(fcf_vals[-1]) < abs(fcf_vals[-2]):
            improvement = 1.0 - abs(fcf_vals[-1]) / max(abs(fcf_vals[-2]), 1e-12)
            crosszero = 60.0 if improvement > 0.50 else (40.0 if improvement >= 0.20 else 20.0)
        put("CROSSZERO", crosszero, annual_fcf=fcf_vals[-3:])

        profitshift = wa({"MI": (0.50, mi_q), "FCFI": (0.30, fcfi_q), "CROSSZERO": (0.20, crosszero)})
        put("PROFITSHIFT", profitshift, source="MI_Q+FCFI_Q+CROSSZERO")
        put("D38", profitshift, canonical="Profitability Inflection", source="PROFITSHIFT")

        # Dilution quality exact fallback thresholds.
        share_vals = [float(x["value"]) for x in shares]
        share_cagr = _cagr(share_vals[-1], share_vals[-4], 3) if len(share_vals) >= 4 else (
            _growth(share_vals[-1], share_vals[-2]) if len(share_vals) >= 2 else None
        )
        dil = _dilution_quality(share_cagr)
        put("F54_DIL", dil, diluted_share_cagr=share_cagr)
        put("DIL", dil, source="F54_DIL")

        # Current market cap uses canonical price × latest available shares.
        current_price = values.get("RAW_CURRENT_PRICE", (None, {}))[0]
        latest_shares = snapshot.facts.get("SHARES_OUTSTANDING")
        if current_price is not None and latest_shares is not None:
            mc = current_price * float(latest_shares["value"])
            put("RAW_CURRENT_MARKET_CAP", mc, price=current_price, shares=float(latest_shares["value"]))

            # WF2 raw valuation evidence. PIR_VAL remains N/A until the frozen
            # growth-adjusted peer-percentile construction is fully available.
            ttm_revenue = snapshot.ttm.get("REVENUE")
            ttm_fcf = snapshot.ttm.get("FREE_CASH_FLOW")
            if ttm_revenue is not None and ttm_revenue > 0:
                put(
                    "RAW_PRICE_TO_SALES_TTM",
                    mc / float(ttm_revenue),
                    market_cap=mc,
                    ttm_revenue=float(ttm_revenue),
                )
            if ttm_fcf is not None and ttm_fcf > 0:
                put(
                    "RAW_PRICE_TO_FCF_TTM",
                    mc / float(ttm_fcf),
                    market_cap=mc,
                    ttm_fcf=float(ttm_fcf),
                )
            cash = snapshot.facts.get("CASH")
            debt = snapshot.facts.get("LONG_TERM_DEBT")
            if cash is not None or debt is not None:
                cash_value = float(cash["value"]) if cash is not None else 0.0
                debt_value = float(debt["value"]) if debt is not None else 0.0
                net_debt = debt_value - cash_value
                put(
                    "RAW_NET_DEBT",
                    net_debt,
                    long_term_debt=debt_value,
                    cash=cash_value,
                    note="long-term debt minus cash; no unverified short-term-debt proxy",
                )
                if ttm_revenue is not None and ttm_revenue > 0:
                    enterprise_value = mc + net_debt
                    put(
                        "RAW_EV_TO_SALES_TTM",
                        enterprise_value / float(ttm_revenue),
                        enterprise_value=enterprise_value,
                        ttm_revenue=float(ttm_revenue),
                    )

        # Viability: canonical CASH leg, plus DIL via model.
        current_fcf = snapshot.ttm.get("FREE_CASH_FLOW")
        cash_fact = snapshot.facts.get("CASH")
        cash_score = None
        if current_fcf is not None and current_fcf >= 0:
            cash_score = 100.0
        elif current_fcf is not None and current_fcf < 0 and cash_fact is not None:
            runway_months = float(cash_fact["value"]) / max(abs(current_fcf) / 12.0, 1e-12)
            cash_score = piecewise_score(runway_months, ((3,0),(6,25),(9,45),(12,65),(18,85),(24,100)))
        put("CASH", cash_score, ttm_fcf=current_fcf, cash=(float(cash_fact["value"]) if cash_fact else None))

        # Confidence legs: deterministic coverage/source/PIT. MODEL_FIT remains absent
        # until route-specific evidence is available, so final confidence stays N/A.
        expected_quant = 18
        present_quant = len(values)
        coverage_score = min(100.0, 100.0 * present_quant / expected_quant)
        put("DATA_COVERAGE", coverage_score, present_quant_features=present_quant, expected_quant_features=expected_quant)
        put("SOURCE_QUALITY", 100.0 if facts else 65.0, fundamental_source="SEC_EDGAR" if facts else None)
        put("PIT_INTEGRITY", 100.0, rule="available_at<=as_of; canonical price window")

        latest_availability = as_of
        if facts:
            latest_fact_avail = max(datetime.fromisoformat(str(x["available_at"])) for x in facts)
            latest_availability = min(as_of, latest_fact_avail)

        count = 0
        for key, (value, evidence) in values.items():
            self.features.save_feature(
                security_id=security_id,
                feature_key=key,
                value=value,
                feature_as_of=as_of,
                available_at=latest_availability,
                source_phase="DERIVED_CANONICAL",
                source_ref=f"SEC+PRICE:{security_id}:{as_of_date.isoformat()}",
                quality_status="CANONICAL_DERIVED",
                computation_version=self.VERSION,
                evidence=evidence,
            )
            count += 1
        return count
