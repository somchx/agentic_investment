from fastapi import APIRouter, Depends

from app.security import current_user_id
from sec_client import KNOWN_CIKS, get_company_facts

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("")
def list_companies(user_id: int = Depends(current_user_id)):
    out = []
    for ticker in sorted(KNOWN_CIKS.keys()):
        try:
            name = get_company_facts(ticker).get("entityName", ticker)
        except Exception:  # noqa: BLE001 -- name is cosmetic, never block the list on it
            name = ticker
        out.append({"ticker": ticker, "name": name})
    return out
