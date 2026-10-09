# Phase25M - Secondary P2 primary-issuer distribution evidence, not adjusted price certification

This offline report extends the previous Phase25j 127-candidate/167-source-anomaly queue with **six** confirmed issuer cash/elective distributions covering **three** issuers and **13** source anomaly observations (CRCT 3, IEP 6, EC 4).

Official primary references:

- CRCT 2024 10-K SEC (CIK 0001828962) records July 2024 one-time USD 0.40 + USD 0.10 regular Class A/B common share distributions, record 2024-07-02, payable 2024-07-19; and USD 0.10 Class A/B regular January 2025 record 2025-01-07, payable 2025-01-21. https://www.sec.gov/Archives/edgar/data/1828962/000182896225000039/crct-20241231.htm
- CRCT first quarter 2025 official results declare USD 0.75 special + USD 0.10 regular Class A/B common share, record 2025-07-07, payable 2025-07-21. https://investor.cricut.com/news-releases/news-release-details/cricut-inc-reports-first-quarter-2025-financial-results
- IEP official 2025 Q1 results declare **USD 0.50 per depositary unit**, record 2025-05-19, payable ~2025-06-25, with holder cash-vs-additional-unit election. It is **not safe** to treat this as an ordinary one-leg cash dividend adjustment. https://ielp.gcs-web.com/news-releases/news-release-details/icahn-enterprises-lp-nasdaq-iep-today-announced-its-first-0
- IEP SEC 2024-05-28 8-K documents CIK 0000813762, symbol IEP on Nasdaq **depositary limited-partner units**, issuer class (not entire timeline SimFinId proof). https://www.sec.gov/Archives/edgar/data/813762/000110465924065621/tm2415571d1_8k.htm
- EC Ecopetrol official 2024 communication gives COP 278 ordinary plus COP 34 extraordinary = COP 312 **per local share**, payments 2024-04-03 and 2024-06-26. https://www.ecopetrol.com.co/wps/wcm/connect/8f07b7a3-b160-483f-a5e6-e5a17bd732bc/dividendos-eng.pdf?CVID=oVXCQ8k&MOD=AJPERES
- EC official shareholder record gives 2025 COP 214 per local share payments 2025-04-04 and 2025-04-29. https://www.ecopetrol.com.co/wps/portal/Home/en/investors/information-for-shareholders/dividends

These dates are **record/payment**, not independently documented Nasdaq/NYSE **ex-dividend** dates. USD/ADS conversion for EC, optional units for IEP, broker withholding, vendor adjusted factor and precise source-event attribution need independent corroboration. Therefore the report marks **all 13** source warnings `source_anomaly_explained=false`, `historical_daily_security_identity_proven=false`, `PIT_backtest_eligible=false`.

Run on Windows from fresh main worktree:

    & "E:\M10\.venv\Scripts\python.exe" -m scripts.phase25m_issuer_primary_action_evidence_triage

Private output only: `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25m\issuer_cash_evidence_secondary_P2.json`.

No SEC source or SimFin file changes; research report not a canonical market-wide split/dividend schedule. The other 114 candidate issuers and 154 unrelated source warnings are not assigned unverified actions.
