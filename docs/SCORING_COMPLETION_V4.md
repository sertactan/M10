# Scoring Completion V4 — source replay checkpoint

Date: 2026-10-11 JST. Branch: `codex/scoring-completion-v4`, based on Task9 PR #177
commit `407d70271b911758af159a468542ee4590538570`. This branch changes only
research code, tests and staging. Frozen formulas, installed Personal Edition,
production databases and previous PRs remain untouched.

## Outcome

New complete Research model scores: **0**. Existing five-stock count: **10**;
INOD S7=100, S11=0 (a real zero), S12=91.528866. S14 remains N/A at 3/6.
Historical canonical acceptance remains zero securities and zero dates.

| Model | Previous | V4 result | Full score | Remaining gate |
|---|---:|---|---|---|
| S6 RSST | missing | 0.05914012806603271853128257494 verified aggregate research candidate | — | Individual WC/NCO/FIN partitions and frozen decomposition review |
| S6 Inventory | missing | No FY2023–25 numeric inventory/supplies or affirmative zero in checked exact 10-K evidence | — | Issuer-source amount or explicit valid model exception |
| S6 Dechow | 5/7 | 5 accepted + RSST aggregate candidate | N/A | Inventory, partition review, normalization |
| B_Q | 5/7 | 5/7 preserved; pure depreciation and interest-bearing debt still unresolved | N/A | DEPI, LVGI, serious flag review |
| S13 | 0/7 risk decisions | 27 contexts replayed; 2026 incorporated proxy related-party context added | N/A | Seven materiality decisions and independent serious flags |
| S11 | complete | Protected | 0.00 | None for current Research |
| S14 | 3/6 | Protected | N/A | B_Q, S6, S13 complete scores |

## RSST accounting and issuer evidence

