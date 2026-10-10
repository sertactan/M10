"""Task9 V4: real dated SEC SIC 7374 FY2025 Jones cohort, cache-first.

Inputs are official SEC SIC listing, SEC companyfacts bulk ZIP (20,440 JSON
members) and official SEC 10-K submission headers. Only three files in the
isolated worktree contain this implementation. Original S11 formulas are
provided by app.recovered_jones without modification.

NETWORK: official sec.gov/data.sec.gov only; configured legitimate SEC contact,
<= 2.0 req/s, no retries; HTTP 403/429 stops the full run. Every accepted
response is stored exclusively in a new PRIVATE task9_jones runtime folder.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal, localcontext
from hashlib import sha256
from html import unescape
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
import zipfile

from app.recovered_jones import MIN_OTHER_PEERS, compute_s11
from app.scoring_v3_jones_peers import (
    _historical_sic, _submission_accession, extract_company_year,
    read_universe,
)

SIC = "7374"
TARGET_CIK = "0000903651"
FY = 2025
FY_WINDOW = 45
REQ_GAP_SECONDS = .52
SOURCE_ROOT = "https://www.sec.gov"
COMPANYFACTS = "https://data.sec.gov"
TAG_MAP = {
    "NI": "NetIncomeLoss",
    "CFO": "NetCashProvidedByUsedInOperatingActivities",
    "REV": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "REC": "AccountsReceivableNetCurrent",
    "PPE": "PropertyPlantAndEquipmentNet",
    "ASSETS": "Assets",
}
_TAG_HEADER = re.compile(rb"</SEC-HEADER>", re.I)
_CIK_ROW = re.compile(
    r'<a\s+href="[^"]*CIK=(\d+)[^"]*"[^>]*>\s*\d+\s*</a>\s*</td>\s*'
    r'<td[^>]*>(.*?)</td>', re.I | re.S,
)


def now_utc():
    return datetime.now(timezone.utc)


def digest(raw):
    return sha256(raw).hexdigest()


def _iso(value):
    if not isinstance(value, str):
        return None
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return timestamp.astimezone(timezone.utc) if timestamp.tzinfo else None
    except ValueError:
        return None


def read_sec_contact(config_path: Path) -> str | None:
    """Read user-configured SEC contact without logging or copying it."""
    if not config_path.is_file() or config_path.is_symlink():
        return None
    for line in config_path.read_text(encoding="utf-8-sig").splitlines():
        if line.lstrip().startswith(("#", ";")) or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "SEC_USER_AGENT":
            agent = value.strip().strip('"').strip("'")
            if "@" in agent and not any(
                part in agent.lower() for part in ("example", "localhost", "your@email")
            ):
                return agent
    return None


class SECStop(Exception):
    pass


class SECCache:
    """Private immutable responses and request receipts, atomic no-overwrite."""

    def __init__(self, cache_root: Path, *, contact: str | None,
                 request_budget: int = 80, min_gap: float = REQ_GAP_SECONDS,
                 transport=None, clock=now_utc, sleeper=time.sleep):
        self.root = Path(cache_root).resolve()
        if not self.root.name.startswith("task9_jones"):
            raise ValueError("Only new PRIVATE task9_jones cache directories allowed")
        self.root.mkdir(parents=True, exist_ok=True)
        self.contact = contact
        self.request_budget = request_budget
        self.min_gap = min_gap
        self.transport = transport or urlopen
        self.clock = clock
        self.sleeper = sleeper
        self.next_at = 0.0
        self.requests = 0
        self.cached = 0
        self.blocked = False
        self.http_statuses = Counter()
        self.receipts = []

    def load(self, url: str, *, limit: int = 1_500_000, partial=False):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc.lower() not in {
            "www.sec.gov", "sec.gov", "data.sec.gov"
        }:
            raise ValueError("Only official HTTPS SEC URLs are supported")
        key = digest(url.encode("utf8"))
        base = self.root / "responses"
        raw_file, meta_file = base / (key + ".bin"), base / (key + ".json")
        if raw_file.is_file() and meta_file.is_file():
            meta = json.loads(meta_file.read_text(encoding="utf8"))
            raw = raw_file.read_bytes()
            if meta.get("url") != url or meta.get("sha256") != digest(raw):
                raise ValueError("Cached SEC source hash mismatch")
            self.cached += 1
            self.receipts.append(meta)
            return raw, meta
        if self.blocked:
            raise SECStop("SEC_ACCESS_STOPPED_PREVIOUS_403_429")
        if not self.contact:
            raise SECStop("SEC_CONTACT_NOT_CONFIGURED")
        if self.requests >= self.request_budget:
            raise SECStop("SEC_REQUEST_BUDGET_REACHED")
        gap = self.next_at - time.monotonic()
        if gap > 0:
            self.sleeper(gap)
        self.next_at = time.monotonic() + self.min_gap
        self.requests += 1
        headers = {"User-Agent": self.contact, "Accept": "text/plain, text/html, application/json",
                   "Accept-Encoding": "identity"}
        if partial:
            headers["Range"] = f"bytes=0-{limit - 1}"
        try:
            with self.transport(Request(url, headers=headers), timeout=20) as response:
                status = response.status
                # Some SEC archive endpoints return HTTP 200 while ignoring
                # the Range header. In header-only mode the first `limit`
                # bytes still suffice when </SEC-HEADER> is present.
                raw = response.read(limit if partial else limit + 1)
        except HTTPError as err:
            self.http_statuses[str(err.code)] += 1
            if err.code in (403, 429):
                self.blocked = True
                raise SECStop("SEC_HTTP_" + str(err.code) + "_NO_RETRY")
            return None, {"url": url, "http_status": err.code,
                          "error": "HTTP_NON_200", "cache_hit": False}
        except (OSError, URLError) as err:
            return None, {"url": url, "error": type(err).__name__, "cache_hit": False}
        self.http_statuses[str(status)] += 1
        if status in (403, 429):
            self.blocked = True
            raise SECStop("SEC_HTTP_" + str(status) + "_NO_RETRY")
        if status not in (200, 206) or len(raw) > limit:
            return None, {"url": url, "http_status": status,
                          "error": "OVERSIZE_OR_NON_200", "cache_hit": False}
        if partial and b"</SEC-HEADER>" not in raw.upper():
            return None, {"url": url, "http_status": status,
                          "error": "SEC_HEADER_NOT_COMPLETE_IN_RANGE", "cache_hit": False}
        meta = {
            "url": url, "http_status": status, "bytes": len(raw),
            "sha256": digest(raw), "observed_at": self.clock().isoformat(),
            "partial_response": bool(partial), "cache_hit": False,
        }
        base.mkdir(exist_ok=True)
        with raw_file.open("xb") as f:
            f.write(raw)
        with meta_file.open("x", encoding="utf8") as f:
            json.dump(meta, f, sort_keys=True)
        self.receipts.append(meta)
        return raw, meta


def sic_listing(sec: SECCache, *, pages=6, count=100):
    """Official SEC SIC directory; de-duplicate CIKs while retaining page hashes."""
    entries, seen, sources = [], set(), []
    for page in range(pages):
        url = SOURCE_ROOT + "/cgi-bin/browse-edgar?" + urlencode({
            "company": "", "SIC": SIC, "owner": "exclude",
            "action": "getcompany", "count": count, "start": page * count,
        })
        raw, receipt = sec.load(url, limit=1_200_000)
        sources.append(receipt)
        if raw is None:
            break
        matches = _CIK_ROW.findall(raw.decode("utf8", errors="replace"))
        if not matches:
            break
        for cik, name in matches:
            cik = cik.zfill(10)
            if cik in seen:
                continue
            seen.add(cik)
            entries.append({"cik": cik, "name": unescape(re.sub(
                r"<[^>]+>", "", name)).strip(), "listed_sec_sic": SIC,
                "directory_source_sha256": receipt["sha256"]})
        if len(matches) < count:
            break
    return entries, sources


def _find_fy2025_facts(raw: bytes):
    """Fast ZIP screening with exact 10-K accession, FY current/prior windows.

    This is candidate ranking only. Final eligibility is checked by the
    unchanged app.scoring_v3_jones_peers.extract_company_year.
    """
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None, "INVALID_COMPANYFACTS_JSON"
    gaap = (data.get("facts") or {}).get("us-gaap") or {}
    revenue = (((gaap.get(TAG_MAP["REV"]) or {}).get("units") or {}).get("USD") or [])
    possible = []
    for row in revenue:
        if row.get("form") != "10-K" or row.get("accn") is None or row.get("start") is None:
            continue
        try:
            end = date.fromisoformat(row["end"])
            start = date.fromisoformat(row["start"])
        except (ValueError, TypeError, KeyError):
            continue
        if (end.year == FY and abs((end-date(FY, 12, 31)).days) <= FY_WINDOW
                and 330 <= (end-start).days+1 <= 400):
            possible.append((row["accn"], end.isoformat(), start.isoformat()))
    if not possible:
        return None, "FY2025_ANNUAL_REVENUE_10K_MISSING"
    candidates = []
    for accession, end, start in sorted(set(possible)):
        prev_end = (date.fromisoformat(start) - date.resolution).isoformat()
        needed = (("NI",end,start),("CFO",end,start),("REV",end,start),
                  ("REV",prev_end,"FULL_YEAR"),("REC",end,None),
                  ("REC",prev_end,None),("PPE",end,None),("ASSETS",prev_end,None))
        present, found_tags = 0, []
        for alias, period_end, period_start in needed:
            concept = gaap.get(TAG_MAP[alias]) or {}
            records = (concept.get("units") or {}).get("USD") or []
            ok = False
            for x in records:
                if (x.get("accn") != accession or x.get("form") != "10-K"
                        or x.get("end") != period_end or x.get("filed") is None):
                    continue
                if period_start == "FULL_YEAR":
                    try:
                        span = (date.fromisoformat(x["end"])-date.fromisoformat(x["start"])).days+1
                        ok = 330 <= span <= 400
                    except (ValueError, TypeError, KeyError):
                        pass
                else:
                    ok = x.get("start") == period_start
                if ok:
                    break
            if ok:
                present += 1
                found_tags.append(alias + "_" + period_end)
        candidates.append({"accession": accession, "period_end": end,
                           "period_start": start, "exact_field_count": present,
                           "found": found_tags})
    if not candidates:
        return None, "FY2025_ANNUAL_FACTS_MISSING"
    best = max(candidates, key=lambda c: (c["exact_field_count"],c["period_end"]))
    return best, None


def private_cached_submissions(sec: SECCache, runtime: Path, cik: str):
    official = runtime / "sec_submissions" / f"CIK{cik}.json"
    if official.is_file() and not official.is_symlink():
        raw = official.read_bytes()
        return raw, {"source": "EXISTING_SEC_SUBMISSIONS_CACHE", "sha256": digest(raw),
                     "bytes": len(raw), "observed_at": sec.clock().isoformat(),
                     "observed_at_is_original_capture": False}
    return sec.load(f"{COMPANYFACTS}/submissions/CIK{cik}.json", limit=2_500_000)


def _amendment_same_eight(companyfacts_raw, original_acc, amendment_acc, annual_end):
    """Compare eight exact Jones monetary facts if amendment carries XBRL.

    A no-XBRL Part III amendment instead requires explicit text limiting
    scope. This function never defaults a missing annual financial concept to
    zero; it checks whether an amendment republishes/changes any eight facts.
    """
    try:
        payload=json.loads(companyfacts_raw)
    except (ValueError,TypeError):
        return False,"INVALID_COMPANYFACTS"
    gaap=(payload.get("facts") or {}).get("us-gaap") or {}
    prior=f"{int(annual_end[:4])-1}{annual_end[4:]}"
    columns=((TAG_MAP["NI"],annual_end), (TAG_MAP["CFO"],annual_end),
             (TAG_MAP["REV"],annual_end), (TAG_MAP["REV"],prior),
             (TAG_MAP["REC"],annual_end), (TAG_MAP["REC"],prior),
             (TAG_MAP["PPE"],annual_end), (TAG_MAP["ASSETS"],prior))
    compared=0
    for tag,end in columns:
        rows=(gaap.get(tag) or {}).get("units",{}).get("USD",[])
        originals={json.dumps({"val":r.get("val"),"start":r.get("start")},sort_keys=True)
                   for r in rows if r.get("accn")==original_acc and r.get("end")==end}
        amend={json.dumps({"val":r.get("val"),"start":r.get("start")},sort_keys=True)
               for r in rows if r.get("accn")==amendment_acc and r.get("end")==end}
        if amend:
            if not originals or amend!=originals:
                return False,"AMENDMENT_MODIFIED_OR_AMBIGUOUS_JONES_FINANCIALS"
            compared+=1
    all_tags=set()
    for tag,concept in gaap.items():
        for row in (concept.get("units") or {}).get("USD",[]):
            if row.get("accn")==amendment_acc:
                all_tags.add(tag)
    return True,("MATCHING_PUBLISHED_JONES_TAGS_"+str(compared)
                 if all_tags else "AMENDMENT_NO_US_GAAP_USD_TAGS")


def _review_amendments(sec: SECCache, original_json: bytes, companyfacts_raw: bytes,
                       cik: str, at: datetime):
    """Filter only reviewed, financially unchanged FY2025 Part III amendments.

    Original response SHA and every amended official filing header SHA remain
    in the output; the filtered response is an explicit analytic selection of
    original 10-K entries, never a claim of unmodified SEC Submissions bytes.
    """
    submission=json.loads(original_json)
    recent=(submission.get("filings") or {}).get("recent") or {}
    forms=recent.get("form",[])
    report_dates=recent.get("reportDate",[])
    accessions=recent.get("accessionNumber",[])
    matching=[i for i,f in enumerate(forms) if f=="10-K/A"
              and i<len(report_dates) and report_dates[i]=="2025-12-31"]
    if not matching:
        return original_json,[]
    original=[i for i,f in enumerate(forms) if f=="10-K" and
              i<len(report_dates) and report_dates[i]=="2025-12-31"]
    if len(original)!=1:
        return None,[{"status":"ORIGINAL_FY2025_10K_NOT_UNIQUE"}]
    findings=[]
    for i in matching:
        amended_acc=accessions[i]
        accession={"accession":amended_acc,
                   "accepted_at":recent["acceptanceDateTime"][i],
                   "report_date":recent["reportDate"][i]}
        url=f"{SOURCE_ROOT}/Archives/edgar/data/{int(cik)}/{amended_acc.replace('-','')}/{amended_acc}.txt"
        raw,receipt=sec.load(url,limit=250_000,partial=True)
        if raw is None:
            return None,[*findings,{"status":"AMENDMENT_HEADER_UNAVAILABLE","url":url}]
        head=raw[:250000].decode("latin-1",errors="replace")
        first=head.split("</SEC-HEADER>",1)[0]
        if (amended_acc not in first or "CONFORMED SUBMISSION TYPE:" not in first
                or not re.search(r"CONFORMED SUBMISSION TYPE:\s*10-K/A\b",first)
                or not re.search(r"CENTRAL INDEX KEY:\s*0*"+str(int(cik))+r"\b",first)
                or "CONFORMED PERIOD OF REPORT:" not in first
                or "20251231" not in first):
            return None,[*findings,{"status":"AMENDMENT_SEC_HEADER_CONFLICT",
                                    "sha256":receipt.get("sha256")}]
        financial_ok, financial_reason=_amendment_same_eight(
            companyfacts_raw,accessions[original[0]],amended_acc,"2025-12-31")
        body=head.split("</SEC-HEADER>",1)[-1].lower()
        body=re.sub(r"<[^>]+>"," ",body)
        body=re.sub(r"(?:&#160;|&nbsp;|\s)+"," ",body)
        # Text explicitly narrows amendment to Part III or isolated corrections
        # outside model financials, plus observed XBRL equalities if any.
        explanatory=body[:45000]
        no_changes=("no other changes have been made" in explanatory
                    or "no other changes are being made" in explanatory)
        part_iii=("part iii" in explanatory and
                  any(s in explanatory for s in (
                      "solely to include","amends the cover page, items 10 through 14",
                      "item 10 (directors","amend and restate in their entirety part iii",
                      "general instruction g(3)")))
        allowed=financial_ok and (no_changes or part_iii)
        item={"accession":amended_acc, "header_url":url,
              "header_sha256":receipt["sha256"],"accepted_at":accession["accepted_at"],
              "financial_comparison":financial_reason,
              "explicit_scope_part_iii":part_iii,
              "explicit_no_other_changes":no_changes,
              "status":"FINANCIALLY_UNCHANGED_AMENDMENT_REVIEWED"
                       if allowed else "AMENDMENT_SCOPE_OR_FINANCIAL_CHANGE_UNRESOLVED"}
        findings.append(item)
        if not allowed:
            return None,findings
    selected={**submission,"filings":{**submission["filings"],
              "recent":{k:[v[i] for i in range(len(forms)) if i not in matching]
                        if isinstance(v,list) and len(v)==len(forms) else v
                        for k,v in recent.items()}}}
    return json.dumps(selected,sort_keys=True).encode("utf8"),findings


def historical_header(sec: SECCache, cik: str, accession: dict, *, end: str):
    url = (f"{SOURCE_ROOT}/Archives/edgar/data/{int(cik)}/"
           f"{accession['accession'].replace('-', '')}/{accession['accession']}.txt")
    raw, receipt = sec.load(url, limit=250_000, partial=True)
    if raw is None:
        return None, receipt, None
    header = {"header_bytes": raw, "header_sha256": digest(raw),
              "source_ref": url, "observed_at": receipt["observed_at"]}
    industry, provenance = _historical_sic(
        header, cik=cik, accession=accession, fiscal_end=end,
        as_of=sec.clock(), observed=sec.clock(),
    )
    return header if industry else None, receipt, provenance


def independent_decimal_reference(target, peers, coefficients, result):
    """Independently fit 3×3 OLS normal equations in high-precision Decimal.

    The original engine uses reorthogonalized QR. This reference uses separate
    Gaussian elimination, then recomputes target NDA/DA/score from raw facts.
    """
    facts = {(r["metric"],r["period_end"]):Decimal(str(r["value"])) for r in target["facts"]}
    with localcontext() as c:
        c.prec=60
        X=[]
        Y=[]
        for observation in peers:
            p={(r["metric"],r["period_end"]):Decimal(str(r["value"]))
               for r in observation["facts"]}
            p_end=observation["period_end"]
            p_prev=(date.fromisoformat(observation["period_start"])-date.resolution).isoformat()
            assets=p[("TOTAL_ASSETS",p_prev)]
            predictors=[
                Decimal(1)/assets,
                (p[("REVENUE",p_end)]-p[("REVENUE",p_prev)])/assets,
                p[("PPE_NET",p_end)]/assets,
            ]
            X.append(predictors)
            Y.append((p[("NET_INCOME",p_end)]-
                      p[("OPERATING_CASH_FLOW",p_end)])/assets)
        system=[]
        for j in range(3):
            system.append([
                sum(row[j]*row[k] for row in X) for k in range(3)
            ]+[sum(row[j]*y for row,y in zip(X,Y))])
        for j in range(3):
            pivot=max(range(j,3),key=lambda i:abs(system[i][j]))
            if system[pivot][j]==0:
                return {"method":"DECIMAL_OLS_INDEPENDENT_NORMAL_EQUATION",
                        "within_1e_8":False,"blocker":"DECIMAL_REFERENCE_SINGULAR"}
            system[j],system[pivot]=system[pivot],system[j]
            scale=system[j][j]
            for k in range(j,4):
                system[j][k]/=scale
            for i in range(3):
                if i==j:
                    continue
                scale=system[i][j]
                for k in range(j,4):
                    system[i][k]-=scale*system[j][k]
        independently_fitted=[system[i][3] for i in range(3)]
        end=target["period_end"]
        prev=(date.fromisoformat(target["period_start"])-date.resolution).isoformat()
        a=facts[("TOTAL_ASSETS",prev)]
        d_rev=facts[("REVENUE",end)]-facts[("REVENUE",prev)]
        d_rec=facts[("ACCOUNTS_RECEIVABLE_NET",end)]-facts[("ACCOUNTS_RECEIVABLE_NET",prev)]
        ta=(facts[("NET_INCOME",end)]-facts[("OPERATING_CASH_FLOW",end)])/a
        nda=(independently_fitted[0]/a+
             independently_fitted[1]*(d_rev-d_rec)/a+
             independently_fitted[2]*facts[("PPE_NET",end)]/a)
        da=ta-nda
        score=Decimal(100)*max(Decimal(0),Decimal(1)-abs(da)/Decimal(".20"))
    actual = Decimal(str(result["score"]))
    original=[Decimal(str(coefficients[k])) for k in ("alpha1","alpha2","alpha3")]
    coefficient_rel_error=max(
        abs(a-b)/max(Decimal(1),abs(b))
        for a,b in zip(original,independently_fitted)
    )
    da_error=abs(da-Decimal(str(result["components"]["discretionary_accrual"])))
    return {"method": "DECIMAL_INDEPENDENT_3X3_NORMAL_EQUATIONS",
            "OLS_alpha_decimal":[str(v) for v in independently_fitted],
            "max_relative_ols_coefficient_error":str(coefficient_rel_error),
            "NDA_decimal": str(nda), "DA_decimal": str(da),
            "score_decimal": str(score), "max_abs_score_diff": str(abs(score-actual)),
            "max_abs_DA_diff":str(da_error),
            "within_1e_8": (abs(score-actual)<=Decimal("0.00000001")
                            and da_error<=Decimal("0.00000001")
                            and coefficient_rel_error<=Decimal("0.00000001"))}


def scan_task9(
    sec: SECCache, *, runtime: Path, max_pages=6, max_candidates=100,
    as_of=None,
):
    """Run cache-first official SIC list + ZIP screen + headers and Jones."""
    at = as_of or sec.clock()
    if at.tzinfo is None:
        raise ValueError("Offset-aware research timestamp required")
    archive = runtime / "bulk/sec/companyfacts.zip"
    universe, universe_info = read_universe(runtime/"data/runtime/operational.db")
    by_cik = {}
    for row in universe:
        if row["cik"] and row["cik"] not in by_cik:
            by_cik[row["cik"]]=row
    target_identity = by_cik.get(TARGET_CIK)
    if not target_identity or target_identity["ticker"] != "INOD":
        raise ValueError("INOD CIK identity missing from local universe")
    events=[]
    ranked=[]
    candidates=[]
    peer_rows=[]
    target_row=None
    target_receipt=None
    stop_reason=None
    with zipfile.ZipFile(archive) as z:
        zentries=set(z.namelist())
        def pull(cik):
            name=f"CIK{cik}.json"
            if name not in zentries:
                return None, None
            info=z.getinfo(name)
            if info.file_size>50_000_000:
                return None,None
            raw=z.read(info)
            return raw, digest(raw)
        target_raw,target_sha=pull(TARGET_CIK)
        if not target_raw:
            raise ValueError("INOD official Companyfacts absent from cached ZIP")
        directory, directory_receipts=sic_listing(sec,pages=max_pages)
        # SEC browse directory contains current SIC membership; treat as
        # DISCOVERY only, not as proof it held at FY2025.
        for pos,item in enumerate(directory):
            cik=item["cik"]
            if cik == TARGET_CIK:
                continue
            record={"cik":cik,"name":item["name"],"listing_position":pos,
                    "directory_source_sha256":item["directory_source_sha256"],
                    "stage":"SIC_DIRECTORY_DISCOVERED"}
            raw,sha=pull(cik)
            if not raw:
                record["status"]="COMPANYFACTS_ZIP_CIK_NOT_PRESENT"
                ranked.append(record);continue
            fields,error=_find_fy2025_facts(raw)
            record.update(companyfacts_sha256=sha,
                          ticker=by_cik[cik]["ticker"] if cik in by_cik else "CIK"+cik,
                          issuer_identity_source=("LOCAL_UNIVERSE" if cik in by_cik
                                                  else "OFFICIAL_SEC_SIC_DIRECTORY"))
            if error:
                record["status"]=error
            else:
                record.update(fields)
                record["status"]=("PRECHECK_EXACT_8_OF_8" if fields["exact_field_count"]==8
                                  else "PRECHECK_INCOMPLETE_FINANCIAL_FACTS")
            ranked.append(record)
        ranked.sort(key=lambda r: (
            -r.get("exact_field_count",0), r.get("status")!="PRECHECK_EXACT_8_OF_8",
            r["listing_position"],
        ))
        def evidence_for(cik, identity, raw, claimed_sha, *, expected_sic=SIC):
            nonlocal stop_reason
            subraw, subreceipt=private_cached_submissions(sec,runtime,cik)
            if not subraw:
                return None, {"status":"MISSING_SEC_SUBMISSIONS",
                              "source":subreceipt}
            try:
                sub=json.loads(subraw)
                acceptance, err=_submission_accession(sub,FY,at=at)
            except (ValueError,KeyError,TypeError):
                return None,{"status":"INVALID_SEC_SUBMISSIONS"}
            amendments=[]
            if err=="FY2025_10K_AMENDMENT_REQUIRES_REVIEW":
                original_submissions_hash=digest(subraw)
                reviewed,amendments=_review_amendments(
                    sec,subraw,raw,cik,sec.clock())
                if reviewed is None:
                    return None,{"status":"AMENDED_10K_REVIEW_BLOCKED",
                                 "amendments":amendments,
                                 "original_submissions_sha256":digest(subraw)}
                sub=json.loads(reviewed)
                acceptance,err=_submission_accession(sub,FY,at=sec.clock())
                if not err:
                    filtered_submissions_sha256=digest(reviewed)
                    subraw=reviewed
            if err:
                return None,{"status":err,"submissions_sha256":digest(subraw)}
            header, headerreceipt, proven=historical_header(
                sec,cik,acceptance,end=acceptance["report_date"])
            if header is None:
                return None,{"status":"DATED_SEC_10K_SIC_HEADER_MISSING_OR_MISMATCH",
                             "header_receipt":headerreceipt}
            # Header is source-captured and matched to SEC accession/fiscal date.
            if not proven:
                return None,{"status":"NO_SIC_IN_OFFICIAL_FY2025_10K_HEADER"}
            observation_clock=sec.clock()
            packet,receipt=extract_company_year(
                raw,subraw,security_id=identity["security_id"],
                ticker=identity["ticker"],cik=cik,as_of=observation_clock,
                submissions_observed_at=_iso(subreceipt["observed_at"]) or at,
                companyfacts_observed_at=observation_clock,
                dated_industry=header,
            )
            actual_sic=(packet or {}).get("industry",{}).get("code") if packet else None
            details={
                "status":"VALID_8_FINANCIALS_AND_HISTORICAL_HEADER" if packet and not receipt["missing"]
                         else "EXTRACT_REJECTED",
                "historical_sic":actual_sic,
                "submissions_sha256":digest(subraw),
                "companyfacts_sha256":claimed_sha,
                "header_sha256":headerreceipt.get("sha256"),
                "header_url":headerreceipt.get("url"),
                "accepted_at":acceptance["accepted_at"],
                "form_accession":acceptance["accession"],
                "source_selected_count":len(receipt["selected"]),
                "missing":receipt["missing"],
            }
            if amendments:
                details["amendment_10K_review"]=amendments
                details["source_submissions_filtered_for_original_10K"]=True
                details["original_submissions_sha256"]=original_submissions_hash
                details["analytical_selection_sha256"]=filtered_submissions_sha256
            if expected_sic and actual_sic!=expected_sic:
                details["status"]="HISTORICAL_SIC_NOT_7374"
                return None,details
            return packet if not receipt["missing"] else None,details
        try:
            target_row,target_receipt=evidence_for(
                TARGET_CIK,target_identity,target_raw,target_sha)
        except SECStop as err:
            stop_reason=str(err)
        if target_row is not None and not stop_reason:
            valid_target=target_row
            pool=[x for x in ranked if x["status"]=="PRECHECK_EXACT_8_OF_8"]
            for idx,item in enumerate(pool[:max_candidates]):
                try:
                    raw,sha=pull(item["cik"])
                    identity=by_cik.get(item["cik"]) or {
                        "security_id":"SEC_CIK_"+item["cik"],
                        "ticker":"CIK"+item["cik"],"cik":item["cik"],
                    }
                    candidate,diag=evidence_for(
                        item["cik"],identity,raw,sha)
                except SECStop as err:
                    stop_reason=str(err)
                    break
                item.update(evaluation=diag)
                item["status"]=diag["status"]
                if candidate:
                    peer_rows.append(candidate)
                if len(peer_rows)>=MIN_OTHER_PEERS:
                    break
        else:
            valid_target=None
    completed_at=sec.clock()
    result=compute_s11(valid_target, peer_rows, completed_at)
    independent=None
    if result["score"] is not None:
        independent=independent_decimal_reference(
            valid_target,peer_rows,result["components"]["OLS_coefficients"],result)
    final={
        "schema":"TASK9_JONES_FY2025_SEC_SIC7374_V4",
        "as_of":completed_at.isoformat(),"ticker":"INOD","target_cik":TARGET_CIK,
        "target_financial_companyfacts_sha256":target_sha,
        "target":target_receipt,"source":"SEC_EDGAR",
        "universe":universe_info,
        "sec_bulk_file_count":len(zentries),
        "sic_directory_candidates":len(directory),
        "sic_directory_source_hashes":[x.get("sha256") for x in directory_receipts
                                       if x.get("sha256")],
        "screened_candidates":len(ranked),
        "precheck_8_of_8":sum(x.get("exact_field_count")==8 for x in ranked),
        "fully_checked_header_candidates":sum(bool(x.get("evaluation")) for x in ranked),
        "verified_same_sic_independent_peers":len(peer_rows),
        "required_peers":MIN_OTHER_PEERS,
        "ranked_candidates":ranked,
        "ranked_rejection_counts":dict(Counter(x["status"] for x in ranked)),
        "stop_reason":stop_reason,
        "network_requests":sec.requests,"cached_responses":sec.cached,
        "http_statuses":dict(sec.http_statuses),
        "source_receipts":sec.receipts,
        "s11_score":result["score"],"s11_missing":result["missing"],
        "s11_result_evidence_hash":result["evidence_hash"],
        "s11_components":result["components"],
        "independent_decimal_reference":independent,
        "canonical_accepted":False,"historical_pit_accepted":False,
        "status":"VERIFIED_RESEARCH" if result["score"] is not None else "DATA_MISSING",
    }
    return final
