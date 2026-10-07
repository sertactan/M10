# WF3 Peer Policy V1

Formula/policy version: `WF3_PEER_POLICY_V1_2026-10-07`.

This is a **new explicit peer-policy version** created to close previously
unfrozen S15.3 destination-cohort definitions. It does not claim these rules
were present in the recovered V1.2/V1.4 source.

## Market-cap buckets

```text
MICRO < $300M
SMALL $300M .. < $2B
MID   $2B .. < $10B
LARGE $10B .. < $200B
MEGA  >= $200B
```

## Profitability state

PIT TTM evidence, first matching state:

```text
PROFITABLE_FCF        TTM FCF > 0
OPERATING_PROFITABLE  otherwise TTM operating income > 0
PRE_PROFIT_REVENUE    otherwise TTM revenue > 0
PRE_REVENUE_OR_BINARY explicitly known TTM revenue <= 0
N/A                    insufficient PIT evidence
```

## N<30 expansion

As-of month and route are never relaxed.

```text
E0 exact: industry + sector + bucket + profitability
E1 drop profitability
E2 allow adjacent market-cap bucket
E3 drop industry, retain sector
E4 all market-cap buckets inside sector
E5 route-only inside same as-of month
```

Select the first stage reaching N>=30. N=30-49 is low-confidence; N>=50 normal.
If E5 remains below 30, percentile legs remain N/A.

## PIT classification

Historical peer observations require an entry in
`security_classification_history` whose effective interval contains the
observation date and whose `available_at <= as_of`.

Current `security_master.sector/industry` is not backfilled into history.

## Whole-universe materialization

```text
python scripts/materialize_wf3_destination.py --date YYYY-MM-DD
```

The report exposes route, classification, peer-observation and destination
coverage separately. Missing evidence is never replaced by zero.
