# Golden Test Cases — S15.3 V1.4 Recovered Final

These cases lock arithmetic, not market predictions.

## G1 — confirmation bonus, no disagreement penalty

```text
S15.3_V1.2 = 76
M10_D = 72
M10_C = 70
DMG = 2
CB = min(3, 0.30*(70-65)) = 1.5
DP = 0
S15.3_V1.4_BASE = 77.5
```

## G2 — disagreement penalty

```text
S15.3_V1.2 = 78
M10_D = 80
M10_C = 64
DMG = 16
CB = 0
DP = min(4, 0.20*(16-10)) = 1.2
S15.3_V1.4_BASE = 76.8
EARLY_ASYMMETRIC = TRUE
```

## G3 — robust destination confidence

```text
DF_B = 40
DF_M = 60
DF_U = 80
RDF10 = 0.35*40 + 0.50*60 + 0.15*80 = 56

DC=80, EQ=80, RP=80, ST=80, PIT=80
RC = 80
alpha = 0.60*((80-50)/50) = 0.36

BaseDF10 = 50
DF10_C = 0.64*50 + 0.36*56 = 52.16
```

## G4 — uncertainty / assumption / route penalties

```text
MC_Bear=80
MC_Base=100
MC_Bull=140
DU=30
DUP=3

AB=60
ABP=0.12*(60-35)=3

RouteGap=35
RDP=0.20*(35-15)=4
```

## G5 — EA10 boost and cap

```text
EA10=80
ProgressGate=PASS
EAB=min(5,0.40*(80-65))=5
ESP=0

If M10_C<70, final score is capped at 79.
```

## G6 — EA penalty

```text
EA10=45
EAB=0
ESP=min(4,0.20*(55-45))=2
```
