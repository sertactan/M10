# Phase25V — Official identity/corporate-action ledger and local mature-label inventory

**As of 2026-10-10. Scope: research evidence ONLY.** The seven ticker cases below have independently located official event announcements, but these documents alone DO NOT certify any of the original 464 ambiguous Phase25R source rows, adjusted-price series, CIK-to-SimFinId joins, complete PIT universe or future returns. **Do not release the seven tickers from quarantine.** Existing Phase25L/25P/25R/25S work is preserved; this ledger adds missing cross-ticker boundary evidence.

## Seven Phase25R strong-cohort ambiguity cases

| Ticker | Authoritative identity and action evidence | Handling |
|---|---|---|
| **B** | Barnes Group (CIK 9984) acquired Jan 27 2025 for **$47.50 cash/share**, delisted at open. [Barnes SEC 8-K](https://www.sec.gov/Archives/edgar/data/9984/000114036125001965/ef20042046_8k.htm). Separately Barrick renamed/ticker **GOLD -> B** effective May 9 2025, new CUSIP **06849F108**. [Barrick issuer release](https://www.barrick.com/English/news/news-details/2025/barrick-announces-name-change-to-barrick-mining-corporation-and-election-of-directors/default.aspx). | Old B and new B **different securities**; Barnes needs terminal $47.50, verified adjustment and date-bound identity. |
| **CWBC** | Original Community West Bancshares **CWBC** last traded Mar 28 2024; effective Apr 1 2024 old CWBC merged into CVCY for **0.79 successor shares/old share**; CVCY renamed/new ticker **CWBC**, CUSIP **203937107**. [Nasdaq ECA](https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2024-160). Nasdaq explicitly warns to keep old CWBC price history separate and continue **CVCY** history in new CWBC. [Nasdaq DTN](https://www.nasdaqtrader.com/TraderNews.aspx?id=dtn2024-8). | **No old-CWBC/new-CWBC direct price stitching.** |
| **FUN** | Cedar Fair LP + old Six Flags merger closed July 1 2024. Combined Six Flags Entertainment CIK **1999001** began trading as FUN July 2. Old Cedar Fair unit exchange **1.0 new common share**, old SIX common **0.58 new share**. [SEC issuer closing exhibit](https://www.sec.gov/Archives/edgar/data/701374/000119312524173426/d813704dex991.htm). | Keep old Cedar Fair units, old SIX and new FUN corporate share identity separate and normalize exchange ratios/rights. |
| **STRR** | Hudson Global HSON common -> renamed Star Equity Holdings STRR at Sep 5 2025 opening after Aug 22 merger; HSONP preferred -> STRRP. [SEC issuer exhibit](https://www.sec.gov/Archives/edgar/data/1210708/000121070825000081/pressreleaseofhudsonglobal.htm). | Date-bound common/preferred identity; no automatic return continuity from ticker alone. |
| **TEL** | Sep 30 2024 TE Connectivity Ltd (Swiss parent) -> TE Connectivity plc (Irish parent) by **one Irish plc common for one Swiss Ltd common**, ticker TEL retained. [Issuer announcement](https://investors.te.com/news-releases/press-release-details/2024/TE-Connectivity-completes-change-in-place-of-incorporation-to-Ireland/default.aspx). | Legal issuer and shares changed despite same symbol; require dated CUSIP/security identity and price evidence. |
| **TTE** | TotalEnergies 2024 NYSE TTE security was an **ADS/ADR**, one deposited ordinary share per ADS. [SEC 2024 20-F](https://www.sec.gov/Archives/edgar/data/879764/000110465925029751/tot-20241231x20f.htm). The **NYSE ordinary share** replacement happened **Dec 8 2025**, OUTSIDE the Jan2024–Sep2025 test window. [Issuer release](https://corporate.totalenergies.us/news/totalenergies-announces-commencement-trading-its-ordinary-shares-nyse). | Keep the 2024–2025 historical TTE class as ADS; do not project 2025 conversion backwards or mix FX/depository units. |
| **VIVO** | Meridian Bioscience VIVO acquired for **$34.00/share cash** Jan 31 2023; last traded Jan 30, suspension Feb 1 2023. [Nasdaq completed-merger notice](https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2023-49). | This old VIVO cannot be assumed to have actively traded as the same security in 2024–2025. A later VIVO ticker requires separate issuer/class evidence. |

## SITC linked corporate-action case (already scoped in PR #157)

- SITE Centers CIK **894315** completed a **1 new share / 4 old reverse split** effective Aug 16 2024 after hours (adjusted trading Aug 19), followed by **Oct 1 2024** distribution of **2 CURB common shares for each 1 SITC** held at Sep 23 record date.
- Primary [SEC FY2024 10-K](https://www.sec.gov/Archives/edgar/data/894315/000095017025029989/sitc-20241231.htm) and [SEC October 1 issuer exhibit](https://www.sec.gov/Archives/edgar/data/894315/000119312524231147/d104351dex991.htm).
- Source evidence is NOT certified total-return pricing: use actual SITC/CURB dated vendor price pairs, distribution/ex-date rights, corporate-action adjustment lineage and independently stamped public-availability times. Reuse Phase25S script; never invent ex-date prices or promote raw source bars.

## Run local mature outcome inventory safely

The local Windows M10 data is not present in this GitHub repository and must never be uploaded publicly. Use **actual** active runtime paths, not automatically these example locations:

~~~powershell
cd E:\M10
& 'E:\M10\.venv\Scripts\python.exe' -m scripts.phase25v_local_mature_learning_inventory `
    --operational-db 'E:\M10\data\runtime\operational.db' `
    --learning-db 'E:\M10\data\runtime\meridyen_learning.sqlite3' `
    --cutoff 2026-10-10
~~~

The CLI **only prints aggregate JSON to stdout**. Both SQLite sources open mode=ro / query_only; no import, model calls, scheduler or database creation. It distinguishes missing DB (null) from verified empty (0). Reports complete WF5/WF6 source-run counts, WF5 observations, legacy learning outcomes, noncanonical research routes, raw native label rows, distinct security/date signals, mature-by-cutoff records, 2X/5X/10X recorded outcomes, batch duplication, invalid dates and censored/out-of-window rows. It never publishes individual positions, tickers or private records.

A positive label count is a **DB-reported count**, NOT a certified mature outcome: without independent PIT/security identity, prices, source timestamps, full corporate-action/dividend/delisting lineage and original WF5+WF6 hashes, mark NOT_PIT_CERTIFIED. Never advertise Precision@K, market-wide 10X recall or trained Learning V3 from this inventory.

## Remaining mandatory gates

1. Reconcile **each of the 464 original private conflict rows** and the 30 ambiguous ticker strings to dated real CIK/CUSIP/class, exchange and SimFinId; preserve seven strong ticker quarantines until row-level validation completes.
2. For each issuer, certify **all** applicable split/dividend/merger/ADR/spinoff/delisting actions and real adjusted price paths, not only the eight researched examples.
3. Separate SEC Accepted, public disseminated_at, vendor available_at and model signal time, no retrospective membership-as-PIT.
4. Read actual Windows learning SQLite; compare any native label counts with wf5-labels-audit and Phase15 OOS SHA256 validation only when complete eligible source-run IDs and batch hashes exist.

**Never edit S1/S2/S14/S15/S16 frozen models, production SQLite, source CSV, Hermes branches, or private learned weights.** The present addition is a source-backed research guide and an isolated, read-only diagnostic.
