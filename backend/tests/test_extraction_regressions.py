"""SEC snapshot regressions. Expectations transcribed from original tables, not Agent output."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from copy import deepcopy
from bs4 import BeautifulSoup
import earnings_release as er
import xbrl_extract as x
R=Path(__file__).resolve().parents[2]
S=R/'research/coverage_v0_1/sources'

class AmazonColumnTests(unittest.TestCase):
    def parse(self,html,metric):
        with patch.object(er,'get_document_text',return_value=html):
            return er.get_release_figure('0001018724',er.EarningsReleaseFiling('fixture','2025-08-01','fixture'),metric)

    def test_original_consolidated_tables_current_quarter_not_prior_year_or_ytd(self):
        expected={1:('2025-03-31',155667,18405),2:('2025-06-30',167702,19171),
                  3:('2025-09-30',180169,17422),4:('2025-12-31',213386,24977)}
        for q,(period,revenue,op) in expected.items():
            html=(S/f'AMZN_FY2025Q{q}_release.html').read_text()
            for metric,value in [('Revenue',revenue),('OperatingIncome',op)]:
                with self.subTest(q=q,metric=metric):
                    actual=self.parse(html,metric)
                    self.assertEqual((actual.period_end,actual.value),(period,value*1_000_000))

    def test_reverse_year_order_negative_value_and_unrecognized_heading(self):
        html=(S/'AMZN_FY2025Q2_release.html').read_text()
        # Counterfactual layout tests, not natural Gold cases.
        flipped=html.replace('2024','YEAR_A').replace('2025','2024').replace('YEAR_A','2025')
        self.assertEqual(self.parse(flipped,'Revenue').value,147977e6)
        negative=html.replace('19,171','(19,171)')
        self.assertEqual(self.parse(negative,'OperatingIncome').value,-19171e6)
        self.assertIsNone(self.parse(html.replace('Three Months Ended','Unknown Period'),'Revenue').value)

class MicrosoftQ4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.facts=json.loads((S/'MSFT_companyfacts.json').read_text())

    def test_q4_values_trace_and_availability(self):
        for metric,expected in [('Revenue',{2024:64727e6,2025:76441e6}),('OperatingIncome',{2024:27925e6,2025:34323e6})]:
            facts=x.extract_quarterly_facts(self.facts,'0000789019',metric)
            for year,value in expected.items():
                q4=[f for f in facts if f.period_end==f'{year}-06-30']
                self.assertEqual(len(q4),1)
                f=q4[0];self.assertEqual(f.value,value)
                self.assertEqual(f.period_start,f'{year}-04-01')
                self.assertEqual(f.fiscal_period,'Q4')
                self.assertEqual(len(f.derivation['operands']),2)
                self.assertNotIn(f,x.facts_as_of(facts,f'{year}-07-29'))
                self.assertIn(f,x.facts_as_of(facts,f'{year}-07-30'))

    def test_conflicting_nine_months_missing_operand_and_currency_fail_closed(self):
        tag='RevenueFromContractWithCustomerExcludingAssessedTax'
        base=deepcopy(self.facts)
        entries=base['facts']['us-gaap'][tag]['units']['USD']
        nine=next(e for e in entries if e.get('start')=='2024-07-01' and e['end']=='2025-03-31' and e['fy']==2025)
        for change in ['conflict','missing','currency']:
            f=deepcopy(base);units=f['facts']['us-gaap'][tag]['units'];data=units['USD']
            if change=='conflict':data.append(nine|{'val':nine['val']+1,'filed':'2025-05-01','accn':'different'})
            if change=='missing':units['USD']=[e for e in data if not (e.get('start')=='2024-07-01' and e['end']=='2025-03-31')]
            if change=='currency':units['EUR']=units.pop('USD')
            with self.subTest(change=change):
                self.assertFalse(any(r.period_end=='2025-06-30' and r.derivation for r in x.extract_quarterly_facts(f,'0000789019','Revenue')))

    def test_operands_match_consolidated_original_inline_facts(self):
        # Independently check original primary statements' non-dimensional contexts.
        expected={'MSFT_2024-06-30_10-K.html':('2023-07-01','2024-06-30',245122e6,109433e6),
                  'MSFT_2024-03-31_10-Q.html':('2023-07-01','2024-03-31',180395e6,81508e6),
                  'MSFT_2025-06-30_10-K.html':('2024-07-01','2025-06-30',281724e6,128528e6),
                  'MSFT_2025-03-31_10-Q.html':('2024-07-01','2025-03-31',205283e6,94205e6)}
        for filename,(start,end,rev,op) in expected.items():
            soup=BeautifulSoup((S/filename).read_text(),'html.parser')
            contexts={c.get('id') for c in soup.find_all(lambda t:t.name.lower().endswith(':context'))
                      if start in c.get_text() and end in c.get_text()
                      and not c.find(lambda t:t.name.lower().endswith((':explicitmember',':typedmember')))}
            for concept,value in [('RevenueFromContractWithCustomerExcludingAssessedTax',rev),('OperatingIncomeLoss',op)]:
                found=[]
                for fact in soup.find_all(lambda t:t.name.lower()=='ix:nonfraction'):
                    if fact.get('name','').split(':')[-1]!=concept or fact.get('contextref') not in contexts:continue
                    raw=fact.get_text('',strip=True).replace(',','')
                    try:found.append(float(raw)*10**int(fact.get('scale','0')))
                    except ValueError:pass
                self.assertIn(value,found,(filename,concept))

if __name__=='__main__':unittest.main()
