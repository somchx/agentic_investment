import os
os.environ.setdefault('DATABASE_URL','sqlite://')
os.environ.setdefault('JWT_SECRET_KEY','thesis-test-secret')
import unittest
from dataclasses import replace
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException
from app.api.reasons import ReasonIn, ReasonEditIn, api_create_reason, api_edit_reason
from app.api.positions import _freeze_reason
from app.db.models import User, Reason as DbReason, HiddenReason
from models import Reason, Fact
from thesis_rules import normalize_rule
from reason_engine import evaluate_yoy_growth, evaluate_margin_level
import db, tools
from agent import _with_tool_calls, scoped_reason_tools
from investigation_state import InvestigationState
from xbrl_extract import extract_annual_facts

def fact(value,year=2025,metric='Revenue',unit='USD',annual=False):
    return Fact(metric,f'{year}-01-01',f'{year}-12-31' if annual else f'{year}-03-31',value,unit,year,'FY' if annual else 'Q1','10-K' if annual else '10-Q',f'0000000001-{year}-01',f'{year+1}-02-01' if annual else f'{year}-05-01','0000000001')
def reason(preset,period='quarterly'):
    m,op,t,k,d,i,r=normalize_rule({'version':1,'preset':preset,'evaluation_period':period},'', '>=',None,'yoy_growth')
    return Reason('test','TEST',m,op,t,kind=k,denominator_metric=d,instant=i,rule_definition=r)
def evaluate(r,fs,den=None,at='2027-01-01'):
    return evaluate_margin_level(r,fs,den,at) if r.kind=='margin_level' else evaluate_yoy_growth(r,fs,at)

