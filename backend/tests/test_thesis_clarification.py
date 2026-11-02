"""Synthetic clarification fixtures; not Gold labels or live-model accuracy claims."""
import os
os.environ.setdefault('DATABASE_URL','sqlite://')
os.environ.setdefault('JWT_SECRET_KEY','natural-test-secret')
import unittest,json
from copy import deepcopy
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import app,db
from app.db.models import User,Reason,HiddenReason,ThesisVersion,ThesisClarification
from thesis_clarification import step,start,advance,get_draft,require_investigable,MAX_CALLS,MAX_ROUNDS
from natural_thesis import confirm_proposal,history
from thesis_evidence import investigate,compact_context
from test_natural_thesis import CLAIM,VERSION,response,call

Q={'key':'growth_scope','text':'What does growth mean to you for Amazon?','why':'Different businesses can grow differently.','options':[{'label':'Total revenue','explanation':'Money earned from sales before expenses.'},{'label':'AWS revenue','explanation':'Sales from Amazon’s cloud business.'}]}
CLEAR={**CLAIM,'scope':'Amazon total revenue','expectation':'Revenue increases YoY','checkable_question':'Is this quarter’s revenue above the same quarter last year?', 'timeframe':'Latest reported quarter','comparison_basis':'Same fiscal quarter last year','evidence_standard':'Consolidated reported revenue in both comparable quarters'}
def output(question=None,claims=None,missing=None,explanation=''):
 return response([call('clarification_turn',{'understood':'You expect growth.','explanation':explanation,'question':question,'claims':claims or [],'missing':missing or []})])
class ClarificationTests(unittest.TestCase):
 def test_vague_dynamic_question_no_retrieval(self):
  seen=[]
  def decide(messages):seen.append(json.loads(messages[0]['content']));return output(Q,missing=['scope'])
  with patch('thesis_evidence.FilingEvidence',side_effect=AssertionError('No retrieval')):
   state,p=step({},'AMZN','คิดว่าน่าจะเติบโตดี','th',decide=decide)
  self.assertEqual(state,'NEEDS_CLARIFICATION');self.assertEqual(p['question']['options'][1]['label'],'AWS revenue');self.assertEqual(seen[0]['company'],'AMZN')
 def test_clear_input_and_multiple_claims_no_unnecessary_question(self):
  for claims in [[CLEAR],[CLEAR,{**CLEAR,'claim_id':'C2','scope':'AWS revenue'}]]:
   state,p=step({},'AMZN','Quarterly revenue above the same quarter last year','en',decide=lambda _:output(claims=claims))
   self.assertEqual(state,'READY_FOR_CONFIRMATION');self.assertIsNone(p['question']);self.assertEqual(len(p['claims']),len(claims))
 def test_only_missing_detail_sent_next(self):
  p={'answers':[{'question':Q,'answer':'AWS revenue'}]}
  q={**Q,'key':'growth_period','text':'Which period should we compare?'}
  def decide(messages):
   data=json.loads(messages[0]['content']);self.assertEqual(data['answers'][0]['answer'],'AWS revenue');return output(q,missing=['timeframe'])
  state,p=step(p,'AMZN','Grow well','en',decide=decide)
  self.assertEqual(p['question']['key'],'growth_period');self.assertEqual(state,'NEEDS_CLARIFICATION')
 def test_repeated_question_and_invalid_output_never_ready(self):
  p={'answers':[{'question':Q,'answer':'Total revenue'}],'question':Q}
  for result in [output(Q,missing=['scope']),response([])]:
   state,after=step(p,'AMZN','Growth','en',decide=lambda _:result)
   self.assertEqual(state,'NEEDS_CLARIFICATION');self.assertIsNone(after['question']);self.assertIn('error',after)
 def test_unsure_explains_not_confirms(self):
  state,p=step({'question':Q},'AMZN','Growth','en',action='explain',decide=lambda _:output(claims=[CLEAR],explanation='Revenue means sales before costs.'))
  self.assertEqual(state,'NEEDS_CLARIFICATION');self.assertEqual(p['question'],Q);self.assertIn('before costs',p['explanation'])
 def test_no_full_investigation_before_clarification(self):
  v=deepcopy(VERSION);v['definition']['confirmed_interpretation']['claims'][0]['ambiguities']=['What is growth?']
  with patch('thesis_evidence.FilingEvidence',side_effect=AssertionError('Called retrieval too early')):
   with self.assertRaises(ValueError):investigate(v,'2025-06-01','2025-01-01','2025-03-31')
  v['definition']['confirmed_interpretation']['claims'][0]['user_clarification']='Still unsure'
  with self.assertRaises(ValueError):require_investigable(v['definition'])
 def test_clarity_independent_of_evidence_and_rule(self):
  self.assertEqual(require_investigable({'thesis_clarity':'CONFIRMED'}),'CONFIRMED')
  self.assertEqual(require_investigable({'thesis_clarity':'EXPLORATORY'}),'EXPLORATORY')
 def test_last_answer_can_complete_but_no_more_questions(self):
  answers=[{'question':{**Q,'key':str(i)},'answer':'Explicit answer'} for i in range(MAX_ROUNDS)]
  state,p=step({'answers':answers},'AMZN','Grow','en',decide=lambda _:output(claims=[CLEAR]))
  self.assertEqual(state,'READY_FOR_CONFIRMATION')
  state,p=step({'answers':answers},'AMZN','Grow','en',decide=lambda _:output({**Q,'key':'extra'},missing=['other']))
  self.assertEqual(state,'NEEDS_CLARIFICATION');self.assertTrue(p['limit_reached']);self.assertIsNone(p['question'])
 def test_over_budget_does_not_call_model(self):
  state,p=step({'attempts':MAX_CALLS+1},'AMZN','Grow','en',decide=lambda _:self.fail('Budget bypass'))
  self.assertTrue(p['limit_reached'])

