# Dual-Magnitude / Destination Specification — Recovered Final

## V1.2 discovery magnitude

```text
M10_D = canonical V1.2 M10
```

## V1.3 Confidence-Weighted Robust Destination

Scenario route destination:

```text
RDF10 = 0.35 DF_B + 0.50 DF_M + 0.15 DF_U
```

Route confidence:

```text
RC_r =
0.25 DC
+0.25 EQ
+0.20 RP
+0.15 ST
+0.15 PIT
```

```text
alpha_r = 0.60 * Clip((RC_r - 50) / 50, 0, 1)
```

Confirmation destination:

```text
DF10_C = (1 - alpha_r) * BaseDF10 + alpha_r * RDF10
```

Destination uncertainty:

```text
DU = Clip(
  100 * (MC_Bull - MC_Bear) / (2 * MC_Base),
  0,
  100
)

DUP = min(10, 0.10 * DU)
```

Assumption-burden penalty:

```text
ABP = min(10, 0.12 * max(0, AB - 35))
```

Route-disagreement penalty:

```text
RouteGap = |DF10_route1 - DF10_route2|
RDP = min(8, 0.20 * max(0, RouteGap - 15))
```

Confirmation magnitude:

```text
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

The scenario market caps and scenario DF values are canonical inputs. The recovered work did
not freeze their upstream construction, so V1.4 must fail closed / return INCONCLUSIVE when
they are absent rather than fabricate them.

## V1.2 route-destination blend retained as historical context

```text
one active destination route:
DF10* = 0.40 BaseDF10 + 0.60 RouteDF10

two active destination routes:
DF10* = 0.25 BaseDF10 + 0.45 PrimaryRouteDF10 + 0.30 SecondaryRouteDF10

no active destination route:
DF10* = BaseDF10
```

V1.3 confirmation uses the confidence-weighted robust `DF10_C` above.
