from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.projects import get_project
from app.auth.deps import AuthContext, get_auth_context
from app.database.session import get_db
from app.models import FinalPrompt, Specification
from app.schemas.state import migrate_state
from app.services.prompt_compiler import compilation_gate, compile_prompt
from app.services.prompt_validator import validate_and_repair, validate_prompt
from app.services.specification import build_specification
from app.services.analytics import track

router = APIRouter(tags=["prompts"])


class CompileBody(BaseModel):
    force: bool = False


class ValidateBody(BaseModel):
    content: str | None = Field(default=None, max_length=200_000)
    repair: bool = True


@router.post("/projects/{project_id}/specification")
def create_specification(
    project_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    row = build_specification(db, project)
    db.commit()
    track("specification_generated")
    return _spec_payload(row)


@router.get("/projects/{project_id}/specification")
def read_specification(
    project_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    row = db.scalars(
        select(Specification).where(Specification.project_id == project.id).order_by(Specification.version.desc())
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Specification not found")
    return _spec_payload(row)


@router.get("/projects/{project_id}/prompt/gate")
def read_compile_gate(
    project_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    return compilation_gate(migrate_state(project.state or {}))


@router.post("/projects/{project_id}/prompt")
def create_prompt(
    project_id: str,
    body: CompileBody | None = None,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    use_force = force or bool(body and body.force)
    try:
        row = compile_prompt(db, project, force=use_force)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    track("prompt_generated")
    return _prompt_payload(row)


@router.post("/projects/{project_id}/prompt/validate")
def validate_existing_prompt(
    project_id: str,
    body: ValidateBody | None = None,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    state = migrate_state(project.state or {})
    row = db.scalars(
        select(FinalPrompt).where(FinalPrompt.project_id == project.id).order_by(FinalPrompt.created_at.desc())
    ).first()
    content = (body.content if body and body.content else None) or (row.content if row else None)
    if not content:
        raise HTTPException(status_code=404, detail="No prompt to validate")
    from app.services.prompt_compiler import _normalize_from_state

    spec_row = db.scalars(
        select(Specification).where(Specification.project_id == project.id).order_by(Specification.version.desc())
    ).first()
    structured = _normalize_from_state(state, (spec_row.structured if spec_row else {}) or {})
    if body is None or body.repair:
        result = validate_and_repair(content, structured, state)
        return {"prompt": result["prompt"], "report": result["report"]}
    return {"prompt": content, "report": validate_prompt(content, structured, state)}


@router.get("/projects/{project_id}/prompt")
def read_prompt(
    project_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    row = db.scalars(
        select(FinalPrompt).where(FinalPrompt.project_id == project.id).order_by(FinalPrompt.created_at.desc())
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return _prompt_payload(row)


def _spec_payload(row: Specification) -> dict:
    return {
        "id": str(row.id),
        "version": row.version,
        "markdown": row.markdown,
        "structured": row.structured,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _prompt_payload(row: FinalPrompt) -> dict:
    details = row.details or {}
    return {
        "id": str(row.id),
        "specification_id": str(row.specification_id) if row.specification_id else None,
        "content": row.content,
        "coverage": _coverage(row),
        "validation": details.get("validation"),
        "gate": details.get("gate"),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _coverage(row: FinalPrompt) -> dict:
    ids = (row.details or {}).get("requirement_ids") or []
    present = [item for item in ids if item in row.content]
    return {
        "requirement_count": len(ids),
        "represented": len(present),
        "coverage": (len(present) / len(ids)) if ids else 1.0,
        "missing": [item for item in ids if item not in present],
    }
