# Phase25Z BKE — official dividends and observed free-price access

Audit date 2026-10-10; source window 2024-01-01–2025-09-30. This advances the Phase25Y-B single-security feasibility study with official event dates and a bounded no-key independent price availability probe. It does not buy data, query paid providers, write operational.db, edit S15/S16 or promote BKE to canonical. The official sources below are public leads; no claim of an exhaustive corporate-action ledger is made.

## SEC/issuer dividend chronology

Every row gives the board authorization, public announcement, record date and payment date in the linked issuer or SEC document. **BKE-specific ex-dates are not established in these documents**. The [NYSE generic ex-date rule](https://www.nyse.com/trade/ex-date-dividends) generally places ex-date on record date under the current T+1 settlement cycle, subject to exceptions, but cannot certify any particular BKE event and does not retroactively settle the January 2024 T+2-era date.

| Board | Announced | Special + regular cash/share | Record | Payment | BKE-specific ex-date | Official source |
| --- | --- | --- | --- | --- | --- | --- |
| 2023-12-04 | 2023-12-05 | $2.50 + $0.35 | 2024-01-12 | 2024-01-26 | UNVERIFIED | [SEC 8-K exhibit](https://www.sec.gov/Archives/edgar/data/885245/000088524523000054/bke202312058-kdivex.htm) |
| 2024-03-25 | 2024-03-26 | $0 + $0.35 | 2024-04-12 | 2024-04-26 | UNVERIFIED | [SEC 8-K exhibit](https://www.sec.gov/Archives/edgar/data/885245/000088524524000049/bke202403268-kdivex.htm) |
| 2024-06-03 | 2024-06-04 | $0 + $0.35 | 2024-07-12 | 2024-07-26 | UNVERIFIED | [SEC 8-K](https://www.sec.gov/Archives/edgar/data/885245/000088524524000065/bke-20240603.htm) |
| 2024-09-09 | 2024-09-10 | $0 + $0.35 | 2024-10-11 | 2024-10-25 | UNVERIFIED | [Issuer release](https://corporate.buckle.com/investor-relations/press-releases/press-release-details/2024/The-Buckle-Inc.-Reports-Quarterly-Dividend-b5b69d6a7/default.aspx) |
| 2024-12-09 | 2024-12-10 | $2.50 + $0.35 | 2025-01-15 | 2025-01-29 | UNVERIFIED | [SEC 8-K exhibit](https://www.sec.gov/Archives/edgar/data/885245/000088524524000117/bke202412108-kdivex.htm) |
| 2025-03-24 | 2025-03-25 | $0 + $0.35 | 2025-04-15 | 2025-04-29 | UNVERIFIED | [Issuer release](https://corporate.buckle.com/investor-relations/press-releases/press-release-details/2025/The-Buckle-Inc--Reports-Quarterly-Dividend-and-Announces-the-Appointment-of-Justin-D--Ellison-as-Vice-President-of-Information-Security/default.aspx) |
| 2025-06-02 | 2025-06-03 | $0 + $0.35 | 2025-07-15 | 2025-07-29 | UNVERIFIED | [SEC 8-K exhibit](https://www.sec.gov/Archives/edgar/data/885245/000088524525000072/bke202506028-kdivex.htm) |
| 2025-09-08 | 2025-09-09 | $0 + $0.35 | 2025-10-15 | 2025-10-29 | UNVERIFIED; payment after source window | [Issuer release](https://corporate.buckle.com/investor-relations/press-releases/press-release-details/2025/The-Buckle-Inc--Reports-Quarterly-Dividend-4c3f50d21/default.aspx) |

The [SEC 2024 10-K](https://www.sec.gov/Archives/edgar/data/885245/000088524524000051/bke-20240203.htm) and [2025 10-K](https://www.sec.gov/Archives/edgar/data/885245/000088524525000052/bke-20250201.htm) give annual dividend context and BKE common-stock/NYSE filing identity, but they do not establish each exchange ex-date, vendor adjustment factor or complete daily CIK/share-class continuity. SEC filing Accepted is not public dissemination or historical feature ingestion `available_at`.

## Actual free independent price availability

A single bounded Windows availability run queried the public Nasdaq BKE historical endpoint without credentials. The private report stores the response hashes, field names, count/date range and three Jan 2025 close samples; raw OHLC rows were held in memory and not committed or redistributed.

| Requested interval | Observed result | Constraint |
| --- | --- | --- |
| 2024-01-01 to 2025-09-30 | 244 BKE rows, 2024-10-09 through 2025-09-30 | `date,open,high,low,close,volume`; no adjusted-close field. |
| 2024-01-01 to 2024-10-08 | 0 rows | Earlier window inaccessible in this probe. Cause and full archive entitlement unverified. |

Nasdaq's [historical-data page](https://www.nasdaq.com/market-activity/quotes/historical) describes up to ten years of displayed daily prices, but the probed JSON endpoint returned only the observed subset above. Public page access does not establish bulk/API redistribution rights or a dividend-adjusted series. No price data from this endpoint is promoted into the model. The existing SimFin BKE rows remain retrospectively adjusted and uncertified. The January 2025 Nasdaq raw-close examples are private and cannot determine $2.50 special-dividend adjustment methodology by themselves.

## Acquisition decision and canonical blocker

| Option | Current cost from Phase25Y-B | What this probe adds | Decision |
| --- | --- | --- | --- |
| SEC + issuer | $0 | Seven paid-in-window dividend announcements plus October 2025 payment announced in-window. | Continue official event enumeration and obtain exchange-specific ex-date notices; still no price series. |
| Nasdaq public price page | No account used; API license unverified | Partial raw-close availability (244 rows), no 2024 early rows or adjustment field. | Research cross-check only; not a canonical feed. |
| [Massive Starter](https://massive.com/pricing) | $29/month listed | Potential 5-year bars and separate dividend factors, not sampled here. | Request licensed BKE sample and methodology if paid access later approved; no subscription started. |
| [Norgate Platinum](https://norgatedata.com/stockmarketpackages.php) | $346.50/6mo or $630/12mo listed | Survivorship-aware lead, but [raw actions/CIK/delisting return absent](https://norgatedata.com/data-package-faq.php). | Not sufficient alone. |
| [CRSP](https://www.crsp.org/research/) | Institutional quote required | Potential daily returns/distributions and delisting fields. | Seek scope/license quote only if procurement authorized; no access claimed. |

**Canonical BKE security-dates: 0. WF9: BLOCKED. Learning V3: NOT_TRAINED.** Missing mandatory artifacts: BKE-specific ex-dates and exhaustive corporate actions, dated daily issuer/share-class/exchange identity, independent full-window dividend-adjusted price and factor method, terminal/delisting audit, contemporaneous PIT membership, historical SEC public/feature ingestion timestamps, and mature 252-session labels. Buying a provider later cannot reconstruct an unarchived 2024–25 local ingestion clock.

## Reproduction

The optional `--online-probe` performs only two no-key Nasdaq availability requests, subject to changing availability. Omit it for fully offline event/eligibility verification. Output is create-only under private `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25z`.

```powershell
$root = "$env:LOCALAPPDATA\S153ResearchTerminal\runtime"
& "E:\M10\.venv\Scripts\python.exe" -m scripts.phase25z_bke_free_evidence --phase25w "$root\phase25w\pilot_cohort_research_only_v1.json" --phase25x "$root\phase25x\evidence_matrix_research_only_v2.json" --phase25y-b "$root\phase25y\bke_provider_feasibility_v1.json" --out "$root\phase25z\bke_free_evidence_next.json"
& "E:\M10\.venv\Scripts\python.exe" -m unittest tests.test_phase25z_bke_free_evidence -v
```

Observed private online report: `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25z\bke_free_evidence_probe_v1.json`, SHA-256 `995a97d66110950300042d17ff49606de512212081048f24cacdcd010e33cce3`. Tests use synthetic responses and no network. PR contains only code, tests and public references.
