from fastapi import APIRouter, Depends

from app.security import current_user_id
from sec_client import KNOWN_CIKS

router = APIRouter(prefix="/api/companies", tags=["companies"])


# Display labels for the fixed pilot cohort. Listing companies must never fetch
# full SEC filings; those are loaded only by financial-data endpoints.
COMPANY_NAMES = {
    "AAPL": "Apple Inc.", "AMZN": "Amazon.com, Inc.", "COST": "Costco Wholesale Corporation",
    "GOOGL": "Alphabet Inc.", "JNJ": "Johnson & Johnson", "KO": "The Coca-Cola Company",
    "META": "Meta Platforms, Inc.", "MSFT": "Microsoft Corporation", "NFLX": "Netflix, Inc.",
    "NVDA": "NVIDIA Corporation", "ORCL": "Oracle Corporation", "PEP": "PepsiCo, Inc.",
    "PG": "The Procter & Gamble Company", "TSLA": "Tesla, Inc.", "WMT": "Walmart Inc.",
}


@router.get("")
def list_companies(user_id: int = Depends(current_user_id)):
    return [{"ticker": ticker, "name": COMPANY_NAMES.get(ticker, ticker)}
            for ticker in sorted(KNOWN_CIKS)]