class PersistenceTests(unittest.TestCase):
 def setUp(self):
  self.engine=create_engine('sqlite://',poolclass=StaticPool)
  for model in (User,Reason,HiddenReason,ThesisVersion,ThesisClarification):model.__table__.create(self.engine)
  self.sessions=sessionmaker(bind=self.engine);self.p=patch.object(db,'SessionLocal',self.sessions);self.p.start()
  self.d=start('ซื้อ Amazon เพราะคิดว่าน่าจะเติบโตดี','AMZN',1,'th')
 def tearDown(self):self.p.stop();self.engine.dispose()
 def move(self,d,action='retry',**kwargs):return advance(d['id'],1,d['revision'],action,**kwargs)
 def test_confirmation_history_ownership_revision_and_replay(self):
  with patch('agent.Planner.decide',return_value=output(Q,missing=['scope'])),patch.dict(os.environ,{'ANTHROPIC_API_KEY':'fixture'}):d=self.move(self.d)
  self.assertNotIn('confirmation_token',d)
  with self.assertRaises(ValueError):get_draft(d['id'],2)
  with self.assertRaises(ValueError):self.move(self.d)
  with patch('agent.Planner.decide',return_value=output(claims=[CLEAR])),patch.dict(os.environ,{'ANTHROPIC_API_KEY':'fixture'}):d=self.move(d,'answer',answer='Total revenue, this quarter versus the same quarter last year',question_key=Q['key'])
  saved=confirm_proposal(d['confirmation_token'],1);definition=saved['rule_definition']
  self.assertEqual(definition['thesis_clarity'],'CONFIRMED');self.assertEqual(definition['confirmed_scope'][0]['timeframe'],CLEAR['timeframe'])
  self.assertEqual(history(1,saved['reason_key'])[0]['original_text'],self.d['original_text'])
  self.assertEqual(len(definition['clarification_history']),1)
  with self.assertRaises(ValueError):confirm_proposal(d['confirmation_token'],1)
 def test_edit_invalidates_previous_confirmation_preview(self):
  with patch('agent.Planner.decide',side_effect=[output(Q,missing=['scope']),output(claims=[CLEAR])]),patch.dict(os.environ,{'ANTHROPIC_API_KEY':'fixture'}):
   d=self.move(self.d);d=self.move(d,'answer',answer='Explicit quarterly revenue expectation',question_key=Q['key'])
  old=d['confirmation_token'];d=self.move(d,'rewind',keep_answers=0)
  self.assertEqual(d['state'],'NEEDS_CLARIFICATION');self.assertEqual(d['answers'],[]);self.assertEqual(len(d['audit']),1)
  with self.assertRaises(ValueError):confirm_proposal(old,1)
 def test_exploration_explicit_no_model_and_keeps_original(self):
  with patch('agent.Planner.decide',side_effect=AssertionError('Exploration confirmation needs no LLM')):d=self.move(self.d,'explore')
  saved=confirm_proposal(d['confirmation_token'],1)
  self.assertEqual(saved['rule_definition']['thesis_clarity'],'EXPLORATORY')
  self.assertEqual(require_investigable(saved['rule_definition']),'EXPLORATORY')
 def test_failed_provider_attempts_bounded_and_answers_retained(self):
  with patch('agent.Planner.decide',side_effect=RuntimeError('Provider down')),patch.dict(os.environ,{'ANTHROPIC_API_KEY':'fixture'}):
   d=self.d
   for i in range(MAX_CALLS):
    with self.assertRaises(RuntimeError):self.move(d)
    d=get_draft(d['id'],1);self.assertEqual(d['attempts'],i+1)
   with self.assertRaises(ValueError):self.move(d)
  self.assertEqual(self.move(d,'explore')['state'],'EXPLORATORY')


