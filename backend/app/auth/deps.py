"""Auth FastAPI dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.database.session import get_db
from app.models import User


@dataclass
class AuthContext:
    user: User | None
    user_id: uuid.UUID | None
    is_guest: bool
    authenticated: bool

    @property
    def requires_ownership(self) -> bool:
        return self.authenticated and self.user_id is not None


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def get_auth_context(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AuthContext:
    token = _bearer_token(authorization)
    if not token:
        return AuthContext(user=None, user_id=None, is_guest=False, authenticated=False)
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(str(payload["sub"]))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return AuthContext(
        user=user,
        user_id=user.id,
        is_guest=bool(user.is_guest),
        authenticated=True,
    )


def require_auth(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if not auth.authenticated:
        raise HTTPException(status_code=401, detail="Authentication required")
    return auth


def require_registered(auth: AuthContext = Depends(require_auth)) -> AuthContext:
    if auth.is_guest:
        raise HTTPException(status_code=403, detail="Registered account required for permanent projects")
    return auth
