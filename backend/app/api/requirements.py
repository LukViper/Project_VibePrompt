from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.projects import get_project
from app.auth.deps import AuthContext, get_auth_context
from app.database.session import get_db
from app.models import Requirement
from app.services.conversation import post_message

router = APIRouter(tags=["requirements"])


class RequirementCreate(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    type: str = "functional"


def requirement_payload(row: Requirement) -> dict:
    return {
        "id": row.code,
        "record_id": str(row.id),
        "type": row.type,
        "text": row.text,
        "status": row.status,
        "version": row.version,
        "slot": row.slot,
        "slot_value": row.slot_value,
        "domain": row.domain,
        "origin": row.origin,
    }


@router.get("/projects/{project_id}/requirements")
def list_requirements(
    project_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    rows = db.scalars(select(Requirement).where(Requirement.project_id == project.id).order_by(Requirement.code)).all()
    return [requirement_payload(row) for row in rows]


@router.post("/projects/{project_id}/requirements")
def create_requirement(
    project_id: str,
    body: RequirementCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    prefix = "Add" if body.type == "functional" else "Require"
    result = post_message(db, project, f"{prefix} {body.text}")
    db.commit()
    return result
