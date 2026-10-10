---
name: meridyen-fundamentals
description: SEC/CIK, dilution, cashflow, valuation and S15.3 source-based research.
---
# A3 — Fundamental Analyst
Use the existing SEC EDGAR and M10 S15.3 implementations unchanged. Original
SEC accession, acceptance time and as-of evidence are required. Check
CIK/ticker historical identity, filing restatements and licensing. Missing
required inputs or historical membership must remain INCONCLUSIVE.
Never produce canonical scores from LLM interpretation or synthetic fixture
and never overwrite production data.

## Official issuer corporate-action review

Phase25M issuer distributions are research evidence for CRCT, IEP and EC;
the six references cover 13 of 167 non-P1 source warnings, **not**
certified ex-dividend dates or vendor adjustment factors. IEP's
cash-or-unit election and EC's COP local-share versus USD ADS units
cannot be treated as ordinary USD cash dividends. Phase25S supports a
SITC 1-for-4 reverse split effective 2024-08-16 and an Oct 2024
CURB spinoff, but does not certify fully adjusted total-return bars,
SEC public `available_at`, or full-window SimFinId↔CIK identity.
Use the existing `phase25m`, `phase25r`, `phase25s` read-only reports
and source links. Do not infer missing history from present-day CIK.

## Phase25L B/FUN official identity transitions

SEC/issuer evidence now documents Barnes NYSE:B cash merger delisting
on 2025-01-27 ($47.50 for eligible common shares); Barrick GOLD→B
ticker effective 2025-05-09; and former Cedar Fair LP FUN /
Six Flags SIX conversion into new FUN common shares from 2024-07-02.
Treat these as *dated issuer action facts*, not a vendor
SimFinId↔CIK full-window crosswalk or a verified backtest payoff.
Read the existing local Phase25L report through the read-only
`phase25_source_evidence` adapter; keep the 464 historical
source identity conflicts quarantined.
