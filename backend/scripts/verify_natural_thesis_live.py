"""Bounded developer smoke; no app DB writes, no Gold labels, no auth token output."""
import os,json,sys
from pathlib import Path
from dotenv import dotenv_values
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'backend'))
key=dotenv_values(root/'.env').get('ANTHROPIC_API_KEY')
if key:os.environ['ANTHROPIC_API_KEY']=key
os.environ['DATABASE_URL']='sqlite://'
os.environ['JWT_SECRET_KEY']='developer-smoke-not-an-app-session'
import app
import requests
from natural_thesis import proposal
from thesis_evidence import investigate
out=root/'reports/natural_thesis_validation'
original='ซื้อหุ้น Apple เพราะเชื่อว่าธุรกิจ Services จะเติบโตต่อเนื่อง และช่วยรักษาความสามารถในการทำกำไรของบริษัท'
try:
    result=json.loads((out/'live-interpretation.json').read_text()) if '--reuse-interpretation' in sys.argv else proposal(original,'AAPL',0,'th')
    safe={k:v for k,v in result.items() if k!='confirmation_token'}
    safe['test_scope']='Developer live smoke; not user confirmation or Gold'
    (out/'live-interpretation.json').write_text(json.dumps(safe,ensure_ascii=False,indent=2))
    print('PASS live interpretation',json.dumps({'claims':len(result['interpretation']['claims']),'usage':result['usage']}),flush=True)
    # Developer test fixture only. Preserve ambiguity; do not invent a user clarification.
    version={'id':'developer-live-smoke','version_no':1,'company':'AAPL','original_text':original,
             'definition':{'confirmed_interpretation':result['interpretation']}}
    investigation=investigate(version,'2025-05-10','2024-03-01','2025-03-31')
    investigation['test_scope']='Developer live smoke; not a stored user-confirmed thesis or Gold'
    (out/'live-investigation.json').write_text(json.dumps(investigation,ensure_ascii=False,indent=2))
    status={'interpretation':'passed','investigation':'completed','rule_status':investigation['rule_status'],
            'evidence_status':investigation['evidence_status'],'tool_calls':len(investigation['tool_calls']),
            'usage':investigation['usage'],'estimated_cost_usd':investigation['estimated_cost_usd']}
    (out/'live-provider-status.json').write_text(json.dumps(status,indent=2))
    print(json.dumps(status),flush=True)
except requests.HTTPError as exc:
    try:error=exc.response.json().get('error',{});detail={'status':exc.response.status_code,'type':error.get('type'),'message':error.get('message')}
    except ValueError:detail={'status':exc.response.status_code,'type':'non-json-error'}
    (out/'live-provider-status.json').write_text(json.dumps(detail,indent=2))
    print(json.dumps(detail),flush=True);sys.exit(1)
except Exception as exc:
    print('FAILED',type(exc).__name__,str(exc)[:300],flush=True);sys.exit(1)
