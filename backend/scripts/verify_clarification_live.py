"""Paid live-model smoke; explicit synthetic tester intents, no user's thesis or Gold mutated."""
import sys,json,os,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env');load_dotenv(ROOT/'backend/.env')
import app
from thesis_clarification import step
from thesis_evidence import investigate
out=ROOT/'reports/clarification_validation';out.mkdir(exist_ok=True)
examples=[('AMZN','ซื้อ Amazon เพราะคิดว่าน่าจะเติบโตดี'),('AAPL','ติดตามว่ารายได้ Services ในไตรมาสล่าสุดเพิ่มจากไตรมาสเดียวกันของปีก่อนหรือไม่ ใช้รายได้ Services ที่บริษัทเปิดเผยใน 10-Q/10-K เป็นหลักฐาน ไม่ต้องกำหนดเปอร์เซ็นต์'),('MSFT','ติดตามว่ารายได้ Azure และรายได้รวมของ Microsoft ในไตรมาสล่าสุดเพิ่มขึ้นจากไตรมาสเดียวกันปีก่อนหรือไม่ ตรวจจากรายได้หรืออัตราการเติบโตที่บริษัทเปิดเผยในงบ ไม่ต้องกำหนดเปอร์เซ็นต์ขั้นต่ำ')]
results=[]
for ticker,original in examples:
 state,p=step({},ticker,original,'th',action='retry');results.append({'ticker':ticker,'original':original,'state':state,**p})
 print(ticker,state,'usage',p.get('metrics'),flush=True)
(out/'live-clarifications.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
# Tester defines this specific bounded claim; no real investor decision is created.
claim={'claim_id':'C1','expectation':'Apple Services net sales rose in fiscal Q2 2025 versus fiscal Q2 2024','checkable_question':'Did Services net sales increase in fiscal Q2 2025 versus fiscal Q2 2024?', 'evidence_queries':['Services net sales March 2025 2024'],'ambiguities':[],'limitations':['Does not establish future growth or profitability causation']}
v={'id':'developer-smoke-not-gold','version_no':1,'company':'AAPL','original_text':claim['expectation'],'definition':{'thesis_clarity':'CONFIRMED','confirmed_interpretation':{'claims':[claim]}}}
for strategy in ('transcript','compact'):
 r=investigate(v,'2025-05-15','2025-01-01','2025-03-31',language='th',context_strategy=strategy)
 (out/f'live-investigation-{strategy}.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
 print(strategy,r['usage'],r['evidence_status'],r['elapsed_seconds'],flush=True)
