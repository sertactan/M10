# V1.4 Factor / DNA Definitions — Recovered Final

V1.4 reuses the full canonical V1.2 factor/DNA/router stack and adds the following confirmation inputs.

## V1.3 robust-destination inputs

```text
V14_DF_B, V14_DF_M, V14_DF_U
V14_MC_BEAR, V14_MC_BASE, V14_MC_BULL
V14_RC_DC, V14_RC_EQ, V14_RC_RP, V14_RC_ST, V14_RC_PIT
V14_AB
V14_ROUTE_GAP
```

`V14_AB` is the canonical 0–100 Assumption Burden score. Its recovered parent expression is:

```text
AB = WA(GrowthStretch, MarginStretch, MultipleStretch, FundingStretch, ExecutionStretch)
```

The original work did not freeze component weights, therefore V1.4 does not invent them.
`V14_AB` must be materialized upstream as a canonical feature.

## Destination-route activation factors

SPIN:

```text
SpinGate =
0.25 Freshness
+0.20 ForcedSeller
+0.20 StandaloneInflection
+0.20 PeerDislocation
+0.15 Catalyst

active if SpinGate >= 65
```

CYCLE:

```text
CycleGate =
0.25 DemandAcceleration
+0.20 SupplyTightness
+0.15 ASPTrend
+0.15 BacklogBookBill
+0.15 MarginTorque
+0.10 CapacityLeadTime

active if:
CycleGate >= 65
DemandAcceleration >= 60
SupplyTightness >= 60
```

ASSET:

```text
AssetGate =
0.25 ResourceQuality
+0.20 TechnicalMaturity
+0.15 Funding
+0.15 Permitting
+0.10 CommodityRegime
+0.15 Catalyst

active if AssetGate >= 60
```

When several destination routes are active they are ranked by gate score.

## EA10 factors

Cycle:
`DEMA, SCTA, MCA, CAPA, DRA, CGC`.

Asset:
`RQA, TDA, FRA, CRA, DRA, CGC`.

Progress evidence:
`DRA, CGC, RouteEvidenceAccel, MI`.
