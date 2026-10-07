# WF2 Destination Raw-Input Contract v1

This is a data-layer contract. It does not alter S15.3 V1.2/V1.4.1 mathematics.

## Fundamental / Inflection raw inputs

All values must be PIT and carry provenance.

```text
RAW_FWD_REVENUE_12
RAW_FWD_EBITDA_12
RAW_FWD_FCF_12
RAW_NET_DEBT

PEER_P90_SALES_MULTIPLE
PEER_MEDIAN_SALES_MULTIPLE
PEER_P90_EBITDA_MULTIPLE
PEER_MEDIAN_EBITDA_MULTIPLE
PEER_P90_FCF_MULTIPLE
PEER_MEDIAN_FCF_MULTIPLE
```

The materializer applies the already-frozen canonical rule:

```text
M* = min(P90_peer, 2 * Median_peer)
SalesEq  = Revenue12 * M_sales - NetDebt
EBITDAEq = EBITDA12 * M_ebitda - NetDebt
FCFEq    = FCF12 * M_fcf
SupportedMC12 = median(valid positive equity estimates)
```

If only one valuation method is valid, the existing canonical specification says
ModelFit is reduced by 15. The destination materializer records that penalty in
evidence but does not manufacture a MODEL_FIT score.

## Ceiling raw inputs

```text
ROUTE_PEER_P99_MARKET_CAP
ROUTE_PEER_N
EVIDENCE_BACKED_COMPARABLE_MC
```

Canonical rule:

```text
PlausibleCeilingMC =
max(P99MarketCap_route_peer, EvidenceBackedComparableMC)
```

Peer P99 is eligible only when route-peer N >= 30. If N<30 and there is no
evidence-backed comparable, the ceiling stays N/A.

## Free-data policy

Forward inputs may come from timestamped SEC/issuer guidance or another
timestamped canonical estimate row. A present-day estimate cannot be backfilled
into an earlier observation.

Peer statistics must be generated from the same-date PIT cohort. Their
percentile implementation will be versioned separately before market-prevalence
walk-forward calibration is enabled.
