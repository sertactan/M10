# WF3 — Destination Engine

Status: COMPLETE — WF3 Peer Policy V1 frozen and whole-universe PIT materializer implemented.

## Canonical rules implemented

Peer priority:

```text
same as-of month
x route
x sector/industry
x market-cap bucket
x profitability state
```

Peer sufficiency:

```text
N >= 50       NORMAL
30 <= N < 50 LOW_CONFIDENCE
N < 30        EXPANSION_REQUIRED
```

Because the canonical S15.3 source does not freeze the exact market-cap bucket
boundaries, profitability-state categories, or the N<30 expansion sequence,
WF3 does not infer them from legacy Meridyen classifications.

If exact peers are fewer than 30 the engine returns:

```text
EXPANSION_REQUIRED_RULE_UNSPECIFIED
```

and does not fabricate percentiles.

## Exact peer outputs

When a metric has at least 30 valid positive peer observations:

```text
PEER_MEDIAN_SALES_MULTIPLE
PEER_P90_SALES_MULTIPLE
PEER_MEDIAN_EBITDA_MULTIPLE
PEER_P90_EBITDA_MULTIPLE
PEER_MEDIAN_FCF_MULTIPLE
PEER_P90_FCF_MULTIPLE
ROUTE_PEER_P99_MARKET_CAP
ROUTE_PEER_N
```

Metric-specific N is enforced. A cohort may contain 50 securities while a
particular valuation metric has fewer than 30 valid values; that metric remains
N/A.

## Destination materialization

Already connected:

```text
F10/I10 -> SUPPORTED_MC_12_FI
D10     -> SUPPORTED_MC_12_D
B10     -> SUPPORTED_MC_12_B
R10     -> N/A unless a reliable canonical valuation bridge is supplied
```

Plausible ceiling:

```text
PLAUSIBLE_CEILING_MC =
max(route-peer P99 market cap, evidence-backed comparable market cap)
```

with the existing N>=30 rule.

## Integrity

Raw valuation evidence and peer-statistics are upstream materializer inputs.
They are excluded from the V1.2 0-100 model feature map, so a large multiple or
market-cap value cannot be misinterpreted as a score.

## WF3 completion

The previously-unfrozen definitions are now versioned separately as
`WF3_PEER_POLICY_V1_2026-10-07`:

- market-cap bucket boundaries
- profitability-state categories
- N<30 expansion sequence
- PIT sector/industry requirement

Historical data coverage can still be incomplete; missing classification,
forward evidence or peer observations remain N/A and are reported by the
whole-universe materializer. That is a data-coverage state, not an unfinished
WF3 formula/policy state.

