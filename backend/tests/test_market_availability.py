"""No network: verify rate limiting, concurrent requests and fast company listing."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

os.environ.setdefault('JWT_SECRET_KEY', 'market-tests-only')
os.environ.setdefault('DATABASE_URL', 'sqlite://')
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api import companies, market
from app.security import current_user_id
import market_data as data
import requests

class MarketAvailabilityTests(unittest.TestCase):
    def setUp(self):
        data._quote_cache.clear()
        data._history_cache.clear()
        data._provider_retry_at = 0
        self.app = FastAPI()
        self.app.include_router(companies.router)
        self.app.include_router(market.router)
        self.app.dependency_overrides[current_user_id] = lambda: 1
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        data._provider_retry_at = 0
        data._quote_cache.clear()
        data._history_cache.clear()

    def limited(self, retry='600'):
        response = Mock(status_code=429, headers={'Retry-After': retry})
        response.raise_for_status.side_effect = requests.HTTPError('429')
        return response

    def success(self):
        response = Mock(status_code=200)
        response.json.return_value = {'chart': {'result': [{'meta': {
            'regularMarketPrice': 125, 'chartPreviousClose': 100,
        }, 'timestamp': [1767225600], 'indicators': {'quote': [{'close': [125]}]}}]}}
        return response

    def test_companies_never_calls_network(self):
        with patch('requests.get', side_effect=AssertionError('unexpected network')):
            r = self.client.get('/api/companies')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 15)
        self.assertTrue(all(c['name'] != c['ticker'] for c in r.json()))

    def test_429_blocks_all_symbols_and_history_until_retry_after(self):
        with patch.object(data.time, 'time', return_value=1000), patch.object(data.requests, 'get', return_value=self.limited()) as get:
            r = self.client.get('/api/market/history/AAPL?range=1mo')
            self.assertEqual(r.status_code, 503)
            self.assertEqual(r.headers['Retry-After'], '600')
            self.assertNotIn('https://', r.json()['detail'])
            self.assertEqual(data.get_quotes(['MSFT', 'NVDA', 'AAPL']), {})
            self.assertEqual(get.call_count, 1)
        with patch.object(data.time, 'time', return_value=1601), patch.object(data.requests, 'get', return_value=self.success()) as get:
            self.assertEqual(data.get_history('AAPL','1mo')[0]['close'], 125)
            self.assertEqual(get.call_count, 1)

    def test_concurrent_requests_are_coalesced_and_quotes_cached(self):
        with patch.object(data.requests, 'get', return_value=self.success()) as get:
            with ThreadPoolExecutor(max_workers=8) as pool:
                quotes = list(pool.map(data.get_quote, ['AAPL'] * 8))
            self.assertEqual(get.call_count, 1)
            self.assertEqual(quotes[0]['price'], 125)
            self.assertEqual(quotes[0]['change'], 25)

    def test_timeouts_and_malformed_json_back_off_without_fake_prices(self):
        for failure in (requests.Timeout(), ValueError('invalid JSON')):
            data._provider_retry_at = 0
            with patch.object(data.requests, 'get', side_effect=failure) as get:
                with self.assertRaises(data.MarketDataUnavailableError): data.get_quote('AAPL')
                with self.assertRaises(data.MarketDataUnavailableError): data.get_history('MSFT')
                self.assertEqual(get.call_count, 1)

    def test_expired_quote_is_not_presented_as_current_during_outage(self):
        with patch.object(data.time, 'time', return_value=1000):
            data._quote_cache['AAPL'] = (900, {'price': 1})
            with patch.object(data.requests, 'get', return_value=self.limited()):
                with self.assertRaises(data.MarketDataUnavailableError): data.get_quote('AAPL')

    def test_invalid_symbols_and_ranges_never_call_provider(self):
        with patch.object(data.requests, 'get') as get:
            self.assertEqual(self.client.get('/api/market/quotes?tickers=UNKNOWN').status_code,400)
            self.assertEqual(self.client.get('/api/market/history/AAPL?range=bad').status_code,400)
            get.assert_not_called()

if __name__ == '__main__': unittest.main()
