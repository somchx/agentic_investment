import os
os.environ.setdefault('JWT_SECRET_KEY','alpha-tests-only')
os.environ.setdefault('DATABASE_URL','sqlite://')
import unittest
from unittest.mock import patch,Mock
from datetime import datetime,timezone
import app
import alpha_market as alpha

def fixture(symbol='AAPL',price='110'):
    return {'Meta Data':{'2. Symbol':symbol},'Time Series (Daily)':{
        '2025-01-02':{'2. high':'102','3. low':'98','4. close':'100','5. volume':'1000'},
        datetime.now(timezone.utc).date().isoformat():{'2. high':'112','3. low':'108','4. close':price,'5. volume':'2000'}}}

class AlphaTests(unittest.TestCase):
    def setUp(self):
        alpha._retry_at=0
        self.env=patch.dict(os.environ,{'ALPHA_VANTAGE_API_KEY':'test-secret','MARKET_DATA_PROVIDER':'alpha_vantage'})
        self.env.start()
    def tearDown(self):
        self.env.stop();alpha._retry_at=0
    def test_quote_is_daily_close_and_has_correct_previous_close(self):
        rows=alpha._parse(fixture(),'AAPL','daily')
        with patch.object(alpha,'_series',return_value=rows):q=alpha.get_quote('AAPL')
        self.assertEqual((q['price'],q['change'],q['change_pct']),(110,10,10))
        self.assertEqual(q['price_type'],'daily_close');self.assertEqual(q['as_of'],rows[-1]['date'])
        self.assertIsNone(q['fifty_two_week_high'])
    def test_wrong_symbol_nonfinite_and_negative_prices_rejected(self):
        for payload in (fixture('IBM'),fixture(price='NaN'),fixture(price='-1'),{'Information':'quota'}):
            with self.assertRaises(alpha.AlphaUnavailable):alpha._parse(payload,'AAPL','daily')
    def test_ranges_use_correct_series_and_intraday_is_not_substituted(self):
        with patch.object(alpha,'_series',return_value=alpha._parse(fixture(),'AAPL','daily')) as get:
            self.assertEqual(len(alpha.get_history('AAPL','1mo')),1);get.assert_called_with('AAPL','daily')
            alpha.get_history('AAPL','5y');get.assert_called_with('AAPL','weekly')
            alpha.get_history('AAPL','max');get.assert_called_with('AAPL','monthly')
            with self.assertRaises(alpha.AlphaRangeUnavailable):alpha.get_history('AAPL','1d')
    def test_shared_cache_bypasses_network_and_budget_even_during_cooldown(self):
        alpha._retry_at=10**12
        with patch.object(alpha,'_cached',return_value=alpha._parse(fixture(),'AAPL','daily')),patch.object(alpha,'_reserve_request') as reserve,patch.object(alpha.requests,'get') as get:
            self.assertEqual(alpha.get_quote('AAPL')['price'],110)
            self.assertEqual(len(alpha.get_history('AAPL','1mo')),1)
            reserve.assert_not_called();get.assert_not_called()
    def test_http200_quota_errors_are_not_cached_or_retried(self):
        r=Mock(status_code=200);r.json.return_value={'Information':'Daily allowance reached'}
        with patch.object(alpha,'_cached',return_value=None),patch.object(alpha,'_reserve_request') as reserve,patch.object(alpha,'_save') as save,patch.object(alpha.requests,'get',return_value=r) as get:
            for _ in range(2):
                with self.assertRaises(alpha.AlphaUnavailable):alpha.get_quote('AAPL')
            self.assertEqual(get.call_count,1);self.assertEqual(reserve.call_count,1);save.assert_not_called()
    def test_transport_errors_do_not_leak_api_key(self):
        import requests
        with patch.object(alpha,'_cached',return_value=None),patch.object(alpha,'_reserve_request'),patch.object(alpha.requests,'get',side_effect=requests.RequestException('URL?apikey=test-secret')):
            with self.assertRaises(alpha.AlphaUnavailable) as error:alpha.get_quote('AAPL')
            self.assertNotIn('test-secret',str(error.exception))
    def test_provider_selection_does_not_call_yahoo(self):
        import market_data
        with patch.object(alpha,'get_history',return_value=[{'date':'2026-01-01','close':100}]),patch.object(market_data,'_fetch_chart',side_effect=AssertionError('Yahoo called')):
            self.assertEqual(market_data.get_history('AAPL','1mo')[0]['close'],100)
            self.assertNotIn('1d',market_data.provider_config()['ranges'])
