"""Real PostgreSQL + HTTP, deterministic fake model/SEC. Requires a fresh *_test_* DB."""
import os,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
assert '_test_' in os.environ['DATABASE_URL'].rsplit('/',1)[-1]
assert os.environ['DATABASE_URL']==os.environ['DATABASE_URL_UNPOOLED']
from sqlalchemy import create_engine,text
from alembic.config import Config
from alembic import command
cfg=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'));cfg.set_main_option('script_location',str(Path(__file__).resolve().parents[1]/'alembic'))
command.upgrade(cfg,'e5f7a9b1c3d5')
engine=create_engine(os.environ['DATABASE_URL'])
with engine.begin() as c:
 uid=c.execute(text("INSERT INTO users(email,password_hash,created_at,full_name,token_version) VALUES ('legacy-natural-migration@example.com','not-a-login',now(),'Legacy migration',0) RETURNING id")).scalar()
 c.execute(text("INSERT INTO reasons(reason_key,user_id,metric,comparison,threshold,kind,denominator_metric,description,instant,is_builtin,created_at) VALUES ('legacy_numeric',:uid,'Revenue','>',.1,'yoy_growth','','Legacy numeric',false,false,now())"),{'uid':uid})
 snapshot={'metric':'Revenue','comparison':'>','threshold':.1,'kind':'yoy_growth','description':'Original snapshot'}
 c.execute(text("INSERT INTO purchases(user_id,ticker,quantity,purchase_price,purchase_date,reason_key,reason_snapshot_json,created_at) VALUES (:uid,'AAPL',1,100,'2025-06-01','legacy_numeric',CAST(:snap AS jsonb),now())"),{'uid':uid,'snap':json.dumps(snapshot)})
 before=c.execute(text('SELECT count(*) FROM reasons')).scalar()
command.upgrade(cfg,'head')
with engine.connect() as c:
 assert c.execute(text('SELECT count(*) FROM reasons')).scalar()==before
 assert c.execute(text("SELECT threshold FROM reasons WHERE reason_key='legacy_numeric'")).scalar()==.1
 assert c.execute(text("SELECT reason_snapshot_json FROM purchases WHERE reason_key='legacy_numeric'")).scalar()==snapshot
command.downgrade(cfg,'e5f7a9b1c3d5');command.upgrade(cfg,'head')
print('PASS migration upgrade/downgrade/re-upgrade without altering existing reasons')
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from test_natural_thesis import CLAIM,response,call,token,VERSION,EvidenceTests
from app.api import theses
from natural_thesis import proposal
from copy import deepcopy
with TestClient(app) as client:
 r=client.post('/api/auth/register',json={'email':'natural-http@example.com','password':'NaturalTest!123','full_name':'Natural HTTP test'});assert r.status_code==200,r.text
 uid=r.json()['user']['id'];client.headers['Authorization']='Bearer '+r.json()['access_token']
 with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'test'}),patch('agent.Planner.decide',return_value=response([call('interpret_thesis',{'claims':[CLAIM]})])):
  r=client.post('/api/theses/interpret',json={'ticker':'AAPL','original_text':'Apple Services will grow and preserve profitability.'});assert r.status_code==200,r.text
 signed=r.json()['confirmation_token']
 r=client.post('/api/theses/confirm',json={'confirmation_token':signed,'confirmed':False});assert r.status_code==400
 r=client.post('/api/theses/confirm',json={'confirmation_token':signed,'confirmed':True});assert r.status_code==200,r.text
 key=r.json()['reason_key'];v1=r.json()['rule_definition']['thesis_version_id']
 r=client.post('/api/positions',json={'ticker':'AAPL','quantity':1,'purchase_price':100,'purchase_date':'2025-06-01','reason_keys':[key]});assert r.status_code==200,r.text
 purchased=client.get('/api/positions').json()[0];snapshot=purchased['reasons'][0]['reason_snapshot'];pid=purchased['id']
 assert snapshot['rule_status_at_purchase']=='NOT_EVALUATED'
 r=client.get(f'/api/positions/{pid}/revalidation');assert r.status_code==200,r.text
 r=client.get('/api/screen',params={'reason_key':key});assert r.status_code==200,r.text
 assert all(c['by_reason'][key].get('rule_status')!='SATISFIED' for c in r.json()['companies'])
 r=client.post('/api/theses/confirm',json={'confirmation_token':token(uid,original='New Services business assumption for later purchases.'),'confirmed':True,'reason_key':key,'expected_version_id':v1});assert r.status_code==200,r.text
 v2=r.json()['rule_definition']['thesis_version_id'];assert v1!=v2
 assert client.get('/api/positions').json()[0]['reasons'][0]['reason_snapshot']==snapshot
 assert len(client.get(f'/api/theses/{key}/versions').json())==2
 # Real workflow was unit tested with adaptive fake planner; API persistence fixture keeps immutable result identity.
 def fake_investigate(version,asof,start,end,**kwargs):
  return {'thesis_version_id':version['id'],'version_no':version['version_no'],'rule_status':'NOT_EVALUATED','evidence_status':'INSUFFICIENT','evaluation_date':asof,'claims':[],'what_we_know':[],'what_is_uncertain':[],'what_to_investigate_next':[]}
 with patch.object(theses,'investigate',side_effect=fake_investigate):
  body={'evaluation_date':'2025-06-01','period_start':'2025-01-01','period_end':'2025-03-31','purchase_id':pid,'acknowledge_cost':True}
  r=client.post(f'/api/theses/{key}/investigate',json=body);assert r.status_code==200,r.text;assert r.json()['thesis_version_id']==v1
  body['evaluation_date']='2025-09-01';r=client.post(f'/api/theses/{key}/investigate',json=body);assert r.status_code==200
  results=client.get(f'/api/theses/{key}/investigations',params={'purchase_id':pid}).json();assert len(results)==2
  assert all(r['thesis_version_id']==v1 for r in results)
 r=client.post('/api/auth/register',json={'email':'other-natural@example.com','password':'NaturalTest!123','full_name':'Other test'});client.headers['Authorization']='Bearer '+r.json()['access_token']
 assert client.get(f'/api/theses/{key}/versions').json()==[]
 assert client.get(f'/api/theses/{key}/investigations').json()==[]
 assert client.post(f'/api/theses/{key}/investigate',json=body).status_code==422
print('PASS HTTP interpretation confirmation/version history, screen, purchase, frozen recheck, timeline, and cross-user isolation')
try:command.downgrade(cfg,'e5f7a9b1c3d5')
except RuntimeError as e:
 assert 'history' in str(e);print('PASS destructive history downgrade refused')
else:raise AssertionError('History could be destroyed')
