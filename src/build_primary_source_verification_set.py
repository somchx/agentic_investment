"""AI-assisted primary-source verification set: for every (ticker,
reason_key)'s latest quarter, confirms the exact dollar figure the live
pipeline's check_reason_status() relied on (from XBRL) is actually printed
in the primary 10-Q/10-K filing text (not the 8-K press release -- a third
independent source), and quotes the surrounding table text as a citation.

This is a citation search, not blind independent re-extraction -- see the
docstring on verify_one() for why: primary 10-Q income-statement tables
don't share one column-order convention across companies (some list the
prior-year column before the current one), which broke a first attempt at
blindly parsing "the first number after the keyword" the same way
earnings_release.py does for 8-K exhibits. Confirming the already-known
value is genuinely printed nearby is more robust to table layout while
still checking against a source outside the XBRL/8-K pipeline.

**Precise about what this is, deliberately, on the module name itself:**
this is Claude (the agent building this project) reading primary-source
text and recording a judgment with a citation -- not a professional human
analyst, and not what "human-verified" implies. Renamed from an earlier
"human_gold_set" name for exactly this reason: call it "AI-assisted
primary-source verification," not "human-labeled ground truth," in any
write-up. It is a genuinely independent read of the primary legal filing
document, distinct from both the XBRL structured-data pipeline and the 8-K
earnings-release cross-check already in data/gold_set.json -- a third
source, not a rubber stamp of either, but still not human labeling. A
stronger claim would need an actual person with accounting/finance
background reading a stratified sample of primary filings independently.

Free: only SEC document fetches, no LLM API calls.

Usage:
    python3 build_primary_source_verification_set.py
"""

import json
import re

from earnings_release import METRIC_KEYWORDS, _clean_text
from filing_context import _find_primary_document
from sec_client import KNOWN_CIKS, get_company_facts, get_document_text
from tools import REASON_DEFS, SECONDARY_EVIDENCE_METRICS, check_reason_status
from xbrl_extract import extract_instant_facts, extract_quarterly_facts

OUT_PATH = "../data/primary_source_verification_set.json"

HISTORY_DEPTH = 8  # distinct filed-dates to sample per (ticker, reason_key)


def historical_as_of_dates(ticker: str, reason_key: str, n: int = HISTORY_DEPTH) -> list[str]:
    """The last `n` distinct filed-dates for this reason's underlying metric
    -- walking these as simulated "today" dates through check_reason_status
    is how portfolio_report.py/main.py replay a reason's status history, and
    the same mechanism works here to sample more than just the latest
    quarter for free. Includes restated-value filed-dates too (not just one
    per quarter); duplicate quarters that resolves to are deduped later by
    accession_number in run().
    """
    metric = SECONDARY_EVIDENCE_METRICS[reason_key]
    facts_json = get_company_facts(ticker)
    cik = str(facts_json.get("cik")).zfill(10)
    if metric == "LongTermDebt":
        facts = extract_instant_facts(facts_json, cik, metric)
    else:
        facts = extract_quarterly_facts(facts_json, cik, metric)
    dates = sorted({f.filed for f in facts})
    return dates[-n:]


def _format_candidates(raw_value: float) -> list[str]:
    """The same dollar amount can be printed in a filing table as millions
    ("82,886"), thousands ("82,886,000"), or occasionally full dollars --
    generate the comma-grouped strings for each plausible scale so the
    search isn't locked into one company's formatting convention.
    """
    candidates = []
    for divisor in (1_000_000, 1_000, 1):
        scaled = raw_value / divisor
        if abs(scaled - round(scaled)) < 0.5:  # only whole-number-looking scales
            candidates.append(f"{round(scaled):,}")
    return candidates


EVIDENCE_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2}) = ([\d,]+) \w+ \(filed (\d{4}-\d{2}-\d{2}), ([\w-]+), accn ([\d-]+)\)"
)


