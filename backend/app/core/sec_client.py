"""Thin client for the SEC XBRL Frames / Company Facts API.

Docs: https://www.sec.gov/os/webmaster-faq#developers
SEC requires a descriptive User-Agent on every request (name + contact email).
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)


class UnsupportedTickerError(Exception):
    """The ticker/CIK genuinely doesn't exist in SEC EDGAR (a 404 on the
    company-facts endpoint itself, not a missing fact within an otherwise
    real company) -- distinct from SecDataUnavailableError so a caller can
    tell "this isn't a real company" apart from "SEC is temporarily down"
    instead of both surfacing as the same generic RequestException (Code
    Audit Session 4 follow-up, item 1/3: an invalid ticker was coming back
    as a completed 'Not enough data' investigation report instead of a
    distinct, cheap, pre-LLM rejection)."""


class SecDataUnavailableError(Exception):
    """SEC EDGAR itself is unreachable/erroring (network failure, timeout,
    5xx) with no cached fallback available -- an infrastructure problem,
    not a fact about the company being investigated. Callers must not let
    this be interpreted as evidence ("Not enough data") or presented as
    part of a completed analysis; it should abort and surface as a
    service-unavailable condition instead."""

USER_AGENT = os.environ.get(
    "SEC_USER_AGENT", "Investment-IS-Project research-contact@example.com"
)
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache")

# get_company_facts() previously cached forever once fetched -- `force_refresh`
# was never actually passed True anywhere in the codebase (Continuous
# Monitoring included), so the cache silently never saw a company's new
# quarterly filing again after the first fetch (confirmed on this project's
# own dev cache: files untouched for 13 days while the hourly monitoring
# job kept running against them). A TTL makes monitoring/`check_reason_status`
# calls eventually see new data on their own, without hammering SEC on every
# single request the way force_refresh=True on every call would (Code Audit
# Session 2, item 1).
CACHE_TTL_SECONDS = int(os.environ.get("SEC_CACHE_TTL_SECONDS", 24 * 3600))


def _is_cache_fresh(path: str) -> bool:
    return os.path.exists(path) and (time.time() - os.path.getmtime(path)) < CACHE_TTL_SECONDS


def get_data_freshness(ticker_or_cik: str) -> dict:
    """Provenance metadata for a company's cached SEC data -- when it was
    last actually fetched, and whether it's within the freshness window.
    Never returns anything that would let a caller present stale data as
    if it were current: `is_stale=True` means the last successful fetch is
    older than CACHE_TTL_SECONDS, so a viewer should not assume it reflects
    any filing published since then (Code Audit Session 3, item 4).
    `cached_at`/`age_seconds` are None if there is no cache file at all yet
    (first-ever request for this ticker)."""
    cik = KNOWN_CIKS.get(ticker_or_cik.upper(), ticker_or_cik).zfill(10)
    path = _cache_path(cik)
    if not os.path.exists(path):
        return {"cached_at": None, "age_seconds": None, "is_stale": None}
    mtime = os.path.getmtime(path)
    age = time.time() - mtime
    return {
        "cached_at": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
        "age_seconds": int(age),
        "is_stale": age >= CACHE_TTL_SECONDS,
    }

# The Phase 1 pilot company set (PROPOSAL.md 3.1 target: 10-15 companies).
# CIKs pulled from SEC's own ticker->CIK mapping (company_tickers.json), not
# hand-typed, to avoid pointing at a stale or wrong entity.
KNOWN_CIKS = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "NVDA": "0001045810",
    "GOOGL": "0001652044",
    "AMZN": "0001018724",
    "META": "0001326801",
    "TSLA": "0001318605",
    "PEP": "0000077476",
    "JNJ": "0000200406",
    "PG": "0000080424",
    "KO": "0000021344",
    "WMT": "0000104169",
    "NFLX": "0001065280",
    "ORCL": "0001341439",
    "COST": "0000909832",
}


def is_supported_ticker(ticker: str) -> bool:
    """Whether `ticker` is one of this project's Phase 1 pilot companies
    (KNOWN_CIKS) -- the cheap, pre-LLM check callers should run before
    starting an investigation, so an obviously-wrong ticker never costs a
    Claude API call at all."""
    return ticker.upper() in KNOWN_CIKS


def _cache_path(cik: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"CIK{cik}.json")


def _classify_request_exception(e: requests.RequestException, url: str) -> Exception:
    """Shared classification for every SEC fetch, not just get_company_facts
    -- get_submissions/get_filing_index_html/get_document_text (used by the
    secondary-evidence and filing-context tools) previously let a raw
    RequestException escape unclassified, which meant a genuine SEC outage
    hitting one of THOSE endpoints was swallowed as an isolated per-tool
    TOOL_UNAVAILABLE instead of aborting the whole investigation the way a
    company-facts outage does (Code Audit Session 4 follow-up, item 1/3:
    reproduced for real -- a mocked SEC outage during get_secondary_evidence
    for a ticker with no cached submissions file completed as a normal
    report instead of surfacing as Data Source Unavailable)."""
    if isinstance(e, requests.HTTPError) and e.response is not None and e.response.status_code == 404:
        return UnsupportedTickerError(f"SEC returned 404 for {url} -- not a real CIK/filing")
    return SecDataUnavailableError(f"SEC EDGAR is unreachable: {e}")


def _get_json(url: str) -> dict:
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise _classify_request_exception(e, url) from e
    time.sleep(0.15)
    return resp.json()


def _get_text(url: str) -> str:
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise _classify_request_exception(e, url) from e
    time.sleep(0.15)
    return resp.text


def get_submissions(ticker_or_cik: str, force_refresh: bool = False) -> dict:
    """Fetch (and cache) the filing history index for one company.

    Used to locate 8-K earnings-release exhibits, which are not part of the
    XBRL company-facts payload.
    """
    cik = KNOWN_CIKS.get(ticker_or_cik.upper(), ticker_or_cik).zfill(10)
    path = os.path.join(CACHE_DIR, f"submissions_CIK{cik}.json")

    if os.path.exists(path) and not force_refresh:
        with open(path, "r") as f:
            return json.load(f)

    os.makedirs(CACHE_DIR, exist_ok=True)
    data = _get_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
    with open(path, "w") as f:
        json.dump(data, f)
    return data


def get_filing_index_html(cik: str, accession_number: str) -> str:
    """Fetch the human-readable filing index page listing each document's
    EDGAR-assigned type (e.g. 'EX-99.1'), cached per accession."""
    cik_nozero = str(int(cik))
    accn_nodash = accession_number.replace("-", "")
    path = os.path.join(CACHE_DIR, f"index_{accession_number}.html")

    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()

    os.makedirs(CACHE_DIR, exist_ok=True)
    url = (
        f"https://www.sec.gov/Archives/edgar/data/{cik_nozero}/{accn_nodash}/"
        f"{accession_number}-index.html"
    )
    text = _get_text(url)
    with open(path, "w") as f:
        f.write(text)
    return text


def get_document_text(cik: str, accession_number: str, filename: str) -> str:
    """Fetch a specific document from within one filing, cached to disk."""
    cik_nozero = str(int(cik))
    accn_nodash = accession_number.replace("-", "")
    path = os.path.join(CACHE_DIR, f"doc_{accession_number}_{filename}")

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    os.makedirs(CACHE_DIR, exist_ok=True)
    url = f"https://www.sec.gov/Archives/edgar/data/{cik_nozero}/{accn_nodash}/{filename}"
    text = _get_text(url)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def get_company_facts(ticker_or_cik: str, force_refresh: bool = False) -> dict:
    """Fetch (and cache) the full XBRL company-facts payload for one company.

    Accepts either a known ticker (see KNOWN_CIKS) or a raw 10-digit CIK.
    Re-fetches once the cache is older than CACHE_TTL_SECONDS (default 24h)
    even without force_refresh=True, so a scheduled job like Continuous
    Monitoring eventually sees a company's new filing on its own instead of
    being stuck on whatever was cached the first time anyone ever asked for
    this ticker.
    """
    cik = KNOWN_CIKS.get(ticker_or_cik.upper(), ticker_or_cik).zfill(10)
    path = _cache_path(cik)

    if not force_refresh and _is_cache_fresh(path):
        with open(path, "r") as f:
            return json.load(f)

    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        # SEC unreachable/rate-limited -- fall back to whatever is cached
        # (even if stale) rather than taking down every caller (Continuous
        # Monitoring, the Investigation Agent, the dashboard) on a transient
        # network blip. Only re-raise if there is truly nothing to fall
        # back to. Logged explicitly (Code Audit Session 3, item 4) so this
        # never happens silently -- the file's mtime is deliberately left
        # untouched, so get_data_freshness() keeps reporting is_stale=True
        # for it until a real refresh succeeds.
        if os.path.exists(path):
            age_hours = (time.time() - os.path.getmtime(path)) / 3600
            logger.warning(
                "SEC fetch failed for CIK%s (%s) -- serving cached data %.1fh old instead of raising",
                cik, e, age_hours,
            )
            with open(path, "r") as f:
                return json.load(f)
        # Nothing cached to fall back to -- classify the failure so callers
        # can tell "this CIK doesn't exist" (UnsupportedTickerError) apart
        # from "SEC itself is down" (SecDataUnavailableError) instead of
        # both surfacing as the same generic RequestException (Code Audit
        # Session 4 follow-up, items 1 and 3).
        if isinstance(e, requests.HTTPError) and e.response is not None and e.response.status_code == 404:
            raise UnsupportedTickerError(
                f"no SEC company-facts found for CIK{cik} (from {ticker_or_cik!r}) -- not a real CIK"
            ) from e
        logger.error("SEC data source unreachable for CIK%s and nothing cached: %s", cik, e)
        raise SecDataUnavailableError(f"SEC EDGAR is unreachable: {e}") from e

    with open(path, "w") as f:
        json.dump(data, f)
    time.sleep(0.15)  # be polite to SEC rate limits (10 req/s max)

    return data


if __name__ == "__main__":
    import sys

    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    facts = get_company_facts(ticker)
    print(f"{ticker}: entityName={facts.get('entityName')}, "
          f"tags={len(facts.get('facts', {}).get('us-gaap', {}))}")
