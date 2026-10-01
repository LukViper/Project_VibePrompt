"""Evidence attachment API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.projects import get_project
from app.auth.deps import AuthContext, get_auth_context
from app.database.session import get_db
from app.schemas.assertions import EvidenceType, VerificationStatus
from app.services.analytics import track
from app.services.evidence_service import attach_evidence

router = APIRouter(tags=["evidence"])


class EvidenceCreate(BaseModel):
    evidence_type: str = EvidenceType.USER_PROVIDED.value
    source: str = ""
    source_url: str = ""
    title: str = ""
    claim: str = Field(default="", max_length=4000)
    content: str = Field(default="", max_length=8000)
    confidence: float | None = None
    verification_status: str = VerificationStatus.UNVERIFIED.value
    attach_to_type: str | None = None
    attach_to_id: str | None = None
    reason: str = ""


@router.post("/projects/{project_id}/evidence")
def create_evidence(
    project_id: str,
    body: EvidenceCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    try:
        result = attach_evidence(
            db,
            project,
            evidence_type=body.evidence_type,
            source=body.source,
            source_url=body.source_url,
            title=body.title,
            claim=body.claim,
            content=body.content,
            confidence=body.confidence,
            verification_status=body.verification_status,
            attach_to_type=body.attach_to_type,
            attach_to_id=body.attach_to_id,
            reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    track("evidence_attached")
    return result
