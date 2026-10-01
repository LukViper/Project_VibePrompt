import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.projects import get_project
from app.auth.deps import AuthContext, get_auth_context
from app.database.session import get_db
from app.models import Idea
from app.services.idea_generation import generate_ideas
from app.services.project_state import reject_idea, select_idea

router = APIRouter(tags=["ideas"])


def idea_payload(row: Idea, index: int) -> dict:
    details = row.details or {}
    return {
        "id": str(row.id),
        "index": index,
        "title": row.title,
        "problem": row.problem,
        "objective": row.objective,
        "why_it_matters": details.get("why_it_matters") or "",
        "solution": details.get("solution") or "",
        "users": details.get("users") or "",
        "architecture": details.get("architecture") or "",
        "ai_nlp": details.get("ai_nlp") or "",
        "data": details.get("data") or "",
        "research_extension": details.get("research_extension") or "",
        "risks": details.get("risks") or [],
        "required_concepts": row.required_concepts,
        "features": row.features,
        "technology": row.technology,
        "difficulty": row.difficulty,
        "estimated_scope": row.estimated_scope,
        "extensions": row.extensions,
        "details": details,
        "source": row.source,
        "selected": row.selected,
        "rejected": row.rejected,
    }


@router.get("/projects/{project_id}/ideas")
def list_ideas(
    project_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    rows = db.scalars(select(Idea).where(Idea.project_id == project.id).order_by(Idea.created_at)).all()
    return [idea_payload(row, index + 1) for index, row in enumerate(rows)]


@router.post("/projects/{project_id}/ideas")
def create_ideas(
    project_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    rows = generate_ideas(db, project)
    db.commit()
    return [idea_payload(row, index + 1) for index, row in enumerate(rows)]


@router.post("/projects/{project_id}/ideas/{idea_id}/select")
def choose_idea(
    project_id: str,
    idea_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    idea = _idea(db, project.id, idea_id)
    state = select_idea(db, project, idea)
    db.commit()
    return {"idea": idea_payload(idea, 0), "state": state}


@router.post("/projects/{project_id}/ideas/{idea_id}/reject")
def dismiss_idea(
    project_id: str,
    idea_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    idea = _idea(db, project.id, idea_id)
    state = reject_idea(db, project, idea)
    db.commit()
    return {"idea": idea_payload(idea, 0), "state": state}


def _idea(db: Session, project_id, idea_id: str) -> Idea:
    try:
        key = uuid.UUID(idea_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Idea not found") from exc
    idea = db.get(Idea, key)
    if idea is None or idea.project_id != project_id:
        raise HTTPException(status_code=404, detail="Idea not found")
    return idea
