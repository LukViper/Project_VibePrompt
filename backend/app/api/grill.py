"""Grill attack generation, listing, and response APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.projects import get_project
from app.auth.deps import AuthContext, get_auth_context
from app.database.session import get_db
from app.schemas.grill_entities import GrillResolutionType
from app.schemas.state import migrate_state
from app.services.analytics import track
from app.services.capability_harness import CapabilityKind, gate_capability, run_grill
from app.services.grill_session import (
    get_next_grill_attack,
    list_grill_attacks,
    respond_to_grill_attack,
)

router = APIRouter(tags=["grill"])


class GrillRespondBody(BaseModel):
    response_text: str = Field(min_length=1, max_length=8000)
    resolution_type: str = GrillResolutionType.RESOLVED.value
    create_requirement: dict | None = None
    create_evidence: dict | None = None
    create_decision: dict | None = None
    create_claim: dict | None = None
    mutate: bool = True


@router.post("/projects/{project_id}/grill")
def start_grill(
    project_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    gate_capability(project.state or {}, CapabilityKind.GRILL).raise_if_blocked()
    track("grill_started")
    report = run_grill(db, project)
    if isinstance(report, dict) and report.get("blocked"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "capability_gated",
                "reason": "missing_project_to_grill",
                "guidance": report.get("response"),
                "provenance": report.get("provenance") or {},
            },
        )
    db.commit()
    track("grill_completed")
    return report


@router.get("/projects/{project_id}/grill")
def read_grill(
    project_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    state = migrate_state(project.state or {})
    return list_grill_attacks(state)


@router.get("/projects/{project_id}/grill/next")
def read_next_grill_attack(
    project_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    state = migrate_state(project.state or {})
    return {"next": get_next_grill_attack(state)}


@router.post("/projects/{project_id}/grill/{attack_id}/respond")
def respond_grill(
    project_id: str,
    attack_id: str,
    body: GrillRespondBody,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    try:
        result = respond_to_grill_attack(
            db,
            project,
            attack_id,
            response_text=body.response_text,
            resolution_type=body.resolution_type,
            create_requirement=body.create_requirement,
            create_evidence=body.create_evidence,
            create_decision=body.create_decision,
            create_claim=body.create_claim,
            mutate=body.mutate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    track("grill_response")
    return result