def verify_one(ticker: str, reason_key: str, as_of: str | None = None) -> dict:
    """Citation-search approach, not blind independent extraction: primary
    10-Q/10-K income-statement tables turned out not to share one column
    order (Amazon's 10-Q lists the prior-year quarter *before* the current
    one; Apple's did the opposite), so blindly taking "the first number
    after the keyword" -- which worked for earnings_release.py's 8-K
    exhibits -- silently grabbed the wrong column here on several
    companies. Instead: take the number the live pipeline already trusts
    (from XBRL), and confirm that exact figure is actually printed in the
    primary filing's text near the relevant keyword. Weaker than fully
    independent re-derivation, but robust to table layout, and still a
    genuine check against a source outside the XBRL/8-K pipeline (the
    literal legal filing document) rather than trusting the extractor.

    Fetches the SPECIFIC filing the XBRL evidence citation names (parsed
    from Fact.label()'s "(filed <date>, <form>, accn <accn>)" suffix), not
    just "whichever 10-Q/10-K is most recent." A first version always
    fetched the latest filing and got this wrong for companies whose most
    recent filing is a 10-K: MSFT's latest 10-K prints only full fiscal
    year figures ($331,839M FY2026), not the $82,886M quarterly figure the
    live pipeline's growth calculation actually used, which was filed
    months earlier in a 10-Q -- the quarterly number the pipeline relies on
    isn't necessarily re-printed anywhere in the newest document at all.
    """
    metric = SECONDARY_EVIDENCE_METRICS[reason_key]
    facts_json = get_company_facts(ticker)
    cik = str(facts_json.get("cik")).zfill(10)
    company_name = facts_json.get("entityName", ticker)

    live = check_reason_status(ticker, reason_key, as_of=as_of)
    supporting = live.get("supporting_evidence", [])

    xbrl_raw_value = None
    form = accn = period_end = None
    for ev in supporting:
        if metric not in ev:
            continue
        m = EVIDENCE_RE.search(ev)
        if not m:
            continue
        period_end = m.group(1)
        xbrl_raw_value = float(m.group(2).replace(",", ""))
        form, accn = m.group(4), m.group(5)
        break

    if xbrl_raw_value is None or not accn:
        return {
            "ticker": ticker, "company": company_name, "reason_key": reason_key,
            "category": "Missing", "verified": False, "as_of_used": as_of,
            "note": f"live pipeline itself has no {metric} evidence for {ticker} "
                    f"(status={live.get('status')}) -- nothing to cross-check against the filing",
            "live_status": live.get("status"),
        }

    doc = _find_primary_document(cik, accn)
    if not doc:
        return {
            "ticker": ticker, "company": company_name, "reason_key": reason_key,
            "category": "Missing", "verified": False, "as_of_used": as_of,
            "note": f"could not locate primary document in filing {accn}", "live_status": live.get("status"),
        }

    html = get_document_text(cik, accn, doc)
    text = _clean_text(html)

    # Bug found and fixed: this originally searched a combined keyword list
    # for all three metrics regardless of which one `metric` actually was,
    # so operating_margin/debt_growth checks kept anchoring on "Revenue"
    # (found earlier in every document) instead of their own section --
    # the 5000-char window from there never reached the real Operating
    # Income or Debt line. Use the metric-specific keyword list instead
    # (same one earnings_release.py's 8-K parser already uses).
    keyword_pos = None
    for keyword in METRIC_KEYWORDS[metric]:
        idx = text.find(keyword)
        if idx != -1:
            keyword_pos = idx
            break

    found_at = None
    for candidate in _format_candidates(xbrl_raw_value):
        idx = text.find(candidate, max(0, (keyword_pos or 0) - 200))
        if idx != -1 and (keyword_pos is None or idx - keyword_pos < 5000):
            found_at = idx
            break

    if found_at is None:
        return {
            "ticker": ticker, "company": company_name, "reason_key": reason_key, "as_of_used": as_of,
            "metric": metric, "category": "Primary-filing-verified", "verified": True,
            "filing_form": form, "accession_number": accn, "primary_document": doc, "period_end": period_end,
            "xbrl_pipeline_value": xbrl_raw_value, "agrees_with_xbrl": False,
            "note": "XBRL-derived figure not found printed anywhere near the relevant "
                    "section of the primary filing text -- worth a manual look",
            "live_status": live.get("status"), "live_computed_value": live.get("computed_value"),
        }

    quote = text[max(0, found_at - 150): found_at + 150]
    return {
        "ticker": ticker,
        "company": company_name,
        "reason_key": reason_key,
        "as_of_used": as_of,
        "metric": metric,
        "category": "Primary-filing-verified",
        "verified": True,
        "filing_form": form,
        "accession_number": accn,
        "primary_document": doc,
        "period_end": period_end,
        "xbrl_pipeline_value": xbrl_raw_value,
        "agrees_with_xbrl": True,
        "quoted_text": quote.strip(),
        "live_status": live.get("status"),
        "live_computed_value": live.get("computed_value"),
    }


