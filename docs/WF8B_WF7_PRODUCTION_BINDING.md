# WF8-B — WF7 Production Calibration Binding

Status: COMPLETE pending CI/merge.

## Rule

S15.3 V1.4.1 production calibration may consume empirical magnitude rates only
from a chain that has passed WF8-A as:

```text
PRODUCTION_EVIDENCE_READY
```

The provider reads the exact WF7 score bucket for the current V1.4.1 score.

Released fields:

```text
P(2X+)
P(5X+)
P(7X+)
P(10X+)
sample size
sample quality
WF7/WF6/hardening provenance
calibration cutoff
```

## Explicit non-outputs

WF7 does not currently validate:

- positive-return probability
- bear/base/bull terminal 12M return scenarios

Therefore WF8-B does not infer or manufacture these values.

## Firewalls

- No WF8 hardened chain -> NOT AVAILABLE.
- Score bucket N<30 -> NOT AVAILABLE.
- Incomplete/non-monotone magnitude frequencies -> NOT AVAILABLE.
- Calibration cutoff later than forecast as-of -> NOT AVAILABLE.
- Legacy `analysis_runs/backtest_results` empirical provider is not used for
  current S15.3 V1.4.1 desktop fallback.

This preserves the rule that S15.3 score is not itself a probability.
