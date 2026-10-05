# Phase 3 — Fundamental / SEC Engine Status

## Provider priority

1. SEC EDGAR — authoritative regulatory history
2. Finnhub — normalized fundamentals, analyst/revenue/EPS estimates, company metrics
3. SimFin — bulk historical normalized statements / local bootstrap
4. Financial Modeling Prep — normalized statements, ratios, fallback validation
5. Company Investor Relations — official KPI/guidance documents

## Implemented

- SEC Submissions ingestion:
  - 10-K / 10-K/A
  - 10-Q / 10-Q/A
  - 8-K / 8-K/A
  - 20-F / 20-F/A
  - 40-F / 40-F/A
  - 6-K / 6-K/A
  - filing date
  - acceptance timestamp
  - accession number
  - primary document URL
  - amendment flag
  - historical submissions files
- SEC Company Facts / XBRL ingestion and accession join
- canonical metric normalization for major statement concepts
- provider-isolated fundamental fact versioning
- PIT availability timestamp separate from filing date
- conservative fallback when a historical acceptance timestamp is unavailable
- Finnhub reported financials + current analyst estimates + company metrics
- SimFin chunked bulk statement bootstrap
- FMP normalized statement / ratio fallback
- structured official SEC/IR KPI and guidance ingestion
- canonical regulatory precedence: SEC > Finnhub > SimFin > FMP
- canonical guidance precedence: SEC > Company IR > Finnhub > FMP
- secondary providers can validate SEC but cannot overwrite SEC
- amendment/restatement history remains versioned
- historical as-of canonical snapshots
- exact-quarter-only TTM calculation; no silent Q4 derivation
- derived FCF = TTM CFO - abs(TTM CAPEX)
- source validation results

## Mandatory lineage retained for fundamental facts

- metric_name
- value
- period_end
- filing_date
- accepted_at
- available_at
- source
- source_document
- accession_number
- retrieved_at
- quality_status
- validation_status

## Important PIT rule

SEC facts become available at EDGAR acceptance time when available.
A later amendment/restatement never changes an earlier historical snapshot.

Current analyst estimates without a provider-supplied historical timestamp are available only from their retrieval time onward. They are never backfilled into older backtests.

## CLI

```powershell
python main.py --sync-fundamentals AAPL
python main.py --sync-fundamentals AAPL --fund-provider SEC_EDGAR
python main.py --show-fundamentals AAPL --fund-as-of 2025-05-05
python main.py --ingest-ir-json .\guidance.json --ir-ticker AAPL
```

## Deliberately not implemented here

- arbitrary web scraping of investor-relations sites
- LLM extraction of unstructured presentations/releases
- point-in-time historical analyst-estimate archives not exposed with reliable timestamps by a configured provider

## CI validation
GitHub Python CI runs compileall and the complete pytest suite for this phase before merge.
