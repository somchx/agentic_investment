"""Regression for a fully answered revenue flow stuck asking which latest quarter."""
import unittest
from unittest.mock import patch
import app
from clarification_answers import explicit_growth_preview,relative_period
from thesis_clarification import step

def answered(value,explanation=''):
 return {'question':{'key':value,'text':value,'options':[{'label':value,'explanation':explanation}]},'answer':value}
def payload():
 return {'answers':[answered('รายได้รวมทั้งหมด'),answered('ไตรมาสถัดไป 1 ไตรมาส'),answered('ไตรมาสก่อนหน้าทันที (QoQ)'),answered('เติบโตปานกลาง 5-10%'),answered('ไตรมาสล่าสุดที่เผยแพร่แล้ว'),answered('ไตรมาสล่าสุดที่ Amazon เพิ่งประกาศไป','ไตรมาสที่เปิดเผยล่าสุด ณ เวลาที่ตัดสินใจลงทุน')], 'attempts':9,'limit_reached':True,'error':'old error'}
class ExplicitAnswersTests(unittest.TestCase):
 def test_complete_saved_answers_preview_without_model_or_more_budget(self):
  state,p=step(payload(),'AMZN','คิดว่าน่าจะเติบโตดี','th',decide=lambda _:self.fail('Must not spend or ask again'))
  self.assertEqual(state,'READY_FOR_CONFIRMATION');self.assertFalse(p['limit_reached']);self.assertNotIn('error',p)
  c=p['claims'][0];self.assertEqual(c['expectation'],'เติบโตปานกลาง 5-10%');self.assertIn('QoQ',c['comparison_basis'])
  self.assertIn('เวลาที่ตัดสินใจลงทุน',c['timeframe']);self.assertNotIn('Q4 2024',c['timeframe'])
  self.assertEqual(p['answers'],payload()['answers']);self.assertEqual(p['attempts'],9)
 def test_ready_after_fifth_answer_before_repeated_latest_question(self):
  p=payload();p['answers']=p['answers'][:5]
  self.assertIsNotNone(explicit_growth_preview(p,'AMZN'))
 def test_relative_periods_are_definitions_not_missing_dates(self):
  for a in ['ไตรมาสล่าสุดที่เผยแพร่แล้ว','ไตรมาสล่าสุดที่ Amazon เพิ่งประกาศไป','latest reported quarter']:
   self.assertTrue(relative_period(a))
  self.assertFalse(relative_period('ไม่แน่ใจ'))
 def test_missing_expectation_is_never_invented(self):
  p=payload();p['answers'].pop(3)
  self.assertIsNone(explicit_growth_preview(p,'AMZN'))
 def test_additional_business_claim_not_dropped(self):
  self.assertIsNone(explicit_growth_preview(payload(),'AMZN','รายได้และกำไรเพิ่มขึ้น'))
  p=payload();p['answers'].append(answered('AWS ต้องช่วยกำไร'))
  self.assertIsNone(explicit_growth_preview(p,'AMZN'))
 def test_conflicting_comparison_not_silently_overridden(self):
  p=payload();p['answers'][3]=answered('รายได้เพิ่มขึ้นจากปีก่อน')
  self.assertIsNone(explicit_growth_preview(p,'AMZN'))
 def test_future_period_not_changed_into_reported_data(self):
  p=payload();p['answers']=p['answers'][:4]
  self.assertEqual(explicit_growth_preview(p,'AMZN')['claims'][0]['timeframe'],'ไตรมาสถัดไป 1 ไตรมาส')
class RecoveryPersistenceTests(unittest.TestCase):
 def test_exhausted_saved_draft_recovers_without_resetting_answers_or_auto_confirming(self):
  from test_thesis_clarification import PersistenceTests
  from thesis_clarification import advance,get_draft
  from app.db.models import ThesisClarification,ThesisVersion
  from sqlalchemy import select,func
  fixture=PersistenceTests();fixture.setUp()
  try:
   with fixture.sessions() as session:
    row=session.get(ThesisClarification,fixture.d['id']);row.payload=payload();row.state='NEEDS_CLARIFICATION';session.commit()
   with patch('agent.Planner.decide',side_effect=AssertionError('No additional paid call')):
    d=advance(fixture.d['id'],1,0,'retry')
   self.assertEqual(d['state'],'READY_FOR_CONFIRMATION');self.assertIn('confirmation_token',d)
   self.assertEqual(d['answers'],payload()['answers']);self.assertEqual(d['attempts'],9)
   with fixture.sessions() as session:self.assertEqual(session.scalar(select(func.count()).select_from(ThesisVersion)),0)
  finally:fixture.tearDown()

if __name__=='__main__':unittest.main()
