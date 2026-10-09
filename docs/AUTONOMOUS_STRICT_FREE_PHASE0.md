# Meridyen Autonomous — Strict Free Phase 0

Status: isolated policy prototype only. **Not wired to any HTTP client, scheduler,
private plugin or Google Cloud runtime.** It must never be described as live billing
protection until every execution path calls it before network requests.

## Verified source-code inventory (2026-10-10)

- Existing: M10 S15.3 V1.2/V1.4/V1.4.1, S16, S16-EA V1.3,
  SEC EDGAR, Massive, provider routing, local SQLite/DuckDB/Parquet,
  Learning V2/V3, model and backtest test suites.
- Not established: current Windows production WF9 `COMPLETE_AND_ACTIVATED`,
  complete 144-month survivorship-free US PIT dataset, real mature-label OOS
  benchmark, activated cloud deployment, cloud cost controls, or autonomous
  FREE LLM inference end-to-end.
- Source graph snapshot `f5b3309` is stale against inspected HEAD `38f00ea`.
- Existing untracked local evidence files were left untouched.

## Safety gate

`core/runtime/strict_free.py` contains a pure Python `authorize_free_llm`
preflight. The decision blocks missing, stale or future evidence, absent model
identity, unverified free tier, non-hard-capped billing and exhausted quotas.
Positive preflight is **not** sufficient to send requests: caller must atomically
reserve a request in a persistent quota ledger and independently enforce cloud
billing and infrastructure quotas. Client integration is a later phase.

**No paid fallback**, **no automatic provider switch**, **no live brokerage
orders**, **no secrets in logs**, and **no automatic production model edits**.
Cloud budget alerts alone are not hard spending caps. If hard no-billable
enforcement is not possible, the cloud/LLM path must remain disabled.

## Next gates

1. Verify provider/model exact IDs and free quota on the account, not from
   assumed marketing names. Require a demonstrable non-billable configuration.
2. Build persistent atomic quota reservations and adapter tests with mock HTTP.
3. Independently prove all possible invocation paths pass the gate.
4. Inspect Google Cloud Billing, Cloud Run/Jobs, Scheduler and storage details
   without creating billable resources; require approval before creation.
5. Execute production-readiness and PIT/OOS audits separately; synthetic
   unit tests are not evidence of real investment returns.
