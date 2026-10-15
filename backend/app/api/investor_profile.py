from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import db
from app.security import current_user_id

router = APIRouter(prefix="/api/investor-profile", tags=["investor-profile"])


@router.get("")
def get_investor_profile(user_id: int = Depends(current_user_id)):
    """The user's own single investor profile (budget/goals/risk tolerance),
    used to personalize the portfolio-wide chat agent -- distinct from the
    reusable named presets under /api/profiles. Returns null if never set."""
    return db.get_investor_profile_settings(user_id)


class InvestorProfileIn(BaseModel):
    budget_usd: float | None = None
    target_growth_pct: float | None = None
    investment_horizon: str | None = None
    risk_tolerance: str | None = None
    goals: str | None = None
    notes: str | None = None


@router.put("")
def put_investor_profile(body: InvestorProfileIn, user_id: int = Depends(current_user_id)):
    try:
        return db.save_investor_profile_settings(
            user_id=user_id,
            budget_usd=body.budget_usd,
            target_growth_pct=body.target_growth_pct,
            investment_horizon=body.investment_horizon,
            risk_tolerance=body.risk_tolerance,
            goals=body.goals,
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
