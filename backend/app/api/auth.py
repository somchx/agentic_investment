import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator
from sqlalchemy.exc import IntegrityError

import db
from app.security import create_access_token, current_user_id

router = APIRouter(prefix="/api/auth", tags=["auth"])
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class Credentials(BaseModel):
    email: EmailStr
    password: str


class Registration(Credentials):
    full_name: FullName
    password: str = Field(min_length=8, max_length=128)


class ProfileUpdate(BaseModel):
    full_name: FullName
    email: EmailStr


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not all(re.search(pattern, value) for pattern in (r"[A-Z]", r"[a-z]", r"[0-9]", r"[^a-zA-Z0-9]")):
            raise ValueError("Password must include uppercase, lowercase, a number and a special character")
        return value


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


def token_response(user: dict) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(user["id"], user["email"], user["token_version"]),
        user=UserOut(**user),
    )


@router.post("/register", response_model=TokenOut)
def register(body: Registration):
    try:
        user_id = db.create_user(body.email, body.password, body.full_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError:
        raise HTTPException(status_code=409, detail="That email is already registered")
    return token_response(db.get_user_by_id(user_id))


@router.post("/login", response_model=TokenOut)
def login(body: Credentials):
    user = db.verify_user(body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="incorrect email or password")
    return token_response(user)


@router.get("/me", response_model=UserOut)
def me(user_id: int = Depends(current_user_id)):
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="not logged in")
    return UserOut(**user)


@router.patch("/me", response_model=UserOut)
def update_profile(body: ProfileUpdate, user_id: int = Depends(current_user_id)):
    try:
        user = db.update_user_profile(user_id, body.full_name, body.email)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="That email is already registered")
    if not user:
        raise HTTPException(status_code=401, detail="not logged in")
    return UserOut(**user)


@router.post("/change-password", response_model=TokenOut)
def change_password(body: PasswordChange, user_id: int = Depends(current_user_id)):
    try:
        user = db.change_user_password(user_id, body.current_password, body.new_password)
    except ValueError as e:
        # A wrong current password is a form error, not an expired login.
        raise HTTPException(status_code=400, detail=str(e))
    if not user:
        raise HTTPException(status_code=401, detail="not logged in")
    # Keep this browser signed in with a fresh token; revoke previous tokens.
    return token_response(user)
