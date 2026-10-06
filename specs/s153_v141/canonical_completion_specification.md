# S15.3 V1.4.1 Canonical Completion Specification

Canonical formula version: `S15.3_V1.4.1_CANONICAL_COMPLETION_2026-10-07`.

## 1. Scope and immutability

V1.4.1 is a **new canonical completion layer**. It does not alter the recovered
S15.3 V1.4 core. The V1.4 formulas for RDF10, route confidence, alpha, DF10_C,
DU/DUP, ABP, RDP, M10_C, DMG, CB/DP, Early Asymmetric, EA10 and all classification
gates remain unchanged.

V1.4.1 freezes only the previously-unfrozen upstream construction of:

- `V14_DF_B / V14_DF_M / V14_DF_U`
- `V14_MC_BEAR / V14_MC_BASE / V14_MC_BULL`
- `V14_RC_DC / V14_RC_EQ / V14_RC_RP / V14_RC_ST / V14_RC_PIT`
- `V14_AB`
- `V14_ROUTE_GAP`

All inputs are point-in-time and must come from the same canonical feature layer
used by V1.2. Missing required evidence remains N/A and fails closed.

## 2. Route-confidence feature generation

The recovered V1.4 formula remains:

```text
RC =
0.25 DC +
0.25 EQ +
0.20 RP +
0.15 ST +
0.15 PIT
```

V1.4.1 binds the upstream components as follows:

```text
DC  = DATA_COVERAGE
EQ  = SOURCE_QUALITY
ST  = MODEL_FIT
PIT = PIT_INTEGRITY
```

Route Purity (`RP`) measures separation between the selected primary and
secondary V1.2 route scores.

```text
if no secondary route:
    RP = 100
else:
    RouteMargin = max(0, PrimaryRouteScore - SecondaryRouteScore)
    RP = Clip(50 + 2 * RouteMargin)
```

No unavailable confidence leg is imputed. If any of DC/EQ/RP/ST/PIT is missing,
V1.4.1 returns `INCONCLUSIVE_V1_4_1_INPUTS`.

## 3. Assumption Burden

All stretch scores are 0-100 where **higher means more assumption burden**.

### Growth evidence and GrowthStretch

```text
GrowthEvidence =
WA(
  0.35 MCR,
  0.25 TAMMC,
  0.20 GP,
  0.10 RPS,
  0.10 FPS
)

GrowthStretch = 100 - GrowthEvidence
```

GrowthEvidence requires at least 3 of the 5 legs and at least one of MCR/TAMMC.
Otherwise GrowthStretch is N/A.

### MarginStretch

```text
MarginStretch = 100 - ETRQ
```

### MultipleStretch

```text
MultipleStretch =
0.60 * (100 - RER)
+0.40 * PIR_VAL
```

Both RER and PIR_VAL are required.

### FundingStretch

```text
FundingStretch = 100 - V
```

where V is canonical V1.2 Viability.

### ExecutionStretch

```text
ExecutionEvidence =
0.60 * EXEC
+0.40 * T10

ExecutionStretch = 100 - ExecutionEvidence
```

Both EXEC and T10 are required.

### Canonical AB

```text
AB =
0.30 GrowthStretch
+0.20 MarginStretch
+0.20 MultipleStretch
+0.15 FundingStretch
+0.15 ExecutionStretch
```

All five stretch blocks are required. The recovered V1.4 AB penalty remains
unchanged:

```text
ABP = min(10, 0.12 * max(0, AB - 35))
```

## 4. Scenario supported-market-cap construction

This layer is supported-market-cap math, not an analyst price target.

For destination-backed routes, primary supported market cap is:

```text
F10 / I10 -> SUPPORTED_MC_12_FI
D10       -> SUPPORTED_MC_12_D
B10       -> SUPPORTED_MC_12_B
R10       -> SUPPORTED_MC_12_R
```

Q10 has no canonical supported-market-cap construction in V1.2 and therefore
remains fail-closed in V1.4.1:

