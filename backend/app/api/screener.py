from fastapi import APIRouter, Depends, HTTPException, Query

import db
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

    # Ownership check (Code Audit Session 3, item 3) -- check_reason_status
    # will happily evaluate ANY reason_key with no idea who it belongs to,
    # so without this a user could screen with another user's private
    # custom reason_key (guessed or otherwise obtained) with no error at
    # all. Reject the whole request the same way as an unknown key, so this
    # can't be used to probe which reason_keys exist.
    for rk in reason_keys:
        if db.get_reason_if_accessible(rk, user_id) is None:
            raise HTTPException(status_code=400, detail=f"unknown reason_key '{rk}'")

    companies = []
    for ticker in sorted(KNOWN_CIKS.keys()):
        by_reason = {}
        company_name = None
        for rk in reason_keys:
            result = check_reason_status(ticker, rk)
            if result.get("error_code") == "EVIDENCE_NOT_FOUND":
                # Missing evidence is not zero and must never fail a threshold.
                by_reason[rk] = {
                    "status": "Not enough data", "computed_value": None, "as_of": None,
                }
                continue
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
