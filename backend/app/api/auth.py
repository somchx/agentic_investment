from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

import db
from app.security import create_access_token, current_user_id

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


@router.post("/register", response_model=TokenOut)
def register(body: Credentials):
    try:
        user_id = db.create_user(body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:  # noqa: BLE001 -- IntegrityError on duplicate email
        raise HTTPException(status_code=409, detail="that email is already registered")
    email = body.email.lower().strip()
    return TokenOut(access_token=create_access_token(user_id, email), user=UserOut(id=user_id, email=email))


@router.post("/login", response_model=TokenOut)
def login(body: Credentials):
    user = db.verify_user(body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="incorrect email or password")
    return TokenOut(access_token=create_access_token(user["id"], user["email"]), user=UserOut(**user))


@router.get("/me", response_model=UserOut)
def me(user_id: int = Depends(current_user_id)):
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="not logged in")
    return UserOut(id=user["id"], email=user["email"])
