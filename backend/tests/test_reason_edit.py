import os
import unittest
from unittest.mock import patch
os.environ.setdefault('DATABASE_URL', 'sqlite://')
os.environ.setdefault('JWT_SECRET_KEY', 'reason-tests-only')
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException
from app.api.reasons import api_edit_reason, ReasonEditIn
from app.db.models import Reason, User, HiddenReason
import db
import tools

class EditReasonTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', poolclass=StaticPool)
        User.__table__.create(self.engine)
        Reason.__table__.create(self.engine)
        HiddenReason.__table__.create(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.patcher = patch.object(db, 'SessionLocal', self.sessions)
        self.patcher.start()
        with self.sessions() as session:
            session.add(Reason(reason_key='revenue_growth', ticker=None, metric='Revenue', comparison='>', threshold=.1, kind='yoy_growth', description='Revenue growth', denominator_metric='', instant=False, is_builtin=True))
            session.commit()

    def tearDown(self):
        self.patcher.stop()
        self.engine.dispose()

    def test_personal_edit_preserves_shared_rule_and_curated_extraction(self):
        edited = api_edit_reason('revenue_growth', ReasonEditIn(description='Growth over 25%', comparison='>=', threshold=.25), user_id=1)
        key = edited['reason_key']
        self.assertEqual(db.get_reason_by_key('revenue_growth')['threshold'], .1)
        self.assertEqual([r['reason_key'] for r in db.list_reasons(user_id=1)], [key])
        self.assertEqual([r['reason_key'] for r in db.list_reasons(user_id=2)], ['revenue_growth'])
        definition = tools.get_reason_def(key)
        self.assertFalse(definition.is_custom)
        self.assertEqual(definition.threshold, .25)
        self.assertFalse(db.get_reason_by_key(key)['is_custom'])
        self.assertIsNone(db.get_reason_if_accessible(key, 2))
        with self.assertRaises(HTTPException) as caught:
            api_edit_reason(key, ReasonEditIn(description='Hack', comparison='<', threshold=1), user_id=2)
        self.assertEqual(caught.exception.status_code, 404)
        api_edit_reason(key, ReasonEditIn(description='Over 30%', comparison='>', threshold=.3), user_id=1)
        self.assertEqual(len(db.list_reasons(user_id=1)), 1)
        self.assertEqual(tools.get_reason_def(key).threshold, .3)

    def test_custom_rule_keeps_identity_and_raw_tag_extraction(self):
        db.save_reason('custom',1,None,'AccountsReceivableNetCurrent','>',.1,'yoy_growth','Original',instant=True)
        result = api_edit_reason('custom', ReasonEditIn(description='Updated', comparison='<', threshold=.2), user_id=1)
        self.assertEqual(result['reason_key'], 'custom')
        self.assertTrue(tools.get_reason_def('custom').is_custom)
        self.assertEqual(db.get_reason_by_key('custom')['description'], 'Updated')

    def test_delete_shared_rule_is_personal_and_preserves_definition(self):
        db.delete_reason('revenue_growth', 1)
        self.assertEqual(db.list_reasons(user_id=1), [])
        self.assertEqual(len(db.list_reasons(user_id=2)), 1)
        self.assertIsNotNone(db.get_reason_by_key('revenue_growth'))
        db.delete_reason('revenue_growth', 1)

    def test_delete_personal_version_does_not_restore_shared_rule(self):
        result = api_edit_reason('revenue_growth', ReasonEditIn(description='Personal', comparison='>', threshold=.2), user_id=1)
        key = result['reason_key']
        with self.assertRaises(ValueError):
            db.delete_reason(key, 2)
        db.delete_reason(key, 1)
        self.assertEqual(db.list_reasons(user_id=1), [])
        self.assertEqual(len(db.list_reasons(user_id=2)), 1)
        self.assertEqual(tools.get_reason_def(key).threshold, .2)
