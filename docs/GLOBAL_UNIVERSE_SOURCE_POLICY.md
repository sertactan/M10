# Global Universe Source Policy

M10 separates **reference coverage** from **authoritative model evidence**.

## Bundled data

Only source data with sufficiently clear redistribution rights may be packaged
inside a public Windows artifact.

### SEC EDGAR — bundled/open

The Windows build generates a current US universe seed from:

- https://www.sec.gov/files/company_tickers_exchange.json

The seed is used only to bootstrap security identity/universe metadata. SEC
fundamental and price evidence continues to follow the canonical PIT pipeline.

## Broad global reference

M10 can sync the Adanos Free Global Ticker Database at runtime as a broad
reference layer. The adapter uses the collision-safe core listing export.

Important: the upstream repository's MIT license applies to its code/original
project material, while its own source-licensing policy states that exchange
source rights vary. Therefore M10 does **not** bundle the mixed-source global CSV
inside the installer.

Rows obtained through this adapter are stored as:

- source_scope = REFERENCE_ONLY
- redistribution_status = LOCAL_REFERENCE_ONLY
- source_priority = 90

They may support symbol discovery, aliases, country/exchange filtering, ISIN
matching, and later official-source reconciliation. They must not silently
become authoritative S15.3 input evidence.

## Official local refresh targets

Market-specific adapters should prefer official sources and preserve source
provenance:

- US — SEC EDGAR; exchange directories only under their permitted usage.
- JP — JPX/TSE official listed-issue data.
- TR — Borsa Istanbul/KAP official sources subject to usage terms.
- HK — HKEX official securities/listing sources subject to usage terms.
- GB/EU — LSE/Euronext only after source-specific redistribution/local-use
  rules are encoded.

## Fail-closed rule

When source terms are unknown or restrictive:

1. do not commit raw rows to the public repository;
2. do not bundle those rows into the installer;
3. permit local personal-use sync only when the source terms allow it;
4. tag the result as reference/fallback, not canonical evidence;
5. retain the last-known-good local snapshot for offline use.
