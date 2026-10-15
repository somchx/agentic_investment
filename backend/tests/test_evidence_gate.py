"""Offline regressions; run against both core implementations via PYTHONPATH."""
import unittest
from types import SimpleNamespace as Obj
from unittest.mock import patch
import investigation_state as gate
import tools

class EvidenceGateTests(unittest.TestCase):
    def assess(self, result, period='2025-06-30'):
        state=gate.InvestigationState('AMZN')
        state.record('check_reason_status',{'reason_key':'debt_growth'},
                     {'status':'Broken','evaluated_period':period})
        state.record('get_secondary_evidence',{'reason_key':'debt_growth'},result)
        return gate.assess_sufficiency(state,[{'reason_key':'debt_growth','status':'Broken'}])

    def test_valid_evidence(self):
        self.assertEqual(self.assess(dict(checked=True,period_matches=True,target_period='2025-06-30')),[])

    def test_unchecked_legacy_wrong_period_and_non_boolean_flags_rejected(self):
        valid=dict(checked=True,period_matches=True,target_period='2025-06-30')
        invalid=[{}, {'checked':False}, {'checked':True},
                 valid|{'checked':False},valid|{'period_matches':False},
                 valid|{'period_matches':None},valid|{'target_period':'2025-03-31'},
                 valid|{'checked':1},valid|{'period_matches':'true'},
                 valid|{'error':'parse failed'}]
        for result in invalid:
            with self.subTest(result=result):self.assertTrue(self.assess(result))
        for period in [None,'',' ']:
            with self.subTest(period=period):self.assertTrue(self.assess(valid|{'target_period':period},period))

    def test_evidence_from_another_reason_cannot_satisfy_gate(self):
        state=gate.InvestigationState('AMZN')
        state.record('check_reason_status',{'reason_key':'debt_growth'},{'status':'Broken','evaluated_period':'2025-06-30'})
        state.record('get_secondary_evidence',{'reason_key':'revenue_growth'},dict(checked=True,period_matches=True,target_period='2025-06-30'))
        self.assertTrue(gate.assess_sufficiency(state,[{'reason_key':'debt_growth','status':'Broken'}]))

class SecondaryToolTests(unittest.TestCase):
    def run_tool(self, release_period='2025-06-30', value=100, as_of='2025-08-15'):
        # Same-quarter restatement is future evidence, although its period matches.
        facts=[Obj(period_end='2025-06-30',filed='2025-08-01',value=100,derivation=None),
               Obj(period_end='2025-06-30',filed='2025-09-01',value=999,derivation=None)]
        with patch.object(tools,'get_company_facts',return_value={'cik':1}), \
             patch.object(tools,'extract_quarterly_facts',return_value=facts), \
             patch.object(tools,'list_earnings_release_filings',return_value=[Obj(filed='2025-07-31')]), \
             patch.object(tools,'get_release_figure',return_value=Obj(period_end=release_period,value=value)):
            return tools.get_secondary_evidence('AMZN','revenue_growth',as_of)

    def test_point_in_time_comparison_does_not_use_future_restatement(self):
        r=self.run_tool()
        self.assertIs(r['checked'],True)
        self.assertEqual(r['filed_value'],100)
        self.assertEqual(r['diff_pct'],0)
        self.assertEqual(r['target_period'],'2025-06-30')

    def test_parse_failure_wrong_period_and_missing_primary_fail_closed(self):
        for kwargs in [dict(release_period=None),dict(value=None),dict(release_period='2025-03-31'),dict(as_of='2025-07-31')]:
            with self.subTest(kwargs=kwargs):
                r=self.run_tool(**kwargs)
                self.assertIs(r['checked'],False)
                self.assertIs(r['period_matches'],False)
                self.assertIn('target_period',r)

if __name__=='__main__':unittest.main()
