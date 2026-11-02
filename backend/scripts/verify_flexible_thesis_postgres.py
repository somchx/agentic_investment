"""Isolated PostgreSQL migration + HTTP integration. Never use an application DB.
Run with DATABASE_URL and DATABASE_URL_UNPOOLED pointing to a DB named *_test_*.
"""
import os,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine,text
from alembic.config import Config
from alembic import command
url=os.environ['DATABASE_URL']
assert '_test_' in url.rsplit('/',1)[-1], 'Requires an isolated test database'
engine=create_engine(url)
cfg=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
cfg.set_main_option('script_location',str(Path(__file__).resolve().parents[1]/'alembic'))
command.upgrade(cfg,'d4e6f8a0b2c4')
legacy={'metric':'Revenue','comparison':'>','threshold':.1,'kind':'yoy_growth','description':'Legacy snapshot'}
with engine.begin() as c:
    uid=c.execute(text("INSERT INTO users(email,password_hash,created_at,full_name,token_version) VALUES ('migration@example.com','not-a-login',now(),'Migration test',0) RETURNING id")).scalar()
    c.execute(text("INSERT INTO reasons(reason_key,user_id,metric,comparison,threshold,kind,denominator_metric,description,instant,is_builtin,created_at) VALUES ('legacy_test',:uid,'Revenue','>',.1,'yoy_growth','','Legacy',false,false,now())"),{'uid':uid})
    pid=c.execute(text("INSERT INTO purchases(user_id,ticker,quantity,purchase_price,purchase_date,reason_key,reason_snapshot_json,created_at) VALUES (:uid,'AAPL',1,100,'2025-06-01','legacy_test',CAST(:snap AS jsonb),now()) RETURNING id"),{'uid':uid,'snap':json.dumps(legacy)}).scalar()
command.upgrade(cfg,'head')
with engine.connect() as c:
    row=c.execute(text("SELECT threshold,rule_definition,original_text FROM reasons WHERE reason_key='legacy_test'")).one()
    assert tuple(row)==(.1,None,'')
    assert c.execute(text('SELECT reason_snapshot_json FROM purchases WHERE id=:id'),{'id':pid}).scalar()==legacy
print('PASS PostgreSQL upgrade preserves legacy rule and purchase snapshot')
command.downgrade(cfg,'d4e6f8a0b2c4');command.upgrade(cfg,'head')
print('PASS safe downgrade/re-upgrade before versioned rules exist')
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
import tools,sec_client,portfolio_report

def fixture(ticker):
    facts={}
    for tag,values in [('RevenueFromContractWithCustomerExcludingAssessedTax',(0,100)),('OperatingIncomeLoss',(10,20)),('LongTermDebtNoncurrent',(50,40))]:
        entries=[]
        for year,value in zip([2024,2025],values):
            item={'end':f'{year}-03-31','val':value,'fy':year,'fp':'Q1','form':'10-Q','accn':f'0000320193-{year}-000001','filed':f'{year}-05-01'}
            if tag!='LongTermDebtNoncurrent':item['start']=f'{year}-01-01'
            entries.append(item)
        facts[tag]={'units':{'USD':entries},'label':tag}
    return {'cik':320193,'entityName':'TEST FIXTURE — not live financial data','facts':{'us-gaap':facts}}
with patch.object(tools,'get_company_facts',side_effect=fixture),patch.object(portfolio_report,'get_company_facts',side_effect=fixture),TestClient(app) as client:
    r=client.post('/api/auth/register',json={'email':'http-thesis@example.com','password':'Only-Test-Password-2026','full_name':'HTTP test'});assert r.status_code in (200,201),r.text
    client.headers['Authorization']='Bearer '+r.json()['access_token']
    payload={'reason_key':'http_direction','description':'Revenue does not decrease','preview_ticker':'AAPL','rule_definition':{'version':1,'preset':'revenue_non_decreasing','evaluation_period':'quarterly'},'original_text':'Original user rationale'}
    r=client.post('/api/reasons',json=payload);assert r.status_code==200,r.text;assert r.json()['preview']['rule_status']=='SATISFIED'
    r=client.get('/api/screen',params={'reason_key':'http_direction'});assert r.status_code==200,r.text
    assert all(c['by_reason']['http_direction']['computed_value']==100 for c in r.json()['companies'])
    r=client.post('/api/positions',json={'ticker':'AAPL','quantity':1,'purchase_price':100,'purchase_date':'2025-06-01','reason_keys':['http_direction']});assert r.status_code==200,r.text
    purchases=client.get('/api/positions').json();purchased=purchases[0];snap=purchased['reasons'][0]['reason_snapshot']
    assert snap['rule_definition']['preset']=='revenue_non_decreasing' and snap['rule_status_at_purchase']=='SATISFIED'
    r=client.patch('/api/reasons/http_direction',json={'description':'New annual expectation','rule_definition':{'version':1,'preset':'revenue_increasing','evaluation_period':'annual'},'original_text':'Changed'});assert r.status_code==200,r.text
    assert client.get('/api/positions').json()[0]['reasons'][0]['reason_snapshot']==snap
    r=client.get(f"/api/positions/{purchased['id']}/revalidation");assert r.status_code==200,r.text
    r=client.get('/api/report/AAPL');assert r.status_code==200,r.text
    assert any(x['reason_key']=='http_direction' for x in r.json()['reasons'])
    r=client.delete('/api/reasons/http_direction');assert r.status_code==200,r.text
    assert client.get('/api/positions').json()[0]['reasons'][0]['reason_snapshot']==snap
print('PASS authenticated API create / screen / purchase / edit / revalidation / report / delete; snapshots unchanged')
try:
    command.downgrade(cfg,'d4e6f8a0b2c4')
except RuntimeError as exc:
    assert 'versioned thesis' in str(exc)
    print('PASS destructive downgrade refused when directional rules exist')
else:raise AssertionError('Unsafe downgrade accepted')