The [Dechow et al. (2011) original Table 3](https://doi.org/10.1111/j.1911-3846.2010.01041.x)
uses Richardson et al.'s WC/NCO/FIN definitions, also described in
[this academic source's Appendix 1](https://www.bauer.uh.edu/vmuslu/docs/Muslu%20(2012).pdf).
For consistent classification of cash, short-term investments, long-term
investments, current debt, long-term debt and preferred stock:

```
WC  = CA - CASH - STI - CL + DLC
NCO = TA - CA - LTI - TL + CL + DLTT
FIN = STI + LTI - DLTT - DLC - PREF
WC + NCO + FIN = TA - CASH - TL - PREF
```

This identity identifies the **aggregate** without assigning unreported
investment or borrowing balances zero. It does **not** provide separate
WC/NCO/FIN amounts or satisfy the existing frozen `decomposition_review` gate.

Official INOD Companyfacts SEC CIK 903651 SHA-256:
`6ccc9dcc93b9c303cee51c166f345350fb16258408c884e2ed5d1231f2741b38`.
Original FY2024/FY2025 10-K body SHA-256:
`a2c0241be84173898a65f43480a16346704f6d61786e3ab4feff61886d973031`,
`2d5dd7f964d0239ea18a982f24e077d1b8e0f08baa73fd28dd66f539d9befba2`.
The exact-period facts and accession are stored per fact in the private receipt.
The FY2025 filing supplies the FY2024 comparative cash balance of USD46.897m;
the earlier FY2024 filing reports USD46.883m. We use the same FY2025 accession
for both FY2024 and FY2025 comparison amounts and preserve both original bodies.
Preferred shares outstanding were zero in each period, with the audited 10-K
balance sheets expressly stating none issued and outstanding; a nil preferred
value XBRL tag is never interpreted as zero.

| USD | FY2024 | FY2025 |
|---|---:|---:|
| Total assets | 113,449,000 | 168,593,000 |
| Cash and cash equivalents | 46,897,000 | 82,230,000 |
| Total liabilities | 50,060,000 | 61,531,000 |
| Aggregate WC+NCO+FIN balance | 16,492,000 | 24,832,000 |

Independent `equity - cash` equals each aggregate balance. Difference
USD8,340,000 / average assets USD141,021,000 = **0.0591401280660327185**.
`app/scoring_v4_dechow.py` uses separate Decimal arithmetic and original-source
replay; it emits `RSST_frozen_accepted=false`, `S6=null` and `S14=null`.
Its private sealed receipt is under `E:/M10/.scoring_v4_private/s6/` (SHA-256
`f65b70b1b998d2eea52054a70df7996bde8d8f96f62b8a4fd35661d1480a983e`).
FY2023 cash/assets/liabilities/zero preferred shares are exact accession
matched, supporting prior-year checks; the RSST delta uses FY2024–25 instants.

The Companyfacts `Supplies` tag has no FY2023–25 matching rows in the two
relevant annual accessions. `InventoryNet` and `Inventories` are absent. The
two annual inline XBRL sources have no inventory/supplies concept; the audited
balance sheet combines prepaid expenses and other current assets. Absence is
not a signed zero. The frozen S6 fallback only concerns score normalization,
not missing inventory. No S6 score is calculated.

## B_Q and S13

V4 Beneish replay extracts the original annual XBRL dimensional facts. The
total D&A minus separately presented acquired intangible and software
amortization leaves **approximate mixed PPE D&A** residuals USD1.496m (2024)
and USD2.189m (2025). PPE still includes software amortization, so these are
not pure depreciation. FY2024/25 unused Wells Fargo facility, pension and
Microsoft license obligations do not establish a comparable positive
interest-bearing debt denominator. No DEPI/LVGI imputation is made. A displayed
XBRL dash is explicitly treated as missing, not numeric zero. Private
`beneish_v4.json` SHA-256:
`b1708c3e0359204c3f76645107b92a60dcfee19320141129ab5e755df3750c7a`.

S13 replays the 27 prior source-context claims across all seven blocks and
checks all 14 cached SEC body hashes. The issuer-linked [2026 proxy](https://investor.innodata.com/financials/sec-filings/sec-filings-details/default.aspx?FilingId=19366041)
adds a scoped Item 404 no-reportable-transaction statement as of its date;
the issuer-hosted PDF SHA-256 is
`38924182ab3243560fc3381372f762f2c4e8039bb5a810974c55ad4bf317fb75`.
This does not prove an absence of all related-party activity. No rubric-backed
numeric materiality/serious-flag adjudication is claimed. Private review packet
SHA-256: `3773036c2912876fcd7e51c4c69588e072f696c94d10f8b9396bbd8c0f5cf86d`.

## Independent source clocks, validation and staging

The new source-clock resolver separately preserves SEC accepted-at and local
observation times. All 14 exact primary-document receipts pass for present
Research at the observed cutoff; **0 historical provider PIT** dates are
attested. Private current-Research receipt SHA-256:
`c41d6d89d32c4715c77d1822b1142d0d5a8d1dbb9adce157cab5f0aecd2bd85d`.
Historical-cutoff receipt SHA-256:
`41943be246fbfa7d8147bab27c83f4ee2c627e72502f50d595bb1d5a08835c3d`.
Both remain private.

Targeted local `unittest`: 35 tests PASS (new V4 plus affected Task9 and UI
regressions). V4 Beneish's original pytest file remains for GitHub CI; a
dependency-free Windows gate suite also passes. In-memory syntax compilation
passes. Windows Qt offscreen staging opens all five stocks and 14 columns,
replays the RSST receipt from original source bytes, shows it explicitly as
research under review while keeping frozen S6 coverage 5/7, S11=0.00,
S14=N/A and total ten scores. Staging receipt:
`E:/M10/.scoring_v4_private/windows_smoke3/receipt.json`.
The earlier failed smoke attempt is retained for audit; it exposed a JSON
string-key replay mismatch, corrected before the passing run.

Task-level status: 9 PARTIAL; 10 BLOCKED; 11 PARTIAL; 12 PARTIAL;
13 PARTIAL; 14 BLOCKED; 15 PENDING_APPROVAL; 16 PARTIAL;
17 PARTIAL; 18 STAGING PASS / production untouched. No new complete model.
