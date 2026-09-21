from fastapi import APIRouter, Depends, HTTPException, Query

from app.security import current_user_id
from sec_client import KNOWN_CIKS
from tools import check_reason_status

router = APIRouter(prefix="/api", tags=["screener"])

_STATUS_RANK = {"Supported": 0, "Weakened": 1, "Not enough data": 2, "Broken": 3}


@router.get("/screen")
def api_screen(reason_key: list[str] = Query(...), user_id: int = Depends(current_user_id)):
    """Runs the exact same deterministic check_reason_status the rest of
    the app uses for one company, looped over every known company and over
    every reason_key given (?reason_key=a&reason_key=b&...). This is NOT an
    opinion about what to buy -- it is a mechanical filter on the user's
    own stated rule(s), zero LLM involved. Each company's per-reason
    results are reported independently (a company missing data for one
    selected reason still shows results for the others), so this is a
    side-by-side comparison, not a combined AND filter.
    """
    reason_keys = [k for k in reason_key if k]
    if not reason_keys:
        raise HTTPException(status_code=400, detail="missing reason_key")

    companies = []
    for ticker in sorted(KNOWN_CIKS.keys()):
        by_reason = {}
        company_name = None
        for rk in reason_keys:
            result = check_reason_status(ticker, rk)
            if "error" in result:
                by_reason[rk] = {"error": result["error"]}
                continue
            company_name = company_name or result["company"]
            by_reason[rk] = {
                "description": result["reason"], "status": result["status"],
                "computed_value": result["computed_value"], "as_of": result["as_of"],
            }
        if company_name is None:
            # every selected reason failed for this company (e.g. a custom
            # reason's tag doesn't exist for it) -- still report it, just
            # with no evaluable results, rather than silently dropping it.
            company_name = ticker
        companies.append({"ticker": ticker, "company_name": company_name, "by_reason": by_reason})

    def worst_rank(company: dict) -> int:
        ranks = [
            _STATUS_RANK.get(r["status"], 9)
            for r in company["by_reason"].values()
            if "status" in r
        ]
        return max(ranks) if ranks else 9

    companies.sort(key=worst_rank)
    return {"reason_keys": reason_keys, "companies": companies}
