from fastapi import APIRouter, Depends, HTTPException

from app.security import current_user_id
from market_data import HISTORY_RANGES, MarketDataUnavailableError, get_history, get_quote, get_quotes, retry_after_seconds, provider_config
from sec_client import KNOWN_CIKS, is_supported_ticker

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/config")
def config(user_id: int = Depends(current_user_id)):
    return provider_config()


@router.get("/quote/{ticker}")
def quote(ticker: str, user_id: int = Depends(current_user_id)):
    ticker = ticker.upper()
    if not is_supported_ticker(ticker):
        raise HTTPException(status_code=400, detail=f"Unsupported ticker: '{ticker}' is not one of {sorted(KNOWN_CIKS)}")
    try:
        return get_quote(ticker)
    except MarketDataUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e) if provider_config()["provider"] == "Alpha Vantage" else "Price provider temporarily unavailable. Please try again later.",
                            headers={"Retry-After": str(retry_after_seconds())}) from e


@router.get("/quotes")
def quotes(tickers: str, user_id: int = Depends(current_user_id)):
    """Batch quote lookup -- `tickers` is a comma-separated list, e.g.
    ?tickers=AAPL,MSFT,NVDA. Best-effort: tickers Yahoo has no data for are
    simply omitted from the response rather than failing the whole batch.
    """
    requested = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    requested = list(dict.fromkeys(requested))
    if any(not is_supported_ticker(t) for t in requested):
        raise HTTPException(status_code=400, detail="Unsupported ticker")
    return get_quotes(requested)


@router.get("/history/{ticker}")
def history(ticker: str, range: str = "3mo", user_id: int = Depends(current_user_id)):
    ticker = ticker.upper()
    if not is_supported_ticker(ticker):
        raise HTTPException(status_code=400, detail=f"Unsupported ticker: '{ticker}' is not one of {sorted(KNOWN_CIKS)}")
    if range not in provider_config()["ranges"]:
        raise HTTPException(status_code=400, detail=f"range must be one of {provider_config()['ranges']}")
    try:
        return get_history(ticker, range)
    except MarketDataUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e) if provider_config()["provider"] == "Alpha Vantage" else "Price provider temporarily unavailable. Please try again later.",
                            headers={"Retry-After": str(retry_after_seconds())}) from e
