# VibePrompt backend

Python, FastAPI, Pydantic, SQLAlchemy, and Alembic. PostgreSQL is the application database. spaCy, scikit-learn, Sentence Transformers, and Hugging Face Transformers implement the NLP pipeline. Gemini is an optional generation provider behind `LLMProvider`.

## Pipeline

```text
message -> preprocess -> intent -> extraction -> embedding
        -> similarity -> relationship / contradiction -> drift / scope
        -> project state version -> response
```

The conversation is not the source of truth. `app/services/project_state.py` stores stable requirement IDs (`REQ-001`) and versions. The prompt compiler reads the specification, not the raw transcript.

## Endpoints

```text
POST /projects
GET  /projects/{id}
POST /projects/{id}/messages
GET  /projects/{id}/messages
GET  /projects/{id}/state
GET  /projects/{id}/requirements
POST /projects/{id}/requirements
POST /projects/{id}/ideas
GET  /projects/{id}/ideas
POST /projects/{id}/ideas/{idea_id}/select
POST /projects/{id}/ideas/{idea_id}/reject
POST /projects/{id}/grill
POST /projects/{id}/review
POST /projects/{id}/specification
GET  /projects/{id}/specification
POST /projects/{id}/prompt
GET  /projects/{id}/prompt
```

## Security

- Put `GEMINI_API_KEY` in the environment. The Flutter app never receives it.
- Request bodies are Pydantic-validated. LLM JSON is accepted only after schema validation.
- A per-IP rate limit is on by default.
- Prompt-injection phrasing is flagged and wrapped as untrusted data. It does not replace the system role.
- Deploy behind HTTPS. This repository does not terminate TLS.

Authentication is not part of the first prototype. A `users` table is reserved for a later JWT or OAuth addition.

## Tests

```bash
pytest
```

Tests use SQLite in memory so they do not need PostgreSQL.
