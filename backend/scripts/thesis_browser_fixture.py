"""Isolated browser test server. Synthetic financial fixtures; never use for research."""
import os
assert '_test_' in os.environ['DATABASE_URL'], 'Test DB only'
from web import app
import tools, portfolio_report
from app.api import reasons, reports
from app.api import portfolio
from market_data import MarketDataUnavailableError

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
for module in [tools,portfolio_report,reasons]:module.get_company_facts=fixture
reports.get_data_freshness=lambda *a,**k: {'source':'TEST FIXTURE'}
portfolio.get_quote=lambda *a: (_ for _ in ()).throw(MarketDataUnavailableError('Test: market data disabled'))
# No remote market or AI calls during UI regression.
from app.api import market
market.get_quote=portfolio.get_quote
market.get_history=lambda *a,**k: []
market.get_quotes=lambda *a,**k: {}