`INCONCLUSIVE_V1_4_1_Q_ROUTE`.

Let `S` be the positive primary-route supported market cap and `P` be
`PLAUSIBLE_CEILING_MC` when present and positive.

```text
MC_Base = min(S, P)   when P is available
MC_Base = S           otherwise
```

Scenario width is determined only by canonical route confidence:

```text
WidthPct =
Clip(
  15 + 35 * (100 - RC) / 100,
  15,
  50
)

w = WidthPct / 100
```

Then:

```text
MC_Bear = MC_Base * (1 - w)

MC_Bull_raw = MC_Base * (1 + w)

MC_Bull =
min(MC_Bull_raw, P)   when P is available
MC_Bull_raw           otherwise
```

All scenario market caps must be > 0.

## 5. Scenario destination factors

Scenario destination factors reuse the **unchanged V1.2 10X destination-score
function and knots**.

For current market cap `C`:

```text
DF_B = DestinationScore(MC_Bear, C, 10)
DF_M = DestinationScore(MC_Base, C, 10)
DF_U = DestinationScore(MC_Bull, C, 10)
```

The V1.2 destination knots remain:

```text
supported_mc / (10 * current_mc)

0.20 -> 0
0.35 -> 25
0.50 -> 50
0.75 -> 75
1.00 -> 100
```

No new destination normalization is introduced.

## 6. RouteGap

For each selected route, calculate its own V1.2 destination factor using the
route's canonical destination rule.

```text
if no secondary route:
    RouteGap = 0
else:
    RouteGap = abs(DF10_primary_route - DF10_secondary_route)
```

For F10/I10/D10/B10/R10, use the corresponding route SupportedMC and the V1.2
destination-score function. Q10 route destination uses the unchanged V1.2
Q-destination score when it is the secondary route.

If a selected secondary route exists but its route destination cannot be
calculated, RouteGap is N/A and V1.4.1 fails closed.

The recovered penalty remains unchanged:

```text
RDP = min(8, 0.20 * max(0, RouteGap - 15))
```

## 7. Downstream V1.4 core remains frozen

After materializing the upstream features above, V1.4.1 calls the recovered V1.4
engine unchanged:

```text
RDF10 = 0.35 DF_B + 0.50 DF_M + 0.15 DF_U

DF10_C = (1-alpha) * BaseDF10 + alpha * RDF10

DU =
Clip(
  100 * (MC_Bull - MC_Bear) / (2 * MC_Base),
  0,
  100
)

M10_C_raw =
0.30 DF10_C
+0.15 MCH10
+0.15 ETRQ
+0.15 RER
+0.10 CMAG
+0.05 FCVX
+0.10 HMG10

M10_C =
Clip(
  M10_C_raw
  -0.10 PIR
  -DUP
  -ABP
  -RDP
)
```

All Dual-Magnitude and final V1.4 gates remain exactly as frozen in the recovered
V1.4 specification.

## 8. Minimum-data / fail-closed rule

A V1.4.1 score is READY only when:

1. V1.2 itself is READY.
2. Current market cap is positive.
3. Primary route is destination-backed (F10/I10/D10/B10/R10).
4. Primary route SupportedMC exists and is positive.
5. DC/EQ/RP/ST/PIT are all available.
6. All five AB stretch blocks are available.
7. DF_B/DF_M/DF_U and MC_Bear/Base/Bull can be produced.
8. RouteGap can be produced.
9. All recovered V1.4 required inputs remain available.

Otherwise return `INCONCLUSIVE_V1_4_1_INPUTS` (or
`INCONCLUSIVE_V1_4_1_Q_ROUTE` for primary Q10).

## 9. Versioning rule

- S15.3.1.4 / V1.4 Recovered Final remains immutable.
- S15.3.1.4.1 is the first version that canonically freezes the upstream
  destination-scenario and Assumption-Burden construction.
- Backtests and live scans must store the exact formula version string.
