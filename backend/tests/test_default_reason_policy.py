"""Offline checks for default-only authoring; historical engines remain supported."""
import os
os.environ.setdefault('DATABASE_URL','sqlite://')
os.environ.setdefault('JWT_SECRET_KEY','test-default-policy-secret')
import unittest
from unittest.mock import patch
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from app.api import reasons,positions,theses
from app.api.reason_policy import DEFAULT_REASON_KEYS
from app.security import current_user_id
from tools import REASON_DEFS

class DefaultReasonPolicyTests(unittest.TestCase):
    def setUp(self):
        app=FastAPI();app.include_router(reasons.router);app.include_router(theses.router)
        app.dependency_overrides[current_user_id]=lambda:1
        self.client=TestClient(app)

    def test_authoring_blocked_before_llm_or_write(self):
        for method,path in [('post','/api/reasons'),('patch','/api/reasons/revenue_growth'),('delete','/api/reasons/revenue_growth'),('post','/api/theses/interpret'),('post','/api/theses/confirm'),('post','/api/theses/clarifications'),('post','/api/theses/clarifications/old-draft')]:
            with self.subTest(path=path,method=method):
                self.assertEqual(getattr(self.client,method)(path).status_code,403)

    def test_catalog_only_defaults(self):
        rows=[{'reason_key':k} for k in [*DEFAULT_REASON_KEYS,'old_custom']]
        with patch.object(reasons.db,'list_reasons',return_value=rows) as listing:
            self.assertEqual([r['reason_key'] for r in self.client.get('/api/reasons?ticker=AMZN').json()],list(DEFAULT_REASON_KEYS))
            listing.assert_called_once_with()

    def test_thresholds_unchanged(self):
        self.assertEqual([(REASON_DEFS[k].comparison,REASON_DEFS[k].threshold) for k in DEFAULT_REASON_KEYS],[('>',.1),('>=',.2),('<',.15)])

    def test_purchase_rejects_custom(self):
        for extra in [{'thesis':'My own reason'},{'reason_keys':['old_custom']}]:
            body=positions.PositionIn(ticker='AAPL',quantity=1,purchase_price=100,purchase_date='2026-10-30',**extra)
            with patch.object(positions,'is_supported_ticker',return_value=True),patch.object(positions,'_freeze_reason') as freeze:
                with self.assertRaises(HTTPException) as exc:positions.record_position(body,user_id=1)
                self.assertEqual(exc.exception.status_code,400);freeze.assert_not_called()

    def test_purchase_defaults_frozen(self):
        body=positions.PositionIn(ticker='AAPL',quantity=1,purchase_price=100,purchase_date='2026-10-30')
        with patch.object(positions,'is_supported_ticker',return_value=True),patch.object(positions,'_freeze_reason',return_value={'frozen':True}) as freeze,patch.object(positions.db,'record_purchase',return_value=5) as save:
            result=positions.record_position(body,user_id=1)
            self.assertEqual([r['reason_key'] for r in result['reasons']],list(DEFAULT_REASON_KEYS))
            self.assertEqual(freeze.call_count,3)
            self.assertIsNone(save.call_args.kwargs['thesis'])
