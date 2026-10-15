"""Real-time-ish market price data -- the "Market Data" tool PROPOSAL.md
section 5 already anticipated as a Phase 1 (Optional) component ("ราคาหุ้น,
Volume -- ใช้ประกอบถ้าจำเป็น"). Distinct from sec_client.py's SEC EDGAR
data in both source and purpose:

- Source: Yahoo Finance's public chart endpoint -- free, no API key, no
  signup, consistent with this project's existing preference for free
  data sources (SEC EDGAR is also free/no-key). Unofficial but widely
  used; if it ever breaks, a paid provider (Alpha Vantage, Finnhub,
  Polygon) is a drop-in replacement behind this same get_quote()
  interface.
- Purpose: display only (current price, day change, portfolio unrealized
  P&L) -- never evidence for a reason's Supported/Weakened/Broken status,
  which must stay point-in-time SEC filing data only. Same discipline as
  why WEB_SEARCH_TOOL is barred from status decisions in agent.py: a live
  price is today's number, not knowable as of any historical as_of date,
  so it has no role in the Evidence Gate's point-in-time guarantee.

"Real-time" here means refreshed on a short cache TTL (~30s) when polled,
not a tick-by-tick streaming feed -- intraday price during market hours,
previous close otherwise (Yahoo's own `regularMarketPrice` reports
whichever is current).
"""

import logging
import time

import requests

logger = logging.getLogger(__name__)

USER_AGENT = "Investment-IS-Project research-contact@example.com"
QUOTE_CACHE_TTL_SECONDS = 30

# ticker -> (cached_at, quote dict)
_quote_cache: dict[str, tuple[float, dict]] = {}


class MarketDataUnavailableError(Exception):
    """The price data source is unreachable, rate-limited, or returned no
    usable data for this ticker -- an infrastructure/data problem, not a
    fact about the company. Mirrors sec_client.SecDataUnavailableError's
    role: callers must not treat a missing quote as "price is zero" or
    silently omit it from a P&L calculation."""


def _is_fresh(ticker: str) -> bool:
    cached = _quote_cache.get(ticker)
    return cached is not None and (time.time() - cached[0]) < QUOTE_CACHE_TTL_SECONDS


def get_quote(ticker: str) -> dict:
    """Current price snapshot for `ticker`. Cached for
    QUOTE_CACHE_TTL_SECONDS so a page polling every few seconds doesn't
    hammer the upstream API on every request.
    """
    ticker = ticker.upper()
    if _is_fresh(ticker):
        return _quote_cache[ticker][1]

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    try:
        resp = requests.get(
            url, headers={"User-Agent": USER_AGENT}, params={"interval": "1d", "range": "1d"}, timeout=10,
        )
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as e:
        cached = _quote_cache.get(ticker)
        if cached is not None:
            age = time.time() - cached[0]
            logger.warning(
                "Market data fetch failed for %s (%s) -- serving cached quote %.0fs old instead of raising",
                ticker, e, age,
            )
            return cached[1]
        raise MarketDataUnavailableError(f"Could not fetch quote for {ticker}: {e}") from e

    chart = payload.get("chart") or {}
    result = chart.get("result")
    if not result:
        raise MarketDataUnavailableError(f"No quote data for {ticker}: {chart.get('error')}")

    meta = result[0].get("meta") or {}
    price = meta.get("regularMarketPrice")
    if price is None:
        raise MarketDataUnavailableError(f"No regularMarketPrice in quote response for {ticker}")

    prev_close = meta.get("chartPreviousClose")
    change = (price - prev_close) if prev_close is not None else None
    change_pct = (change / prev_close * 100) if change is not None and prev_close else None

    quote = {
        "ticker": ticker,
        "price": price,
        "previous_close": prev_close,
        "change": change,
        "change_pct": change_pct,
        "day_high": meta.get("regularMarketDayHigh"),
        "day_low": meta.get("regularMarketDayLow"),
        "volume": meta.get("regularMarketVolume"),
        "fifty_two_week_high": meta.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": meta.get("fiftyTwoWeekLow"),
        "currency": meta.get("currency"),
        "market_time": meta.get("regularMarketTime"),
        "cached_at": time.time(),
    }
    _quote_cache[ticker] = (time.time(), quote)
    return quote


def get_quotes(tickers: list[str]) -> dict[str, dict]:
    """Best-effort batch of get_quote() -- a single failed ticker (e.g. one
    SEC-known ticker Yahoo doesn't recognize) doesn't take down the whole
    batch; it's just omitted and logged, same "degrade, don't crash"
    posture as sec_client's stale-cache fallback."""
    quotes: dict[str, dict] = {}
    for ticker in tickers:
        try:
            quotes[ticker.upper()] = get_quote(ticker)
        except MarketDataUnavailableError as e:
            logger.warning("Skipping quote for %s in batch: %s", ticker, e)
    return quotes


HISTORY_RANGES = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "5y", "max"}
# Each range uses a coarse-enough interval that the point count stays small
# (a few hundred at most) -- this is for a dashboard sparkline/chart, not
# tick-level backtesting data.
_RANGE_INTERVAL = {
    "1d": "5m", "5d": "15m", "1mo": "1d", "3mo": "1d",
    "6mo": "1d", "1y": "1wk", "5y": "1wk", "max": "1mo",
}
# Historical ranges change slowly (today's partial bar aside) -- a much
# longer TTL than get_quote's 30s is appropriate, and keeps repeated chart
# opens from re-fetching the same months of data every time.
HISTORY_CACHE_TTL_SECONDS = 5 * 60

# (ticker, range) -> (cached_at, points)
_history_cache: dict[tuple[str, str], tuple[float, list[dict]]] = {}


def get_history(ticker: str, range_: str = "3mo") -> list[dict]:
    """Daily (or coarser) closing-price series for `ticker` over `range_`,
    for charting -- e.g. [{"date": "2026-01-02", "close": 184.3}, ...].
    Display only, same as get_quote (see module docstring)."""
    ticker = ticker.upper()
    if range_ not in HISTORY_RANGES:
        raise ValueError(f"range must be one of {sorted(HISTORY_RANGES)}, got {range_!r}")

    cache_key = (ticker, range_)
    cached = _history_cache.get(cache_key)
    if cached and (time.time() - cached[0]) < HISTORY_CACHE_TTL_SECONDS:
        return cached[1]

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    try:
        resp = requests.get(
            url, headers={"User-Agent": USER_AGENT},
            params={"interval": _RANGE_INTERVAL[range_], "range": range_}, timeout=10,
        )
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as e:
        if cached is not None:
            logger.warning("History fetch failed for %s/%s (%s) -- serving cached series instead", ticker, range_, e)
            return cached[1]
        raise MarketDataUnavailableError(f"Could not fetch history for {ticker}: {e}") from e

    chart = payload.get("chart") or {}
    result = chart.get("result")
    if not result:
        raise MarketDataUnavailableError(f"No history data for {ticker}: {chart.get('error')}")

    timestamps = result[0].get("timestamp") or []
    closes = ((result[0].get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    points = [
        {"date": time.strftime("%Y-%m-%d", time.gmtime(ts)), "close": round(close, 4)}
        for ts, close in zip(timestamps, closes)
        if close is not None
    ]
    _history_cache[cache_key] = (time.time(), points)
    return points
