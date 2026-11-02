"""Isolated test server: real HTTP/DB workflow, synthetic LLM/SEC evidence. Not research data."""
import os,json
assert '_test_' in os.environ['DATABASE_URL']
from thesis_browser_fixture import app
import agent,thesis_evidence
from unittest.mock import patch
CLAIM={'claim_id':'C1','expectation':'Services เติบโต','checkable_question':'รายได้ Services เพิ่มขึ้นหรือไม่?',
 'evidence_queries':['Services sales'],'ambiguities':['เติบโตต่อเนื่องหมายถึงกี่งวด?'],'limitations':['รายได้เพิ่มไม่พิสูจน์สาเหตุของกำไร']}
TEXT='Services net sales increased during the quarter. Higher costs and competition may pressure future margins.'
thesis_evidence.get_submissions=lambda ticker:{'cik':'0000320193','filings':{'recent':{'form':['10-Q'],'accessionNumber':['0000320193-25-000001'],'reportDate':['2025-03-31'],'filingDate':['2025-05-01'],'primaryDocument':['apple.htm']}}}
thesis_evidence.get_document_text=lambda *args:TEXT

def block(name,args,ident='fixture'):
 return {'content':[{'type':'tool_use','name':name,'id':ident,'input':args}],'usage':{'input_tokens':10,'output_tokens':10}}
def decide(self,messages):
 name=self.tools[0]['name']
 if name=='interpret_thesis':return block(name,{'claims':[CLAIM]})
 if name=='verify_evidence':return block(name,{'entails_statement':True,'relevant_to_claim':True,'period_matches':True,'addresses_full_claim':True,'role':'SUPPORTING','reason':'Synthetic browser verifier'})
 turns=sum(1 for m in messages if m['role']=='assistant')
 if turns==0:return block('search_filings',{'claim_id':'C1','query':'Services sales','purpose':'SUPPORT'})
 if turns==1:
  content=json.loads(messages[-1]['content'][0]['content']);eid=content['excerpts'][0]['evidence_id']
  return block('assess_observation',{'claim_id':'C1','evidence_id':eid,'quote':'Services net sales increased during the quarter.','statement':'Services sales increased (synthetic test).','proposed_role':'SUPPORTING','fact_or_inference':'FACT'})
 if turns==2:return block('search_filings',{'claim_id':'C1','query':'Services competition costs','purpose':'CONTRADICTION'})
 return block('finish_investigation',{})
agent.Planner.decide=decide
os.environ['ANTHROPIC_API_KEY']='isolated-fixture-no-network'
