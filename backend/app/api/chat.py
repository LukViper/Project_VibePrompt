from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.projects import get_project
from app.auth.deps import AuthContext, get_auth_context
from app.database.session import get_db
from app.models import Message
from app.services.analytics import track
from app.services.conversation import post_message

router = APIRouter(tags=["chat"])


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


@router.post("/projects/{project_id}/messages")
def create_message(
    project_id: str,
    body: MessageCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    result = post_message(db, project, body.content)
    if (result.get("state") or {}).get("conflicts"):
        open_conflicts = [
            c for c in (result["state"].get("conflicts") or []) if c.get("status") == "open"
        ]
        if open_conflicts:
            track("conflict_detected")
    if result.get("ideas"):
        track("idea_refined")
    db.commit()
    return result


@router.post("/projects/{project_id}/messages/stream")
def stream_message(
    project_id: str,
    body: MessageCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Persist the turn, then stream the assistant reply text progressively.

    Full NLP/state updates still run server-side before streaming begins so
    ProjectState remains the source of truth.
    """
    project = get_project(project_id, db, auth)
    result = post_message(db, project, body.content)
    db.commit()
    assistant = (result.get("assistant_message") or {}).get("content") or ""

    def event_stream():
        # Emit structured prelude so clients can refresh state before tokens.
        yield f"event: meta\ndata: { _json_meta(result) }\n\n"
        if not assistant:
            yield "event: done\ndata: {}\n\n"
            return
        # Progressive chunks (provider-native stream when available; else chunked).
        for chunk in _chunk_text(assistant):
            yield f"event: token\ndata: { _escape(chunk) }\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/projects/{project_id}/messages")
def list_messages(
    project_id: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    project = get_project(project_id, db, auth)
    if project.conversation is None:
        return []
    rows = db.scalars(
        select(Message).where(Message.conversation_id == project.conversation.id).order_by(Message.created_at)
    ).all()
    return [
        {
            "id": str(row.id),
            "role": row.role,
            "content": row.content,
            "intent": row.intent,
            "analysis": row.analysis,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


def _chunk_text(text: str, size: int = 48):
    for index in range(0, len(text), size):
        yield text[index : index + size]


def _escape(text: str) -> str:
    import json

    return json.dumps(text)


def _json_meta(result: dict) -> str:
    import json

    return json.dumps(
        {
            "stage": result.get("stage"),
            "intent": result.get("intent"),
            "user_message": result.get("user_message"),
            "assistant_message": result.get("assistant_message"),
            "state": result.get("state"),
            "ideas": result.get("ideas") or [],
        },
        default=str,
    )