def run() -> None:
    tickers = sorted(KNOWN_CIKS.keys())
    results = []
    for ticker in tickers:
        print(f"--- {ticker} ---")
        for reason_key in REASON_DEFS:
            seen_accns = set()
            count = 0

            # Always check the current/latest state first (as_of=None) --
            # this is what surfaces genuine current "Missing" cases like
            # JNJ's operating margin. If historical sampling ran *instead*
            # of this, tickers whose metric stopped being reported at some
            # point would only ever hit the old dates when it still existed,
            # silently losing the "currently Missing" case entirely.
            as_of_candidates = [None] + list(reversed(historical_as_of_dates(ticker, reason_key)))

            for as_of in as_of_candidates:
                r = verify_one(ticker, reason_key, as_of=as_of)
                accn_key = r.get("accession_number")
                if accn_key and accn_key in seen_accns:
                    continue  # same filing resolved again from a nearby as_of -- not a new data point
                if accn_key:
                    seen_accns.add(accn_key)
                elif count > 0:
                    continue  # already recorded one "Missing" for this (ticker, reason_key) -- don't repeat it per historical date
                results.append(r)
                count += 1
                label = as_of or "latest"
                if r["verified"]:
                    flag = "CONFIRMED" if r["agrees_with_xbrl"] else "NOT FOUND IN TEXT"
                    print(f"  [{reason_key}] {label} {flag}: xbrl={r['xbrl_pipeline_value']:,.0f} "
                          f"live_status={r['live_status']}")
                else:
                    print(f"  [{reason_key}] {label} NOT VERIFIED: {r['note']} (live_status={r['live_status']})")

    # Manually diagnosed, one call each, why the citation search missed
    # these 5 (recorded here rather than left as a bare "not found" --
    # each is a distinct, real failure mode of full-text search on large
    # SEC documents, not one bug repeated 5 times):
    diagnoses = {
        ("COST", "revenue_growth"): (
            "Keyword matched a 'Financial Highlights' summary table earlier in the "
            "document showing a different (adjacent, not current) quarter's figures "
            "before the real income statement -- a document-structure issue, not a "
            "wrong number in the filing."
        ),
        ("JNJ", "revenue_growth"): (
            "Keyword matched inline-XBRL tag metadata (e.g. "
            "'RevenueFromContractWithCustomerExcludingAssessedTax us-gaap:...') left "
            "in the text after HTML-tag stripping -- the cleaning regex doesn't fully "
            "remove <ix:...> inline XBRL elements for this filer's document structure."
        ),
        ("MSFT", "debt_growth"): (
            "Keyword matched a 'Long-term debt' commitments/payment-schedule table "
            "(future obligations by year) that appears earlier in the document than "
            "the actual balance sheet line."
        ),
        ("PEP", "revenue_growth"): (
            "Same inline-XBRL-metadata artifact as JNJ."
        ),
        ("PG", "debt_growth"): (
            "Keyword matched an accounting-policy footnote sentence ('Long-term debt "
            "designated in a fair value hedging relationship is adjusted...') before "
            "the balance sheet line itself."
        ),
    }
    for r in results:
        key = (r["ticker"], r["reason_key"])
        # Only the latest-quarter entry (as_of_used is None) -- these
        # diagnoses were derived from that specific quarter's document; a
        # historical quarter's citation-search miss (if any) is a different
        # instance of the document-structure problem and needs its own look,
        # not this quarter's canned explanation copy-pasted onto it.
        if key in diagnoses and r.get("as_of_used") is None:
            r["diagnosis"] = diagnoses[key]

    # The 4 structural categories a flat per-quarter scan can't produce
    # (they're rare, cross-period phenomena, not properties of one quarter)
    # -- the concrete real cases already found and verified earlier this
    # session, with their evidence citations, recorded here so the full
    # stratified set (Supported/Weakened/Broken/Missing from the scan above,
    # plus these 4) lives in one place.
    structural_cases = [
        {
            "category": "Restatement",
            "ticker": "MSFT",
            "description": (
                "Revenue for the quarter ending 2016-09-30 was originally reported as "
                "$20,453M (10-Q filed 2016-10-20, accn 0001193125-16-742796), then "
                "restated to $21,928M (+7.2%) in filings from 2017-10-26 onward "
                "(accn 0001564590-17-020171) -- Microsoft's early adoption of the "
                "ASC 606 revenue recognition standard. Verified via XBRL: the same "
                "SalesRevenueNet tag reports two different values for the identical "
                "period at different filed dates. See 'Fixed: a spurious conflict...' "
                "and the earlier ASC 606 section in README.md."
            ),
            "evidence_type": "XBRL cross-filing comparison (not primary-text-quoted)",
        },
        {
            "category": "Tag/definition conflict (not a restatement)",
            "ticker": "MSFT",
            "description": (
                "Same 10-K (accn 0001193125-26-323660) reports both LongTermDebtNoncurrent "
                "($31.1B, excludes debt due within a year) and LongTermDebt ($40.3B, "
                "includes it) for the identical quarter-end -- two different accounting "
                "concepts, not two versions of the same number. See 'Fixed: a spurious "
                "conflict from merging two different accounting concepts' in README.md."
            ),
            "evidence_type": "XBRL, same-filing dual-tag comparison",
        },
        {
            "category": "Real anomaly (financing event, not a data problem)",
            "ticker": "GOOGL",
            "description": (
                "Long-term debt grew from ~$10.9B (Q1 2025) to ~$98.2B (Q2 2026, "
                "+315.8%). Confirmed via the actual 10-Q primary filing text (not "
                "just XBRL): 'Long-Term Debt During 2026, we issued $20.0 billion of "
                "US dollar-denominated fixed-rate senior unsecured notes and $31.8 "
                "billion of foreign currency-denominated fixed-rate senior unsecured "
                "notes for general corporate purposes.' Independently re-confirmed by "
                "investigate.py's real LLM run: is_data_artifact=False."
            ),
            "evidence_type": "Primary filing text, directly quoted",
        },
        {
            "category": "Data artifact (filer's own XBRL tagging error)",
            "ticker": "ORCL",
            "description": (
                "Oracle's own FY2020 10-K (accn not re-verified in this pass; see gold "
                "set section in README.md) tags a Revenue datapoint with quarter-length "
                "start/end dates (2018-03-01 to 2018-05-31, 91 days -- passes this "
                "project's single-quarter filter) but a value of $39.4B -- Oracle's "
                "actual full-year FY2018 revenue, not a quarter's. The filer's own "
                "tagging is internally inconsistent, not a bug in this project's "
                "extraction code."
            ),
            "evidence_type": "XBRL internal inconsistency (start/end length vs. value magnitude)",
        },
    ]
    results.extend(structural_cases)

    with open(OUT_PATH, "w") as f:
        json.dump(results, f, indent=2)

    verified = [r for r in results if r.get("verified")]
    agree = [r for r in verified if r["agrees_with_xbrl"]]
    missing = [r for r in results if r.get("verified") is False]
    print(f"\nWrote {len(results)} entries to {OUT_PATH} (incl. {len(structural_cases)} structural cases)")
    print(f"Verified against primary filing text: {len(verified)}")
    print(f"  of which confirmed (value found in primary filing text): {len(agree)}/{len(verified)}")
    print(f"Not verified (metric absent from primary filing, confirms 'Not enough data'): {len(missing)}")
    for m in missing:
        print(f"  {m['ticker']} [{m['reason_key']}]: {m['note']}")


if __name__ == "__main__":
    run()
