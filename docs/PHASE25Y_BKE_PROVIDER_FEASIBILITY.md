# Phase25Y provider feasibility: BKE (research only)

Audit date: 2026-10-10. Window: 2024-01-01 to 2025-09-30. This offline investigation reuses the private Phase25W 25-security pilot and Phase25X eight-security matrix read-only. It makes no vendor data query or purchase. The advertised provider datasets below are procurement leads, not observed BKE rows.

## Starting evidence

BKE is Phase25W SimFinId 196385, with 438 retrospective source-price rows and 21 retrospective monthly ticker observations. Phase25X shows present-day local CIK lead 0000885245, 318 local period-scoped SEC fact rows, 11 accessions, and zero fact rows with accepted_at. The official [2024 10-K filing detail](https://www.sec.gov/Archives/edgar/data/885245/000088524524000051/0000885245-24-000051-index.htm) displays Accepted 2024-04-03 15:59:57. Its [cover](https://www.sec.gov/Archives/edgar/data/885245/000088524524000051/bke-20240203.htm) identifies BKE common stock on NYSE. This is a dated filing anchor, not daily identity continuity.

The official [December 2024 8-K exhibit](https://www.sec.gov/Archives/edgar/data/885245/000088524524000117/bke202412108-kdivex.htm) announces a $2.50 special dividend and $0.35 regular dividend, with January 15, 2025 record and January 29 payment dates. It proves those announcements, not a complete action ledger or ex-date and adjustment chain. BKE's Phase25X gates remain historical identity PARTIAL; actions BLOCKED; independent adjusted price BLOCKED; delisting payoff BLOCKED; SEC available_at PARTIAL; contemporary membership BLOCKED. Canonical accepted: 0; WF9: BLOCKED.

The SEC says its submissions API is typically updated within a second and XBRL APIs within a minute, and filings often appear on sec.gov within 1–3 minutes of EDGAR acceptance. These are typical service delays, not historical per-feature capture evidence. [SEC API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [SEC FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions).

## Provider and cost matrix

Public list prices viewed 2026-10-10; USD, before any tax, enterprise license, or redistribution terms.

| Route | Published cost | Potential evidence | Remaining limit |
| --- | --- | --- | --- |
| SEC EDGAR and issuer filings | $0 API/key cost; fair-use limits | Official CIK, accession, Accepted, 10-K class, 8-K action announcements. [SEC](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) | Needs complete filing enumeration and public/feature capture timestamps. No independent daily price or terminal return. |
| Massive Stocks Basic | [$0/month](https://massive.com/pricing), five calls/minute, two years history | Reference, corporate action, split-adjusted bars advertised. | Rolling two-year window on audit date excludes January–September 2024. Bars are [split-adjusted, not dividend-adjusted](https://massive.com/knowledge-base/article/is-massives-stock-data-adjusted-for-splits-or-dividends). No BKE response verified. |
| Massive Stocks Starter | [$29/month](https://massive.com/pricing), individual/nonprofessional, five years history | Candidate independent bars, [dividend adjustment factors](https://www.massive.com/docs/rest/stocks/corporate-actions/dividends), split events and [ticker-event history](https://massive.com/knowledge-base/article/how-does-polygon-handle-ticker-changes-and-acquisitions). | No BKE sample acquired; total-return bars not native. Need reconcile special dividend, rights, spinoff and any exit payoff, plus licensing and PIT lineage. |
| Norgate US Stocks Platinum | [$346.50/6 months or $630/12 months](https://norgatedata.com/stockmarketpackages.php); [three-week trial](https://norgatedata.com/data-package-faq.php) limited to two years | Survivorship-free delisted series and [total-return adjustment mode](https://norgatedata.com/data-package-faq.php). | Trial cannot cover full window at audit date. Vendor explicitly lacks direct action details, historical exchange location, CIK, and [delisting return/recovery](https://norgatedata.com/data-package-faq.php). Windows proprietary database access lapses with subscription. |
| CRSP US Stock Database, possibly linked to Compustat | [Institutional quote required](https://www.crsp.org/research/) | [Daily prices, returns, distributions, historical identifiers and delisting fields](https://www.crsp.org/research__trashed/crsp-us-stock-databases/). [Terminal-return methodology](https://www.crsp.org/crsp_pdf/crsp-us-stock-indexes-databases-calculations-index-methodologies-guide-flat-file-format-2-0/) includes explicit missing-value states. | Need license, BKE PERMNO-to-CIK/class link and actual coverage audit. Cannot recreate unarchived local 2024–25 SEC-feature ingestion clock. |

Norgate says its permanent assetid is not CIK and it provides no other unique identifier; [its FAQ](https://norgatedata.com/data-package-faq.php) says raw corporate-action details and delisting return are not supplied. Massive documents split-adjusted bars, with separate dividend factors; a factor is a calculation input, not a verified BKE total-return series. CRSP is the strongest candidate for a licensed market-data backbone, but its advertised fields alone do not prove BKE coverage or historical available_at.

## Acceptance artifacts still needed

| Gate | Current | Required artifact |
| --- | --- | --- |
| CIK and traded share class | PARTIAL | Dated security-level CIK, class and exchange intervals covering every BKE session, reconciled with SEC covers. |
| Official corporate actions | BLOCKED | Enumerated SEC/issuer split, normal/special dividend, rights, spinoff and merger declarations, ex/effective dates and cash/share terms; independent feed reconciliation. |
| Independent adjusted price | BLOCKED | Licensed raw and total-return BKE daily bars, adjustment factors and special-dividend reconciliation against source bars. |
| Delisting/terminal payoff | BLOCKED | Historical listing-status and exit audit; actual payoff if delisted or explicit missing state. A null local delisted_date is not a no-delisting certificate. |
| SEC publication and feature available_at | PARTIAL | Per-accession Accepted, observed public dissemination, archived local feature-ingestion timestamps and restatement lineage. |
| Contemporary PIT membership | BLOCKED | Archived 2024–25 universe observation or independently certified as-of membership. |

Technical blocker: No held source bundle covers all gates and no archived 2024–25 feature-ingestion timeline has been shown. A low-cost acquisition trial would request a dated BKE sample under Massive Starter at $29 for one month if eligible, then reconcile against free SEC filings. Norgate Platinum costs at least $346.50 for six months but still lacks event/terminal fields. CRSP requires a quote. No subscription was started.

## Offline Windows reproduction

Use the existing private Phase25W and Phase25X JSON paths with scripts.phase25y_provider_feasibility. Example:

    python -m scripts.phase25y_provider_feasibility --phase25w "$env:LOCALAPPDATA\S153ResearchTerminal\runtime\phase25w\pilot_cohort_research_only_v1.json" --phase25x "$env:LOCALAPPDATA\S153ResearchTerminal\runtime\phase25x\evidence_matrix_research_only_v2.json" --out "$env:LOCALAPPDATA\S153ResearchTerminal\runtime\phase25y\bke_provider_feasibility_v1.json"
    python -m unittest tests.test_phase25y_provider_feasibility -v

The output is create-only, private, and records source SHA-256. The code makes no network call or operational DB connection. It fails closed on changed quarantine or canonical baseline and never upgrades a provider catalogue claim to PASS. S15/S16, Hermes and production models were untouched. No PR was merged.
