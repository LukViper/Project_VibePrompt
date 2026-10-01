"""Assertion lifecycle promotion APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.projects import get_project
from app.auth.deps import AuthContext, get_auth_context
from app.database.session import get_db
from app.schemas.assertions import AssertionStatus
from app.services.analytics import track
from app.services.assertion_promotion import promote_assertion

router = APIRouter(tags=["assertions"])


class PromoteBody(BaseModel):
    reason: str = ""
    superseded_by: str | None = None


def _promote(
    project_id: str,
    assertion_id: str,
    target: AssertionStatus,
    body: PromoteBody | None,
    db: Session,
    auth: AuthContext,
):
    project = get_project(project_id, db, auth)
    try:
        result = promote_assertion(
            db,
            project,
            assertion_id,
            target_status=target.value,
            reason=(body.reason if body else "") or f"user {target.value.lower()}",
            superseded_by=body.superseded_by if body else None,
        )
    except ValueError as exc:
        message = str(exc)
        code = 404 if "not found" in message.lower() else 409
        raise HTTPException(status_code=code, detail=message) from exc
    db.commit()
    track("assertion_promoted")
    return result


@router.post("/projects/{project_id}/assertions/{assertion_id}/confirm")
def confirm_assertion(
    project_id: str,
    assertion_id: str,
    body: PromoteBody | None = None,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    return _promote(project_id, assertion_id, AssertionStatus.CONFIRMED, body, db, auth)


@router.post("/projects/{project_id}/assertions/{assertion_id}/reject")
def reject_assertion(
    project_id: str,
    assertion_id: str,
    body: PromoteBody | None = None,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    return _promote(project_id, assertion_id, AssertionStatus.REJECTED, body, db, auth)


@router.post("/projects/{project_id}/assertions/{assertion_id}/lock")
def lock_assertion(
    project_id: str,
    assertion_id: str,
    body: PromoteBody | None = None,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    return _promote(project_id, assertion_id, AssertionStatus.LOCKED, body, db, auth)


@router.post("/projects/{project_id}/assertions/{assertion_id}/supersede")
def supersede_assertion(
    project_id: str,
    assertion_id: str,
    body: PromoteBody | None = None,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    if body is None:
        body = PromoteBody()
    return _promote(project_id, assertion_id, AssertionStatus.SUPERSEDED, body, db, auth)


@router.post("/projects/{project_id}/assertions/{assertion_id}/propose")
def propose_assertion(
    project_id: str,
    assertion_id: str,
    body: PromoteBody | None = None,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Promote INFERRED/MENTIONED → PROPOSED explicitly."""
    return _promote(project_id, assertion_id, AssertionStatus.PROPOSED, body, db, auth)
