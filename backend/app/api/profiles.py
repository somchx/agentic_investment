from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import db
from app.security import current_user_id

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.get("")
def list_profiles(user_id: int = Depends(current_user_id)):
    return db.list_profiles(user_id)


class ProfileIn(BaseModel):
    name: str
    risk_tolerance: str
    investment_horizon: str
    position_size_pct: float
    objective: str


@router.post("")
def create_profile(body: ProfileIn, user_id: int = Depends(current_user_id)):
    try:
        db.save_profile(
            user_id=user_id, name=body.name, risk_tolerance=body.risk_tolerance,
            investment_horizon=body.investment_horizon, position_size_pct=body.position_size_pct,
            objective=body.objective,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "profiles": db.list_profiles(user_id)}


@router.delete("/{profile_id}")
def delete_profile(profile_id: int, user_id: int = Depends(current_user_id)):
    db.delete_profile(profile_id, user_id)
    return {"ok": True}