class BudgetAndGroundingTests(unittest.TestCase):
 def test_compact_context_deduplicates_and_keeps_exact_quotes(self):
  class Source:
   registry={'e1':{'evidence_id':'e1','ticker':'AAPL','text':'Exact source quotation.'}}
   searches=[{'claim_id':'C1','purpose':'SUPPORT','query':'sales','evidence_ids':['e1']},{'claim_id':'C1','purpose':'CONTRADICTION','query':'risks','evidence_ids':['e1']}]
  messages=compact_context({'role':'user','content':'confirmed intent'},Source(),[],[],[],2)
  state=json.loads(messages[-1]['content'])
  self.assertEqual(len(state['available_excerpts']),1);self.assertEqual(state['available_excerpts'][0]['text'],'Exact source quotation.')
  self.assertEqual(len(state['searches']),2)
 def test_tool_attempts_are_bounded_even_for_many_invalid_calls(self):
  class Source:
   searches=[];registry={};catalog=[];future=False
  class Planner:
   def decide(self,messages):return response([call('nonexistent',{'claim_id':'C1'},str(i)) for i in range(100)])
  result=investigate(VERSION,'2025-06-01','2025-01-01','2025-03-31',planner_factory=lambda a,b:Planner(),evidence=Source())
  self.assertLessEqual(len(result['tool_calls']),24);self.assertFalse(result['what_we_know'])
  self.assertEqual(result['evidence_status'],'INSUFFICIENT');self.assertEqual(result['rule_status'],'NOT_EVALUATED')
  self.assertTrue(all(u['stage']=='planning' for u in result['stage_usage']))
 def test_unconfirmed_chat_cannot_reuse_historical_verdict(self):
  from natural_thesis import stored_evidence
  v=deepcopy(VERSION);v['definition']['confirmed_interpretation']['claims'][0]['ambiguities']=['Which business?']
  with patch('natural_thesis.resolve_version',return_value=v):r=stored_evidence(1,'old')
  self.assertEqual(r['thesis_clarity'],'NEEDS_CLARIFICATION');self.assertIsNone(r['investigation'])

class UnsurePersistenceTests(unittest.TestCase):
 setUp=PersistenceTests.setUp
 tearDown=PersistenceTests.tearDown
 move=PersistenceTests.move
 def test_unsure_free_text_saved_without_consuming_decision(self):
  with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'fixture'}),patch('agent.Planner.decide',side_effect=[output(Q,missing=['scope']),output(Q,missing=['scope'],explanation='Revenue means sales before costs.')]):
   d=self.move(self.d);d=self.move(d,'answer',answer='ยังไม่แน่ใจ อยากให้อธิบายก่อน',question_key=Q['key'])
  self.assertEqual(d['state'],'NEEDS_CLARIFICATION');self.assertEqual(d['answers'],[])
  self.assertEqual(len(d['help_requests']),1);self.assertEqual(d['question']['key'],Q['key'])

if __name__=='__main__':unittest.main()
