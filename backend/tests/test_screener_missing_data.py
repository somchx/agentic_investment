"""Global screener rules skip missing evidence without comparing it to thresholds."""
import os
import unittest
from unittest.mock import patch
os.environ.setdefault('DATABASE_URL', 'sqlite://')
os.environ.setdefault('JWT_SECRET_KEY', 'screener-tests-only')
from app.api import reasons, screener
import tools
from models import Reason

class ScreenerMissingDataTests(unittest.TestCase):
    def test_missing_tag_never_reaches_comparison(self):
        reason = Reason('test', '', 'AccountsReceivableNetCurrent', '>', 0.1,
                        kind='yoy_growth', instant=True, is_custom=True)
        with patch.object(tools, 'get_company_facts', return_value={'cik': 1, 'facts': {}}), patch.object(tools, 'evaluate_yoy_growth') as evaluate:
            result = tools._evaluate_reason_obj('EMPTY', reason, None)
        self.assertEqual(result['error_code'], 'EVIDENCE_NOT_FOUND')
        evaluate.assert_not_called()

    def test_screen_keeps_valid_results_and_skips_missing(self):
        def check(ticker, key):
            if ticker == 'EMPTY':
                return {'error_code': 'EVIDENCE_NOT_FOUND', 'error': 'no facts'}
            return {'company': 'Has Data', 'reason': 'Growth', 'status': 'Supported', 'computed_value': 0.2, 'as_of': '2026-01-01'}
        with patch.object(screener, 'KNOWN_CIKS', {'EMPTY': '1', 'FULL': '2'}), patch.object(screener.db, 'get_reason_if_accessible', return_value={'ticker': None}), patch.object(screener, 'check_reason_status', side_effect=check):
            result = screener.api_screen(['global'], user_id=1)
        rows = {row['ticker']: row['by_reason']['global'] for row in result['companies']}
        self.assertEqual(rows['EMPTY']['status'], 'Not enough data')
        self.assertIsNone(rows['EMPTY']['computed_value'])
        self.assertEqual(rows['FULL']['computed_value'], 0.2)

    def test_create_saves_one_global_rule(self):
        body = reasons.ReasonIn(reason_key='custom_global_test', ticker=None, preview_ticker='FULL', metric='AccountsReceivableNetCurrent', comparison='>', threshold=0.1, kind='yoy_growth', description='Growth', instant=True)
        with patch.object(reasons.db, 'save_reason') as save, patch.object(reasons, 'check_reason_status', return_value={'status': 'Supported'}):
            result = reasons.api_create_reason(body, user_id=1)
        self.assertTrue(result['ok'])
        save.assert_called_once()
        self.assertIsNone(save.call_args.kwargs['ticker'])
