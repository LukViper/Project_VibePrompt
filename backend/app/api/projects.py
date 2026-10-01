"""Project CRUD with guest / registered ownership isolation."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import AuthContext, get_auth_context, require_auth
from app.database.base import utcnow
from app.database.session import get_db
from app.models import Project
from app.schemas.state import ProjectStateModel
from app.services.analytics import track
from app.services.architecture import propose_architecture
from app.services.conversation import ensure_conversation, post_message
from app.services.grill import grill, professional_review
from app.services.project_state import empty_state, public_state
from app.services.summary import build_project_summary, format_summary_for_chat

router = APIRouter(tags=["projects"])


class ProjectCreate(BaseModel):
    title: str = ""
    description: str | None = Field(default=None, max_length=8000)


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)


def get_project(
    project_id: str,
    db: Session,
    auth: AuthContext | None = None,
) -> Project:
    try:
        key = uuid.UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    project = db.get(Project, key)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    assert_project_access(project, auth)
    return project


def assert_project_access(project: Project, auth: AuthContext | None) -> None:
    """Enforce ownership when the project is owned or the caller is authenticated.

    Legacy anonymous projects (user_id is None) remain readable without a token
    so existing tests and demos keep working. Owned projects require the matching
    bearer token.
    """
    if project.user_id is None:
        return
    if auth is None or not auth.authenticated:
        raise HTTPException(status_code=401, detail="Authentication required for this project")
    if auth.user_id != project.user_id:
        raise HTTPException(status_code=403, detail="Not allowed to access this project")


def project_payload(project: Project) -> dict:
    return {
        "id": str(project.id),
        "title": project.title,
        "status": project.status,
        "user_id": str(project.user_id) if project.user_id else None,
        "is_ephemeral": bool(project.is_ephemeral),
        "state": public_state(project.state or empty_state()),
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }


@router.post("/projects")
def create_project(
    body: ProjectCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    ephemeral = False
    owner_id = None
    if auth.authenticated and auth.user_id is not None:
        owner_id = auth.user_id
        ephemeral = bool(auth.is_guest)
    project = Project(
        title=body.title,
        status="onboarding",
        state=empty_state(),
        user_id=owner_id,
        is_ephemeral=ephemeral,
    )
    if body.title:
        project.state["project"]["title"] = body.title
    db.add(project)
    db.flush()
    ensure_conversation(db, project)
    analysis = post_message(db, project, body.description) if body.description else None
    db.commit()
    db.refresh(project)
    track("project_created")
    payload = project_payload(project)
    if analysis:
        payload["analysis"] = analysis
    return payload


@router.get("/projects")
def list_projects(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    rows = db.scalars(
        select(Project).where(Project.user_id == auth.user_id).order_by(Project.updated_at.desc())
    ).all()
    return [project_payload(row) for row in rows]


@router.get("/projects/{project_id}")
def read_project(
    project_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    return project_payload(get_project(project_id, db, auth))


@router.patch("/projects/{project_id}")
def update_project(
    project_id: str,
    body: ProjectUpdate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    if body.title is not None:
        project.title = body.title.strip()
        state = project.state or empty_state()
        state.setdefault("project", {})["title"] = project.title
        project.state = state
    project.updated_at = utcnow()
    db.commit()
    db.refresh(project)
    return project_payload(project)


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    # Guests and owners may delete their own; anonymous legacy only without ownership barrier.
    db.delete(project)
    db.commit()
    return {"deleted": True, "id": project_id}


@router.post("/projects/{project_id}/claim")
def claim_project(
    project_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """Attach a legacy anonymous project to the current registered (non-guest) user."""
    if auth.is_guest:
        raise HTTPException(status_code=403, detail="Registered account required to claim a project")
    project = db.get(Project, uuid.UUID(project_id)) if _valid_uuid(project_id) else None
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id is not None and project.user_id != auth.user_id:
        raise HTTPException(status_code=403, detail="Project already owned by another user")
    project.user_id = auth.user_id
    project.is_ephemeral = False
    project.updated_at = utcnow()
    db.commit()
    db.refresh(project)
    return project_payload(project)


@router.get("/projects/{project_id}/state")
def read_state(
    project_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    payload = public_state(project.state or empty_state())
    ProjectStateModel.model_validate(payload)
    return payload


@router.get("/projects/{project_id}/summary")
def read_summary(
    project_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    summary = build_project_summary(project.state or empty_state())
    return {"summary": summary, "narrative": format_summary_for_chat(summary)}


@router.post("/projects/{project_id}/grill")
def run_grill(
    project_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    track("grill_started")
    report = grill(project.state or empty_state(), persist_on_project=project, session=db)
    db.commit()
    track("grill_completed")
    return report


@router.post("/projects/{project_id}/architecture")
def run_architecture(
    project_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    result = propose_architecture(db, project)
    db.commit()
    return result


@router.post("/projects/{project_id}/review")
def run_review(
    project_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    return professional_review(project.state or empty_state())


def _valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False
