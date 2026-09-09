"""Build a stratified sample for a real human (accounting/finance background)
to review -- the thing this project's own verification so far can't be:
independent human labeling, not AI reading text and citing itself.

Pulls from data/gold_set.json (XBRL vs 8-K) and
data/primary_source_verification_set.json (XBRL vs primary filing text,
AI-assisted -- see that module's docstring for why it's not called
"human-verified") to select cases spanning every category a reviewer should
see, with a direct clickable link to the actual SEC filing index page for
each one so reviewing means "open this link and check," not "trust our
citation."

Free: no LLM calls, just reads the two JSON files this project already
built and formats real EDGAR URLs.

Usage:
    python3 build_review_sample.py
"""

import json

from sec_client import KNOWN_CIKS

PRIMARY_PATH = "../data/primary_source_verification_set.json"
OUT_JSON = "../data/review_sample.json"
OUT_MD = "../data/review_sample.md"


def filing_url(cik: str, accession_number: str) -> str:
    cik_nozero = str(int(cik))
    accn_nodash = accession_number.replace("-", "")
    return (
        f"https://www.sec.gov/Archives/edgar/data/{cik_nozero}/"
        f"{accn_nodash}/{accession_number}-index.htm"
    )


REASON_DESCRIPTIONS = {
    "revenue_growth": "Revenue growth must exceed 10% YoY",
    "operating_margin": "Operating margin must stay at or above 20%",
    "debt_growth": "Long-term debt must not grow more than 15% YoY",
}


def _pick_diverse(candidates: list[dict], cap: int, max_per_ticker: int = 2) -> list[dict]:
    """Cap a bucket's size while spreading across tickers/quarters instead
    of e.g. filling all 15 "Broken" slots with the same company's history --
    picking the same ticker's 10 quarters in a row doesn't add reviewer
    coverage the way one quarter each from 10 different tickers does.
    """
    picked = []
    per_ticker = {}
    for r in candidates:
        t = r["ticker"]
        if per_ticker.get(t, 0) >= max_per_ticker:
            continue
        picked.append(r)
        per_ticker[t] = per_ticker.get(t, 0) + 1
        if len(picked) >= cap:
            break
    return picked


def build_sample(cap_per_status: int = 15, cap_needs_eyes: int = 10) -> list[dict]:
    with open(PRIMARY_PATH) as f:
        primary = json.load(f)

    per_quarter = [r for r in primary if r.get("category") == "Primary-filing-verified"]
    missing = [r for r in primary if r.get("category") == "Missing"]
    structural = [r for r in primary if r.get("category") not in ("Primary-filing-verified", "Missing")]

    by_status = {}
    for r in per_quarter:
        by_status.setdefault(r["live_status"], []).append(r)

    sample = []

    # Supported / Weakened / Broken -- up to cap_per_status each, spread
    # across tickers/quarters rather than one company's whole history,
    # prioritizing cases the citation search itself already confirmed
    # (still needs independent human eyes -- this just gives the reviewer a
    # cleaner starting set; the harder "not found" cases are their own
    # bucket below so they aren't lost, just not mixed in here).
    for status, review_cat in (("Supported", "Supported"), ("Weakened", "Weakened"), ("Broken", "Broken")):
        confirmed = [r for r in by_status.get(status, []) if r["agrees_with_xbrl"]]
        for r in _pick_diverse(confirmed, cap_per_status):
            sample.append({**r, "review_category": review_cat})

    # Missing / Not enough data -- both real cases.
    for r in missing:
        sample.append({**r, "review_category": "Missing / Not enough data"})

    # Needs-human-eyes: the citation search couldn't confirm these near an
    # automated match -- exactly the cases where a human reading the filing
    # directly adds the most value over this project's own automated checks.
    already = {(r["ticker"], r["reason_key"], r.get("as_of_used")) for r in sample}
    not_found = [
        r for r in per_quarter
        if not r["agrees_with_xbrl"] and (r["ticker"], r["reason_key"], r.get("as_of_used")) not in already
    ]
    for r in _pick_diverse(not_found, cap_needs_eyes):
        sample.append({**r, "review_category": "Needs human eyes (automated citation search failed)"})

    # The 4 structural cases already curated with real evidence.
    for r in structural:
        sample.append({**r, "review_category": r["category"]})

    # Attach a real, clickable link to the specific filing for every case
    # that has an accession number.
    for r in sample:
        cik = KNOWN_CIKS.get(r["ticker"])
        accn = r.get("accession_number")
        if cik and accn:
            r["filing_url"] = filing_url(cik, accn)

    return sample


def write_markdown(sample: list[dict]) -> None:
    lines = [
        "# Stratified Review Sample",
        "",
        "For a reviewer with accounting/finance background to independently confirm.",
        "Each entry links to the actual SEC filing -- please open it and check the claim",
        "yourself rather than trusting the quoted text/values below.",
        "",
    ]

    by_cat = {}
    for r in sample:
        by_cat.setdefault(r["review_category"], []).append(r)

    for category, entries in by_cat.items():
        lines.append(f"## {category} ({len(entries)})")
        lines.append("")
        for r in entries:
            ticker = r.get("ticker", "?")
            reason_key = r.get("reason_key", "")
            desc = REASON_DESCRIPTIONS.get(reason_key, reason_key)
            lines.append(f"### {ticker} -- {desc}" if reason_key else f"### {ticker}")
            if r.get("filing_url"):
                lines.append(f"- **Filing:** [{r.get('filing_form', '')} {r.get('accession_number', '')}]({r['filing_url']})")
            if "xbrl_pipeline_value" in r and r["xbrl_pipeline_value"] is not None:
                lines.append(f"- **Pipeline's value:** {r['xbrl_pipeline_value']:,.0f}")
            if "live_status" in r:
                lines.append(f"- **Pipeline's status:** {r['live_status']}")
            if r.get("quoted_text"):
                lines.append(f"- **Quoted from filing:** \"{r['quoted_text']}\"")
            if r.get("description"):
                lines.append(f"- **Claim:** {r['description']}")
            if r.get("note"):
                lines.append(f"- **Note:** {r['note']}")
            if r.get("diagnosis"):
                lines.append(f"- **Why automated check failed:** {r['diagnosis']}")
            lines.append("- **Reviewer verdict:** ___________  **Notes:** ___________")
            lines.append("")

    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))


def run() -> None:
    sample = build_sample()
    with open(OUT_JSON, "w") as f:
        json.dump(sample, f, indent=2)
    write_markdown(sample)

    from collections import Counter
    counts = Counter(r["review_category"] for r in sample)
    print(f"Built {len(sample)}-case stratified review sample:")
    for cat, n in counts.items():
        print(f"  {cat}: {n}")
    print(f"\nWrote {OUT_JSON} and {OUT_MD}")


if __name__ == "__main__":
    run()
