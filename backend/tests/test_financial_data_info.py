import unittest
from unittest.mock import patch
from types import SimpleNamespace
import app
from xbrl_extract import list_available_tags
from models import Reason
import tools

class FinancialDataInfoTests(unittest.TestCase):
    def test_definition_and_filing_provenance(self):
        tags = list_available_tags({'cik': 320193, 'entityName': 'Example', 'facts': {'us-gaap': {
            'AccountsReceivableNetCurrent': {'label': 'Receivables', 'description': 'Source definition.', 'units': {'USD': [
                {'form': '10-Q', 'end': '2025-03-31', 'filed': '2025-05-01', 'accn': '0000320193-25-000001'},
                {'form': '10-K', 'end': '2025-12-31', 'filed': '2026-02-01', 'accn': '0000320193-26-000002'},
            ]}}
        }}})
        self.assertEqual(tags[0]['description'], 'Source definition.')
        self.assertEqual(tags[0]['source']['form'], '10-K')
        self.assertEqual(tags[0]['source']['period_end'], '2025-12-31')
        self.assertEqual(tags[0]['source']['url'], 'https://www.sec.gov/Archives/edgar/data/320193/000032019326000002/0000320193-26-000002-index.html')

    def test_absent_metadata_is_not_invented(self):
        tags = list_available_tags({'facts': {'us-gaap': {'A': {'units': {'USD': [{'end': '2025-01-01', 'form': '10-K'}]}}}}})
        self.assertIsNone(tags[0]['description'])
        self.assertIsNone(tags[0]['source'])

    def test_instant_ratio_passes_denominator_facts(self):
        reason = Reason('test', '', 'A', '>', .1, kind='margin_level', denominator_metric='B', instant=True, is_custom=True)
        numerator = [SimpleNamespace(filed='2026-01-01')]
        denominator = [SimpleNamespace(filed='2026-01-01')]
        with patch.object(tools, 'get_company_facts', return_value={'cik': 1}), patch.object(tools, 'extract_instant_facts_for_tag', side_effect=[numerator, denominator]), patch.object(tools, 'evaluate_margin_level') as evaluate:
            tools._evaluate_reason_obj('TEST', reason, None)
        evaluate.assert_called_once_with(reason, numerator, denominator, '2026-01-01')
