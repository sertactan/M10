"""INOD Task9: checked, contextual SEC disclosure research; NOT S13 auto scoring.

Each curated claim requires a real filing-specific text anchor and additional
nearby corroborating language; a bare keyword scan never creates a finding.
Source hashes, SEC URLs, timestamps and paragraph excerpts are preserved.
No automated inspection asserts human rubric review or zero serious flags.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Mapping

from app.forensic_evidence import BLOCK_WEIGHTS, RUBRIC
from app.scoring_v3_sec_filing_evidence import _extract_text

VERSION = "M10_TASK9_FORENSIC_CONTEXT_REVIEW_V1"
SOURCE_SHA = "53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794"
BLOCKS = tuple(BLOCK_WEIGHTS)
CIK = "0000903651"

# block, accession, section, exact anchor, contextual corroboration,
# evidence type, scoped factual finding, required inference boundary.
# No numeric levels encoded: S13 rubric has no automated materiality cutoffs.
SPECS = (
 ("AUD","0001104659-26-020655","10-K Item 8, auditor report","In our opinion, the consolidated financial statements present fairly",("December 31, 2025","conformity with accounting principles"),"MITIGATING","FY2025 auditor states that the financial statements present fairly in material respects.","An unmodified financial statement opinion does not independently certify internal controls."),
 ("AUD","0001104659-26-020655","10-K Item 8, audit scope","The Company is not required to have, nor were we engaged to perform, an audit of its internal control over financial reporting",("expressing an opinion",),"SCOPE_LIMIT","The auditor says it did not audit effectiveness of internal control over financial reporting.","Auditor non-engagement is not evidence of a material weakness."),
 ("AUD","0001104659-26-020655","10-K Item 8, critical audit matters","revenue recognition is a critical audit matter",("high degree of auditor effort","Testing the design and operating effectiveness"),"COMPLEXITY","Revenue recognition was identified as a FY2025 critical audit matter, with substantive auditor procedures.","CAM is not fraud, restatement, adverse opinion, or proven material weakness."),
 ("AUD","0001410578-25-000194","10-K Item 8, auditor report","In our opinion, the consolidated financial statements present fairly",("December 31, 2024","conformity with accounting principles"),"MITIGATING","FY2024 independent financial statement audit provided a fair-presentation opinion.","Not an audit opinion on internal controls."),
 ("RPT","0001104659-26-020655","10-K Item 13, related parties","Item 13. Certain Relationships and Related Transactions, and Director Independence",("incorporated by reference","proxy statement"),"EXTERNAL_REVIEW_NEEDED","FY2025 10-K incorporates Item 13 related-party matters by reference from a proxy statement.","The primary 10-K cannot establish global absence of related-party transactions."),
 ("RPT","0001410578-25-000194","10-K Item 13, related parties","Item 13. Certain Relationships and Related Transactions, and Director Independence",("incorporated by reference","proxy statement"),"EXTERNAL_REVIEW_NEEDED","FY2024 10-K also incorporates Item 13 related-party matters from a proxy statement.","Full company RPT review requires the incorporated proxy."),
 ("RPT","0001104659-26-092010","8-K Item 5.02, incoming CEO","related party transactions involving Mr. Singhal",("Item 404(a)","requiring disclosure"),"NARROW_MITIGATING","CEO appointment filing says no reportable Item 404(a) transactions involving this named officer.","Not a representation about ALL other officers, affiliates or subsidiaries."),
 ("RPT","0001104659-26-075184","8-K Item 5.02, incoming CFO","no direct or indirect material interest",("Item 404(a)","Mr. Chauhan"),"NARROW_MITIGATING","CFO appointment filing reports no Item 404(a)-reportable material transaction interest for this officer.","Does not rule out unrelated related-party dealings."),
 ("REC","0001410578-25-000194","10-K Item 1A, customer receivables concentration","61% or $16.6 million of our accounts receivable was due from two customers",("December 31, 2024","allowances"),"ADVERSE_EXPOSURE","FY2024 filing: two customers accounted for 61%, or $16.6 million, of receivables.","Concentration is NOT by itself DSO deterioration, fraud or customer default."),
 ("REC","0001104659-26-020655","10-K Item 1A, customer receivables concentration","63% or $29.2 million of our accounts receivable were due from one customer",("December 31, 2025","allowances"),"ADVERSE_EXPOSURE","FY2025 filing: one customer accounted for 63%, or $29.2 million, of receivables.","Cannot assume impairment of these receivables or a write-off."),
 ("REC","0001104659-26-092021","10-Q note, segment/customer concentrations","66% of the Company’s accounts receivable was due from two customers",("June 30, 2026","No other customer"),"ADVERSE_EXPOSURE","2026Q2 filing: two customers accounted for 66% of receivables.","Its FY2025 comparative says two customers at 63%, whereas FY2025 10-K says one; reconcile."),
 ("REC","0001104659-26-092021","10-Q note, credit loss accounting","Effective January 1, 2026, the Company adopted ASU 2025-05",("Credit Losses","Accounts Receivable"),"POLICY_CHANGE","2026Q2 filing reports adoption of ASU 2025-05 on receivable/contract-asset credit losses.","A policy update is not automatically proof of allowance deterioration."),
 ("DIL","0001104659-26-092133","8-K Item 1.01, equity distribution agreement","an aggregate offering price of up to $300,000,000",("Sales Agents","common stock"),"ADVERSE_CAPACITY","August 2026 8-K permits an equity offering up to $300 million.","Approved capacity does not prove actual share sales or dilution."),
 ("DIL","0001104659-26-092133","8-K Item 1.01, ATM selling discretion","no obligation to sell any of the Shares",("suspend offers","terminate"),"MITIGATING_CONDITION","Issuer may suspend or terminate the at-the-market selling program.","Not evidence that no subsequent sales occurred."),
 ("DIL","0001104659-26-092021","10-Q consolidated six-month cash flow","Stock-based compensation",("13,104","5,602"),"ADVERSE_EXPENSE","2026 first-half SBC cash flow adjustment was $13.104m versus $5.602m prior first half (thousands of dollars).","SBC expense is not a count of newly issued shares."),
 ("DIL","0001104659-26-092021","10-Q Note 11, compensation plans","the Company adopted the Amended and Restated Innodata Inc. Equity Compensation Plan",("June 4, 2026","stockholders"),"DISCLOSED_APPROVAL","Stockholders approved the 2026 equity compensation plan on June 4, 2026.","Plan approval alone does not determine future dilution."),
 ("REV","0001104659-26-020655","10-K auditor revenue CAM","revenue recognition is a critical audit matter",("high degree of auditor effort","customer contracts"),"COMPLEXITY","FY2025 auditor CAM notes high effort checking contracts and revenue evidence.","CAM does not establish aggressive recognition or fraud."),
 ("REV","0001104659-26-092021","10-Q consolidated balance sheet","Advances from customers",("66,962","1,812"),"CUSTOMER_ADVANCE_LIABILITY","2026Q2 customer advance liabilities $66.962m versus $1.812m at year-end 2025 (USD thousands).","Amounts are liabilities, not automatically earned revenue or channel stuffing."),
 ("REV","0001104659-26-020655","10-K Notes, deferred revenue policy","Deferred revenue represents payments received from customers in advance",("performance obligations","12 months"),"POLICY_DISCLOSURE","FY2025 policy defers advance payments until conditions and expects most obligations satisfied within 12 months.","Policy text alone is not contract-by-contract compliance evidence."),
 ("ACQ","0001104659-26-020655","10-K management discussion, goodwill","The Company concluded that there is no impairment of goodwill",("market multiples","revenue"),"MANAGEMENT_ASSERTION","FY2025 management assessment found no goodwill impairment using comparable revenue multiples.","Management assertion is not an independent appraisal or proof of zero acquisition risk."),
 ("ACQ","0001410578-25-000194","10-K management discussion, goodwill","The Company concluded that there is no impairment of goodwill",("market multiples","revenue"),"MANAGEMENT_ASSERTION","FY2024 management also reported no goodwill impairment.","Does not prove organic growth or eliminate intangible asset valuation risk."),
 ("ACQ","0001104659-26-092021","10-Q condensed consolidated balance sheet","Goodwill",("2,036","2,079"),"ACCOUNTING_BALANCE","2026Q2 goodwill listed $2.036m compared with $2.079m in December 2025 (USD thousands).","Balance does not establish acquisition quality, impairment, or organic growth."),
 ("GOV","0001410578-25-000194","10-K Item 1A / financial notes, investigations and pending dispute","received a subpoena from the SEC requesting certain information",("DOJ","Securities Class Action"),"REGULATORY_INFORMATION_REQUEST","FY2024 filing says it received SEC and DOJ information/document requests believed related to securities class-action allegations.","Subpoenas and document requests are real events but are not findings of wrongdoing; multiple requests may relate to a single issue."),
 ("GOV","0001104659-26-020655","10-K Item 1A/Item 8, securities litigation","The motion to dismiss is fully briefed and pending",("Securities Class Action","cannot predict"),"UNRESOLVED_ALLEGATION","FY2025 filing describes pending securities class-action litigation and dismissal motion.","Lawsuit allegation is not an adjudicated fraud finding."),
 ("GOV","0001104659-26-092010","8-K Item 5.02, CEO succession","transition of Jack S. Abuhoff from the role of Chief Executive Officer",("Executive Chairman","September 30, 2026"),"MANAGEMENT_TRANSITION","Board announced existing CEO move to Executive Chairman and Rahul Singhal CEO succession.","Personnel transition is not intrinsically a breakdown of governance."),
 ("GOV","0001104659-26-075184","8-K Item 5.02, CFO appointment","will continue to serve as the Company",("Interim Chief Financial Officer","Mr. Chauhan"),"FINANCE_TRANSITION","Filing describes new CFO and a continuing principal accounting officer in finance leadership.","A role transition is not automatically an internal-control deficiency."),
 ("GOV","0001104659-26-107790","8-K Item 5.02, board change","Michael S. Rogers to serve as an independent director",("September 10, 2026","Board of Directors"),"NARROW_MITIGATING","Company disclosed election of an independent director.","One director appointment does not certify entire board effectiveness."),
)

QUESTIONS = {
 "AUD":["Obtain full audit scope and confirm any genuinely established weakness, restatement or qualification.","CAM is a critical matter, not a negative audit opinion."],
 "RPT":["Read definitive FY2024/25 proxies incorporated by reference, and assess all affiliates.","Person-specific Item404 absence must not be generalized."],
 "REC":["Reconcile 2025 63% one-customer 10-K vs two-customer 2026Q2 comparative.","Independently examine receivable aging, DSO and credit-loss allowance."],
 "DIL":["Verify executed ATM shares and net proceeds, not the $300m ceiling.","Reconcile SBC, diluted shares, options/warrants, capital raises."],
 "REV":["Review actual performance obligations, milestone terms and cash realization.","Separate CAM from restatement/fraud; evaluate advance liability changes."],
 "ACQ":["Review actual transactions and goodwill allocation/impairment assumptions.","Separate management no-impairment assessment from independent evidence."],
 "GOV":["Verify lawsuits/information requests outcomes, not just allegations.","Read transition arrangements, independent director and control disclosures."],
}


def _utc(instant: str) -> datetime:
    parsed = datetime.fromisoformat(instant.replace("Z","+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("TIMESTAMP_MUST_INCLUDE_OFFSET")
    return parsed.astimezone(timezone.utc)


def _anchored(spec: tuple, meta: Mapping, text: str) -> dict | None:
    block, accession, section, anchor, needs, category, claim, boundary = spec
    results = []
    pattern = r"\s+".join(re.escape(word) for word in anchor.split())
    for match in re.finditer(pattern, text, flags=re.IGNORECASE):
        before, after = max(0, match.start()-300), min(len(text), match.end()+1550)
        context = text[before:after]
        flat_context = re.sub(r"\s+"," ",context).casefold()
        if all(re.sub(r"\s+"," ",part).casefold() in flat_context for part in needs):
            results.append((match.start(), re.sub(r"\s+"," ",context).strip()))
    if not results:
        return None
    offset, context = results[0]
    return {
        "finding_id":f"{block}:{accession}:{sha256(anchor.encode()).hexdigest()[:12]}",
        "block":block,"kind":category,"observed_claim":claim,
        "inference_boundary":boundary,"section_reference":section,
        "section_boundary_status":"REVIEWER_LABEL; NOT AUTOMATICALLY CERTIFIED",
        "anchor":anchor,"required_nearby_context":list(needs),
        "corroborated_occurrences_in_source":len(results),
        "selection_policy":"FIRST_CORROBORATED_PASSAGE_RESEARCH_ONLY_NO_SCORE",
        "extracted_text_offset":offset,"context_excerpt":context[:2200],
        "context_sha256":sha256(context.encode()).hexdigest(),
        "accession":accession,"form":meta["form"],
        "filing_date":meta["filing_date"],"period_end":meta["period_end"],
        "sec_report_date":meta.get("sec_report_date"),
        "accepted_at":meta["accepted_at"],"retrieved_at":meta["retrieved_at"],
        "source_ref":meta["source_ref"],"filing_body_sha256":meta["source_content_sha256"],
        "extracted_text_sha256":meta["extracted_text_sha256"],
        "numeric_risk":None,"independent_serious_flag":None,"historical_pit_accepted":False,
    }


def review_contexts(sources: Mapping[str, tuple[Mapping, bytes]], *,
                    as_of: str, specs: tuple = SPECS) -> dict:
    """Review verified bytes, reject stale/cross-issuer metadata; no automatic score."""
    at = _utc(as_of)
    if not sources:
        raise ValueError("NO_VERIFIED_FILING_BODIES")
    parsed = {}
    for accession, (meta, raw) in sources.items():
        if (meta.get("accession") != accession
                or meta.get("source_content_sha256") != sha256(raw).hexdigest()
                or f"/Archives/edgar/data/903651/{accession.replace('-', '')}/" not in meta.get("source_ref","")
                or meta.get("form") not in ("10-K","10-Q","8-K","8-K/A")):
            raise ValueError("FILING_BODY_HASH_OR_ISSUER_MISMATCH")
        if _utc(meta["accepted_at"]) > _utc(meta["retrieved_at"]) or _utc(meta["retrieved_at"]) > at:
            raise ValueError("SOURCE_CLOCK_UNACCEPTABLE")
        text = _extract_text(raw)
        if sha256(text.encode()).hexdigest() != meta["extracted_text_sha256"]:
            raise ValueError("EXTRACTED_TEXT_SHA_CHANGED")
        parsed[accession] = (meta,text)
    findings = defaultdict(list)
    unresolved = []
    for spec in specs:
        block, accession = spec[:2]
        result = _anchored(spec,*parsed[accession]) if block in BLOCKS and accession in parsed else None
        if result is None:
            unresolved.append({"block":block,"accession":accession,"anchor":spec[3],
                               "reason":"NOT_UNIQUELY_CORROBORATED_IN_THE_REAL_FILING"})
        else:
            findings[block].append(result)
    blocks = {}
    for block in BLOCKS:
        vals = findings[block]
        blocks[block] = {
            "status":"SOURCE_CONTEXTS_VERIFIED_REVIEW_REQUIRED" if vals else "CONTEXT_NOT_VERIFIED",
            "source_verified_findings":len(vals),"findings":vals,
            "risk":None,"human_review_completed":False,
            "coverage_complete":False,"outstanding_review_questions":QUESTIONS[block],
        }
    return {
        "version":VERSION,"issuer":{"ticker":"INOD","cik":CIK},"as_of":at.isoformat(),
        "scope":"SOURCE_VERIFIED_CURRENT_RESEARCH_NOT_HISTORICAL_PIT",
        "source_contract":{"sha256":SOURCE_SHA,"lines":[1707,1833],
                           "weights":dict(BLOCK_WEIGHTS),"risk_rubric":list(RUBRIC)},
        "filing_bodies_verified":len(parsed),"accessions":sorted(parsed),
        "blocks":blocks,"unresolved_anchors":unresolved,
        "serious_flag_candidates":[
            {"issue":"FY2024/FY2025 securities litigation and SEC/DOJ document requests",
             "source_accessions":["0001410578-25-000194","0001104659-26-020655"],
             "status":"UNRESOLVED_ALLEGATION_NOT_ADJUDICATED","confirmed_flag":None,
             "independence_key":None,"caveat":"Multiple mentions may describe same underlying dispute."},
            {"issue":"FY2025 revenue-recognition auditor CAM",
             "source_accessions":["0001104659-26-020655"],
             "status":"CAM_NOT_ESTABLISHED_MISCONDUCT","confirmed_flag":False,
             "independence_key":None},
            {"issue":"Up to $300m ATM selling arrangement",
             "source_accessions":["0001104659-26-092133"],
             "status":"AUTHORIZED_CAPACITY_NOT_PROVEN_ISSUANCE","confirmed_flag":None,
             "independence_key":None},
        ],
        "independent_serious_flags":None,"serious_flag_count":None,
        "independence_review_complete":False,
        "human_review_packet":{
            "block_reviews_required":list(BLOCKS),
            "reviewer":None,"reviewed_at":None,"signed_risk_decisions":None,
            "serious_flags_independently_reviewed":False,
            "external_material_needed":[
                "FY2024/2025 incorporated definitive proxy Item 13 disclosures",
                "Cross-filing referenced exhibits, contractual terms and any SEC/DOJ outcomes",
                "Detailed receivable aging, actual ATM transactions and independence evidence"],
        },
        "status":"REVIEW_REQUIRED","S13":None,"S14":None,
        "canonical_accepted":False,"historical_pit_accepted":False,
    }
