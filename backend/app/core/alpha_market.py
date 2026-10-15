"""Alpha Vantage end-of-day prices; never used as SEC thesis evidence.

Shared Postgres cache and a UTC-day request budget survive Render restarts.
Only validated data is cached. Failed responses still consume request budget.
"""
import math
import os
import time
from datetime import datetime, timedelta, timezone
from threading import RLock

import requests
from sqlalchemy.dialects.postgresql import insert
from app.db.session import SessionLocal
from app.db.models import MarketDataCache, MarketDataUsage

_lock = RLock()
_retry_at = 0.0
CACHE_TTL = 86400
FUNCTIONS = {'daily': ('TIME_SERIES_DAILY', 'Time Series (Daily)'),
             'weekly': ('TIME_SERIES_WEEKLY', 'Weekly Time Series'),
             'monthly': ('TIME_SERIES_MONTHLY', 'Monthly Time Series')}
RANGES = {'5d', '1mo', '3mo', '6mo', '1y', '5y', 'max'}

class AlphaUnavailable(Exception):
    pass

class AlphaRangeUnavailable(ValueError):
    pass


def retry_after_seconds():
    return max(1, math.ceil(_retry_at - time.time()))


def _cached(key):
    with SessionLocal() as session:
        row = session.get(MarketDataCache, key)
        if row and time.time() - row.fetched_at < CACHE_TTL:
            return row.payload
    return None


def _reserve_request():
    # Advisory lock serializes the small budget reservation across instances.
    from sqlalchemy import text
    today = datetime.now(timezone.utc).date().isoformat()
    with SessionLocal.begin() as session:
        session.execute(text('SELECT pg_advisory_xact_lock(72819462)'))
        session.execute(insert(MarketDataUsage).values(day=today, requests=0).on_conflict_do_nothing())
        row = session.get(MarketDataUsage, today)
        if row.requests >= 25:
            raise AlphaUnavailable('Daily market data allowance reached. Cached data remains available.')
        row.requests += 1


def _save(key, payload):
    with SessionLocal.begin() as session:
        stmt = insert(MarketDataCache).values(key=key, payload=payload, fetched_at=time.time())
        session.execute(stmt.on_conflict_do_update(index_elements=['key'], set_={
            'payload': stmt.excluded.payload, 'fetched_at': stmt.excluded.fetched_at}))


def _parse(payload, ticker, period):
    if not isinstance(payload, dict): raise AlphaUnavailable('Invalid market data response.')
    meta = payload.get('Meta Data', {})
    if meta.get('2. Symbol', '').upper() != ticker:
        raise AlphaUnavailable('Market data symbol could not be verified.')
    series = payload.get(FUNCTIONS[period][1])
    if not isinstance(series, dict) or not series: raise AlphaUnavailable('No historical prices returned.')
    rows = []
    try:
        for date, bar in sorted(series.items()):
            parsed_date = datetime.strptime(date, '%Y-%m-%d').date()
            if parsed_date > datetime.now(timezone.utc).date(): raise ValueError()
            prices = {k: float(bar[v]) for k, v in [('close','4. close'),('high','2. high'),('low','3. low')]}
            volume = int(bar['5. volume'])
            if any(not math.isfinite(v) or v <= 0 for v in prices.values()) or volume < 0 or not prices['low'] <= prices['close'] <= prices['high']:
                raise ValueError()
            rows.append({'date': date, **prices, 'volume': volume})
    except (ValueError, TypeError, KeyError):
        raise AlphaUnavailable('Invalid historical price values.') from None
    return rows


def _series(ticker, period):
    global _retry_at
    key = f'alpha_vantage:{ticker}:{period}'
    with _lock:
        cached = _cached(key)
        if cached is not None: return cached
        api_key = os.environ.get('ALPHA_VANTAGE_API_KEY', '').strip()
        if not api_key: raise AlphaUnavailable('Alpha Vantage API key is not configured.')
        if time.time() < _retry_at: raise AlphaUnavailable('Market data provider is temporarily unavailable.')
        _reserve_request()
        params = {'function': FUNCTIONS[period][0], 'symbol': ticker, 'apikey': api_key}
        if period == 'daily': params['outputsize'] = 'compact'
        try:
            response = requests.get('https://www.alphavantage.co/query', params=params, timeout=(3, 15))
            if response.status_code == 429: _retry_at = time.time() + 86400
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict) and ('Information' in payload or 'Note' in payload):
                _retry_at = time.time() + 86400
                raise AlphaUnavailable('Provider allowance or subscription does not permit this request.')
            rows = _parse(payload, ticker, period)
        except (requests.RequestException, ValueError):
            # Never return/log the request URL: it contains the API key.
            _retry_at = max(_retry_at, time.time() + 60)
            raise AlphaUnavailable('Could not retrieve historical prices from Alpha Vantage.') from None
        except AlphaUnavailable:
            _retry_at = max(_retry_at, time.time() + 60)
            raise
        _save(key, rows)
        return rows


def get_history(ticker, range_):
    if range_ not in RANGES:
        raise AlphaRangeUnavailable('Intraday prices are not included. Select a daily or longer range.')
    period = 'daily' if range_ in {'5d','1mo','3mo'} else ('monthly' if range_ == 'max' else 'weekly')
    rows = _series(ticker, period)
    if range_ == '5d': rows = rows[-5:]
    elif range_ != 'max':
        days = {'1mo':31,'3mo':93,'6mo':186,'1y':366,'5y':1830}[range_]
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
        rows = [r for r in rows if r['date'] >= cutoff]
    if not rows: raise AlphaUnavailable('No prices are available for the selected period.')
    return [{'date': r['date'], 'close': r['close']} for r in rows]


def get_quote(ticker):
    rows = _series(ticker, 'daily')
    last = rows[-1]
    previous = rows[-2]['close'] if len(rows) > 1 else None
    change = last['close'] - previous if previous is not None else None
    return {'ticker': ticker, 'price': last['close'], 'previous_close': previous,
            'change': change, 'change_pct': change / previous * 100 if previous else None,
            'day_high': last['high'], 'day_low': last['low'], 'volume': last['volume'],
            'fifty_two_week_high': None, 'fifty_two_week_low': None,
            'currency': 'USD', 'market_time': None, 'cached_at': time.time(),
            'source': 'Alpha Vantage', 'price_type': 'daily_close', 'as_of': last['date']}
