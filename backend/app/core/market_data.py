"""Real-time-ish market price data -- the "Market Data" tool PROPOSAL.md
section 5 already anticipated as a Phase 1 (Optional) component ("ราคาหุ้น,
Volume -- ใช้ประกอบถ้าจำเป็น"). Distinct from sec_client.py's SEC EDGAR
data in both source and purpose:

- Source: Alpha Vantage when configured (daily closing prices, shared 24h cache).
  The optional legacy source is Yahoo Finance's public chart endpoint -- free, no API key, no
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

from functools import wraps
from threading import RLock
from email.utils import parsedate_to_datetime
import os
import math
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


# One shared gate across quotes and history: a rejected request must not cause
# all 15 symbols and concurrent browser requests to immediately retry Yahoo.
_provider_lock = RLock()
_provider_retry_at = 0.0


def _serialized(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        with _provider_lock:
            return fn(*args, **kwargs)
    return wrapped


def provider_name():
    return os.environ.get("MARKET_DATA_PROVIDER", "alpha_vantage" if os.environ.get("ALPHA_VANTAGE_API_KEY") else "yahoo")


def provider_config():
    alpha = provider_name() == "alpha_vantage"
    return {"provider": "Alpha Vantage" if alpha else "Yahoo Finance",
            "price_type": "daily_close" if alpha else "market_price",
            "ranges": sorted(HISTORY_RANGES - {"1d"} if alpha else HISTORY_RANGES),
            "configured": bool(os.environ.get("ALPHA_VANTAGE_API_KEY")) if alpha else True}


def _alpha_call(method, *args):
    import alpha_market
    try:
        return getattr(alpha_market, method)(*args)
    except alpha_market.AlphaUnavailable as exc:
        raise MarketDataUnavailableError(str(exc)) from None


def retry_after_seconds() -> int:
    if provider_name() == "alpha_vantage":
        import alpha_market
        return alpha_market.retry_after_seconds()
    return max(1, math.ceil(_provider_retry_at - time.time()))


def _fetch_chart(ticker: str, params: dict) -> dict:
    global _provider_retry_at
    if time.time() < _provider_retry_at:
        raise MarketDataUnavailableError("Price provider is temporarily unavailable; retry later.")
    try:
        resp = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
            headers={"User-Agent": USER_AGENT}, params=params, timeout=(3, 5),
        )
        if resp.status_code == 429:
            delay = 300.0
            raw = resp.headers.get("Retry-After", "")
            try:
                delay = max(delay, float(raw))
            except ValueError:
                try:
                    delay = max(delay, parsedate_to_datetime(raw).timestamp() - time.time())
                except (ValueError, TypeError, OverflowError):
                    pass
            _provider_retry_at = time.time() + delay
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, dict) or not (payload.get("chart") or {}).get("result"):
            raise ValueError("No chart data")
        return payload
    except (requests.RequestException, ValueError) as exc:
        _provider_retry_at = max(_provider_retry_at, time.time() + 30)
        logger.warning("Market provider unavailable (%s); backing off", type(exc).__name__)
        raise MarketDataUnavailableError("Price provider is temporarily unavailable; retry later.") from exc


def _is_fresh(ticker: str) -> bool:
    cached = _quote_cache.get(ticker)
    return cached is not None and (time.time() - cached[0]) < QUOTE_CACHE_TTL_SECONDS


@_serialized
def get_quote(ticker: str) -> dict:
    """Current price snapshot for `ticker`. Cached for
    QUOTE_CACHE_TTL_SECONDS so a page polling every few seconds doesn't
    hammer the upstream API on every request.
    """
    ticker = ticker.upper()
    if provider_name() == "alpha_vantage":
        return _alpha_call("get_quote", ticker)
    if _is_fresh(ticker):
        return _quote_cache[ticker][1]

    payload = _fetch_chart(ticker, {"interval": "1d", "range": "1d"})

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


@_serialized
def get_history(ticker: str, range_: str = "3mo") -> list[dict]:
    """Daily (or coarser) closing-price series for `ticker` over `range_`,
    for charting -- e.g. [{"date": "2026-01-02", "close": 184.3}, ...].
    Display only, same as get_quote (see module docstring)."""
    ticker = ticker.upper()
    if range_ not in HISTORY_RANGES:
        raise ValueError(f"range must be one of {sorted(HISTORY_RANGES)}, got {range_!r}")

    if provider_name() == "alpha_vantage":
        return _alpha_call("get_history", ticker, range_)

    cache_key = (ticker, range_)
    cached = _history_cache.get(cache_key)
    if cached and (time.time() - cached[0]) < HISTORY_CACHE_TTL_SECONDS:
        return cached[1]

    payload = _fetch_chart(ticker, {"interval": _RANGE_INTERVAL[range_], "range": range_})

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
