"""Decision approve/reject API — user must activate PROPOSED recommendations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.projects import get_project
from app.auth.deps import AuthContext, get_auth_context
from app.database.session import get_db
from app.services.analytics import track
from app.services.decisions import approve_decision, list_decisions, reject_decision

router = APIRouter(tags=["decisions"])


@router.get("/projects/{project_id}/decisions")
def get_decisions(
    project_id: str,
    status: str | None = None,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    return list_decisions(project.state or {}, status=status)


@router.post("/projects/{project_id}/decisions/{decision_id}/approve")
def approve(
    project_id: str,
    decision_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    try:
        state = approve_decision(db, project, decision_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    track("decision_made")
    return {"state": state, "decision_id": decision_id, "status": "ACTIVE"}


@router.post("/projects/{project_id}/decisions/{decision_id}/reject")
def reject(
    project_id: str,
    decision_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    try:
        state = reject_decision(db, project, decision_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return {"state": state, "decision_id": decision_id, "status": "REJECTED"}