class DirectionalTests(unittest.TestCase):
    def test_revenue_increase_equal_decrease_and_zero_base(self):
        for preset,expect in [('revenue_non_decreasing',[True,True,False]),('revenue_increasing',[True,False,False])]:
            for current,holds in zip([110,100,90],expect):
                ev=evaluate(reason(preset),[fact(100,2024),fact(current)])
                self.assertEqual(ev.rule_status,'SATISFIED' if holds else 'BREACHED')
                self.assertEqual(ev.evidence_status,'SUFFICIENT')
        self.assertEqual(evaluate(reason('revenue_increasing'),[fact(0,2024),fact(1)]).rule_status,'SATISFIED')
        self.assertEqual(evaluate(reason('revenue_non_decreasing'),[fact(0,2024),fact(0)]).rule_status,'SATISFIED')
    def test_operating_profit(self):
        for n,status in [(10,'SATISFIED'),(0,'BREACHED'),(-10,'BREACHED')]:
            self.assertEqual(evaluate(reason('operating_profit_positive'),[fact(n,metric='OperatingIncome')]).rule_status,status)
    def test_margin_up_equal_down(self):
        for n,status in [(30,'SATISFIED'),(20,'SATISFIED'),(10,'BREACHED')]:
            ev=evaluate(reason('margin_non_decreasing'),[fact(20,2024,'OperatingIncome'),fact(n,metric='OperatingIncome')],[fact(100,2024),fact(100)])
            self.assertEqual(ev.rule_status,status);self.assertEqual(ev.comparison_value,.2)
    def test_debt_up_equal_down(self):
        for n,status in [(110,'BREACHED'),(100,'SATISFIED'),(90,'SATISFIED')]:
            fs=[replace(fact(100,2024),period_start=''),replace(fact(n),period_start='')]
            self.assertEqual(evaluate(reason('debt_non_increasing'),fs).rule_status,status)
    def test_missing_units_duration_company_and_year_matching(self):
        r=reason('revenue_non_decreasing')
        bad=[[],[fact(100)],[fact(100,2024),fact(101,unit='EUR')],
             [fact(100,2024),replace(fact(101),period_start='2025-02-01')],
             [fact(100,2024),replace(fact(101),cik='0000000002')],
             [fact(100,2024),replace(fact(101),period_start='2025-01-30',period_end='2025-04-29')]]
        for fs in bad:
            with self.subTest(fs=fs):
                ev=evaluate(r,fs);self.assertEqual(ev.rule_status,'NOT_EVALUATED');self.assertEqual(ev.evidence_status,'INSUFFICIENT')
    def test_margin_denominator_period_unit_and_zero(self):
        nums=[fact(20,2024),fact(20)]
        for den in [[fact(100,2024),fact(0)], [fact(100,2024),fact(100,unit='EUR')], [fact(100,2024),replace(fact(100),period_start='2025-01-02')]]:
            self.assertEqual(evaluate(reason('margin_non_decreasing'),nums,den).rule_status,'NOT_EVALUATED')
    def test_temporal_and_conflict_are_not_rule_status(self):
        r=reason('operating_profit_positive')
        ev=evaluate(r,[fact(10)],at='2025-04-01')
        self.assertEqual(ev.evidence_status,'NOT_YET_OBSERVABLE');self.assertEqual(ev.rule_status,'NOT_EVALUATED')
        ev=evaluate(r,[fact(10),replace(fact(20),filed='2025-06-01')])
        self.assertEqual(ev.rule_status,'SATISFIED');self.assertEqual(ev.evidence_status,'CONFLICTING')
    def test_annual_vs_quarterly(self):
        fs=[fact(100,2024,annual=True),fact(105,annual=True)]
        self.assertEqual(evaluate(reason('revenue_non_decreasing','annual'),fs).rule_status,'SATISFIED')
        self.assertEqual(evaluate(reason('revenue_non_decreasing'),fs).rule_status,'NOT_EVALUATED')
    def test_numeric_rule_zero_and_negative_base(self):
        fields=normalize_rule({'version':1,'preset':'custom','evaluation_period':'quarterly'},'Revenue','>',.1,'yoy_growth')
        m,o,t,k,d,i,definition=fields
        r=Reason('numeric','',m,o,t,kind=k,rule_definition=definition)
        for base in [0,-10]:self.assertEqual(evaluate(r,[fact(base,2024),fact(20)]).rule_status,'NOT_EVALUATED')
        self.assertEqual(evaluate(r,[fact(100,2024),fact(120)]).rule_status,'SATISFIED')
    def test_mapping_overrides_arbitrary_client_threshold_and_operator(self):
        m,op,t,*_=normalize_rule({'version':1,'preset':'revenue_non_decreasing','evaluation_period':'quarterly'},'Fake','<',999,'yoy_growth')
        self.assertEqual((m,op,t),('Revenue','>=',None))
        for definition in [{'version':2},{'version':1,'preset':'unknown','evaluation_period':'quarterly'}]:
            with self.assertRaises(ValueError):normalize_rule(definition,'','>',0,'yoy_growth')
    def test_annual_extractor_does_not_use_ytd(self):
        entries=[{'start':'2025-01-01','end':'2025-12-31','val':100,'form':'10-K','filed':'2026-02-01','accn':'x','fy':2025},
                 {'start':'2025-01-01','end':'2025-09-30','val':90,'form':'10-Q','filed':'2025-11-01','accn':'y','fy':2025}]
        fs=extract_annual_facts({'facts':{'us-gaap':{'Revenues':{'units':{'USD':entries}}}}},'1','Revenue')
        self.assertEqual(len(fs),1);self.assertEqual(fs[0].value,100)
    def test_agent_cannot_override_canonical_status(self):
        state=InvestigationState(ticker="AAPL")
        state.tool_calls.append({'name':'check_reason_status','input':{'reason_key':'test'},'result':{'status':'Broken','rule_status':'BREACHED','evidence_status':'SUFFICIENT','value_unit':'USD'}})
        result=_with_tool_calls({'reasons':[{'reason_key':'test','status':'Supported','rule_status':'SATISFIED'}]},state)
        self.assertEqual(result['reasons'][0]['rule_status'],'BREACHED')
        self.assertEqual(result['reasons'][0]['status'],'Broken')

    def test_agent_tool_schema_contains_only_visible_reason_keys(self):
        rows=[{'reason_key':'my_direction','rule_definition':reason('revenue_non_decreasing').rule_definition,'original_text':'Keep growing'}]
        with patch.object(db,'list_reasons',return_value=rows):
            specs,keys,context=scoped_reason_tools(user_id=77)
        self.assertEqual(keys,{'my_direction'})
        self.assertEqual(context[0]['original_text'],'Keep growing')
        for spec in specs:
            prop=spec['input_schema']['properties'].get('reason_key')
            if prop is not None:self.assertEqual(prop['enum'],['my_direction'])

    def test_secondary_debt_does_not_claim_verified_boundary(self):
        r=reason('debt_non_increasing')
        fs=[replace(fact(v,y,metric='LongTermDebt'),period_start=None) for y,v in [(2024,50),(2025,40)]]
        ev=evaluate_yoy_growth(r,fs,'2025-06-01')
        with patch.object(tools,'_evaluate_reason_obj',return_value=('Apple',r,fs,ev)):
            result=tools.structured_secondary_evidence('AAPL',r,'2025-06-01')
        self.assertFalse(result['checked']);self.assertFalse(result['period_matches'])


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://',poolclass=StaticPool)
        for table in [User.__table__,DbReason.__table__,HiddenReason.__table__]:table.create(self.engine)
        self.sessions=sessionmaker(bind=self.engine)
        self.patch=patch.object(db,'SessionLocal',self.sessions);self.patch.start()
    def tearDown(self):self.patch.stop();self.engine.dispose()
    def test_create_preview_edit_and_frozen_purchase(self):
        payload=ReasonIn(reason_key='direction',description='Revenue not decreasing',rule_definition={'version':1,'preset':'revenue_non_decreasing','evaluation_period':'quarterly'},original_text='My original reason',preview_ticker='AAPL')
        fs=[fact(100,2024),fact(110)]
        with patch.object(tools,'load_reason_facts',return_value=('Apple',fs,None)):
            response=api_create_reason(payload,user_id=1)
            self.assertEqual(response['preview']['rule_status'],'SATISFIED')
            stored=db.get_reason_by_key('direction');self.assertIsNone(stored['threshold']);self.assertFalse(stored['is_custom'])
            frozen=_freeze_reason('AAPL','direction','2025-06-01',1)
            self.assertEqual(frozen['original_text'],'My original reason')
            api_edit_reason('direction',ReasonEditIn(description='Revenue must increase',rule_definition={'version':1,'preset':'revenue_increasing','evaluation_period':'annual'},original_text='New rationale'),user_id=1)
            self.assertEqual(frozen['rule_definition']['preset'],'revenue_non_decreasing')
            self.assertEqual(frozen['rule_definition']['evaluation_period'],'quarterly')
            self.assertEqual(tools.evaluate_frozen_reason('AAPL',frozen,'2025-06-01')['rule_status'],'SATISFIED')
            with self.assertRaises(HTTPException):api_edit_reason('direction',ReasonEditIn(description='Not mine'),user_id=2)
    def test_legacy_snapshot_still_works(self):
        frozen={'metric':'Revenue','comparison':'>','threshold':.1,'kind':'yoy_growth','description':'Legacy','is_builtin':True}
        with patch.object(tools,'load_reason_facts',return_value=('Apple',[fact(100,2024),fact(120)],None)):
            self.assertEqual(tools.evaluate_frozen_reason('AAPL',frozen,'2025-06-01')['rule_status'],'SATISFIED')

if __name__=='__main__':unittest.main()
