"""Investigation capability: fetch the actual narrative text from a 10-Q
(not just the XBRL numbers) explaining *why* a metric moved -- the MD&A
(Management's Discussion and Analysis) section. This is what an agent
needs to distinguish "debt spiked because of a bond issuance for AI capex"
from "debt spiked because of an accounting restatement" from "debt spiked
because of an acquisition" -- something a numeric threshold check alone
can never answer, no matter how the Weakened/Broken boundary is tuned.

Retrieval here is free (SEC HTML fetch + text search, no LLM calls). Only
an LLM actually reading and synthesizing the retrieved paragraphs into an
explanation costs API budget -- that step is NOT wired up yet, see
README.md.

Proof of concept, verified against GOOGL's real Q2 2026 10-Q: the primary
filing document (not the XBRL data, not the press release) contains a
"Long-Term Debt" narrative section reading "During 2026, we issued $20.0
billion of US dollar-denominated fixed-rate senior unsecured notes and
$31.8 billion of [other notes]..." -- exactly the kind of explanation this
project's Broken debt reason (GOOGL, AMZN, META, TSLA all currently show
this) needs before a human reviewer should trust it's a financing event
and not a data problem.
"""

import re

from sec_client import get_document_text, get_filing_index_html, get_submissions

# Keywords for the narrative section covering each reason's metric, in
# priority order -- 10-Qs organize MD&A under headings like these.
SECTION_KEYWORDS = {
    "Revenue": ["Revenues", "Net Sales", "Results of Operations"],
    "OperatingIncome": ["Operating Income", "Operating Margin", "Results of Operations"],
    "LongTermDebt": ["Long-Term Debt", "Financing", "Liquidity and Capital Resources"],
}


def _find_primary_document(cik: str, accession_number: str) -> str | None:
    """The main 10-Q/10-K document (not an exhibit) -- the filing index
    lists it with type "10-Q" or "10-K", distinct from EX-* exhibits.
    """
    html = get_filing_index_html(cik, accession_number)
    rows = re.findall(r"<tr.*?</tr>", html, re.S)
    for row in rows:
        if re.search(r">10-[QK]<", row):
            clean = re.sub(r"<[^>]+>", " ", row)
            match = re.search(r"(\S+\.htm)", clean)
            if match:
                return match.group(1)
    return None


def _clean_text(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def latest_10q_accession(ticker: str) -> str:
    """Most recent 10-Q/10-K accession number for a company -- the filing
    whose narrative reflects the reason being investigated right now.
    """
    subs = get_submissions(ticker)
    recent = subs["filings"]["recent"]
    for form, accn in zip(recent["form"], recent["accessionNumber"]):
        if form in ("10-Q", "10-K"):
            return accn
    raise RuntimeError(f"no 10-Q/10-K found for {ticker}")


def get_filing_narrative(cik: str, accession_number: str, metric: str, context_chars: int = 800) -> list[str]:
    """Return the text surrounding each occurrence of this metric's section
    keywords in the primary 10-Q/10-K document -- the narrative explanation
    a human (or an LLM investigating an anomaly) would actually read.

    Returns an empty list if the primary document or none of the keywords
    could be found; callers should treat that as "no narrative evidence
    available," not as an error.
    """
    doc = _find_primary_document(cik, accession_number)
    if not doc:
        return []

    html = get_document_text(cik, accession_number, doc)
    text = _clean_text(html)

    snippets = []
    for keyword in SECTION_KEYWORDS.get(metric, []):
        # Case-insensitive: filers vary ("Long-Term Debt" vs Amazon's
        # "Long-term debt"), and a case-sensitive miss silently fell through
        # to a lower-priority keyword and grabbed the wrong section (a lease
        # commitments table instead of the actual debt-issuance narrative).
        for m in re.finditer(re.escape(keyword), text, re.I):
            start = max(0, m.start() - 50)
            end = min(len(text), m.start() + context_chars)
            snippets.append(text[start:end])
        if snippets:
            break  # first keyword that actually appears wins
    return snippets
