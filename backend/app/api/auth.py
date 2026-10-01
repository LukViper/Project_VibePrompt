"""Authentication API — guest continue, register, login."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import AuthContext, require_auth
from app.auth.security import create_access_token, hash_password, verify_password
from app.database.session import get_db
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterBody(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(default="", max_length=120)


class LoginBody(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)


def user_payload(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name or "",
        "is_guest": bool(user.is_guest),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def token_response(user: User) -> dict:
    token = create_access_token(
        user_id=str(user.id),
        is_guest=bool(user.is_guest),
        email=user.email,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_payload(user),
    }


@router.post("/guest")
def continue_as_guest(db: Session = Depends(get_db)):
    user = User(is_guest=True, display_name="Guest")
    db.add(user)
    db.commit()
    db.refresh(user)
    return token_response(user)


@router.post("/register")
def register(body: RegisterBody, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Invalid email")
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        display_name=(body.display_name or "").strip() or email.split("@")[0],
        is_guest=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return token_response(user)


@router.post("/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email, User.is_guest.is_(False)))
    if user is None or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return token_response(user)


@router.get("/me")
def me(auth: AuthContext = Depends(require_auth)):
    assert auth.user is not None
    return user_payload(auth.user)
