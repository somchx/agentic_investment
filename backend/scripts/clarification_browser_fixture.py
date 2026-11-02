"""Synthetic LLM and SEC for isolated UI tests; never use with production DB."""
from natural_browser_fixture import app,block,TEXT
import agent,json,os,time
from test_thesis_clarification import Q,CLEAR

def decide(self,messages):
 name=self.tools[0]['name']
 if name=='clarification_turn':
  data=json.loads(messages[0]['content']);answers=data['answers']
  if answers:time.sleep(float(os.environ.get('CLARIFICATION_FIXTURE_DELAY','0')))
  if data['action']=='explain':return block(name,{'understood':'ยังไม่ได้เลือก','explanation':'รายได้คือเงินจากการขายก่อนหักต้นทุน เช่น ขายได้ 100 บาท ยังไม่ได้หมายถึงกำไร 100 บาท','missing':['scope'],'question':Q,'claims':[]})
  if not answers:return block(name,{'understood':'คุณคาดหวังให้บริษัทเติบโต','missing':['scope'],'question':Q,'claims':[]})
  return block(name,{'understood':'ติดตามรายได้รายไตรมาสเทียบไตรมาสเดียวกันปีก่อน','missing':[],'question':None,'claims':[{**CLEAR,'expectation':'รายได้เพิ่มจากไตรมาสเดียวกันของปีก่อน'}]})
 if name=='verify_evidence':return block(name,{'entails_statement':True,'relevant_to_claim':True,'period_matches':True,'addresses_full_claim':False,'role':'SUPPORTING','reason':'Synthetic browser verifier: partial claim only'})
 self.fixture_turn=getattr(self,'fixture_turn',0)+1
 if self.fixture_turn==1:return block('search_filings',{'claim_id':'C1','query':'Services sales','purpose':'SUPPORT'})
 if self.fixture_turn==2:
  state=json.loads(messages[-1]['content']);eid=state['available_excerpts'][0]['evidence_id']
  return block('assess_observation',{'claim_id':'C1','evidence_id':eid,'quote':'Services net sales increased during the quarter.','statement':'รายได้ Services เพิ่มขึ้นในไตรมาสนี้ (ข้อมูลสมมติสำหรับทดสอบ UI)','proposed_role':'SUPPORTING','fact_or_inference':'FACT'})
 if self.fixture_turn==3:return block('search_filings',{'claim_id':'C1','query':'Services costs competition','purpose':'CONTRADICTION'})
 return block('finish_investigation',{})
agent.Planner.decide=decide
