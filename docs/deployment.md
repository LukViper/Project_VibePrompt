# Deployment

## Local (SQLite)

```bash
cd backend
source .venv/bin/activate
# .env at repo root
uvicorn app.main:app --reload --port 8000
```

```bash
cd mobile_web
flutter run -d chrome
```

## Docker (Postgres + API)

```bash
cp .env.example .env
# set GEMINI_API_KEY or OPENAI_API_KEY and AUTH_SECRET
docker compose up --build
```

## Production checklist

1. `ENVIRONMENT=production`
2. Strong unique `AUTH_SECRET`
3. Explicit `CORS_ORIGINS` (not `*`)
4. Configure at least one LLM provider (`GEMINI_API_KEY` and/or `OPENAI_API_KEY`)
5. Prefer Postgres `DATABASE_URL` (compose includes pgvector)
6. Set `AUTO_CREATE_TABLES=false` and run Alembic migrations
7. Confirm `GET /readyz` returns 200
8. Terminate TLS at the reverse proxy; HSTS header is set by the API in production mode

## Provider selection

| `LLM_PROVIDER` | Behavior |
|---|---|
| `auto` | Gemini if configured, else OpenAI |
| `gemini` | Force Gemini |
| `openai` | Force OpenAI-compatible endpoint |

## Observability

- `/health`, `/readyz`
- Privacy-conscious event counters via analytics snapshot on `/readyz`
