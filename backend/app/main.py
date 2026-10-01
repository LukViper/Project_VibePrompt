"""VibePrompt API. NLP and LLM calls stay on the server; the client never sees keys."""

from contextlib import asynccontextmanager
from time import time
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, chat, decisions, ideas, projects, prompts, requirements
from app.config.settings import get_settings
from app.database.base import Base
from app.database.session import engine
from app.llm.router import provider_status
from app.services.analytics import snapshot as analytics_snapshot

settings = get_settings()
_HITS: dict[str, list[float]] = {}
logger = logging.getLogger("vibeprompt")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.is_production and settings.auth_secret_is_insecure:
        raise RuntimeError(
            "Refusing to start: ENVIRONMENT=production requires a strong AUTH_SECRET "
            "(not the development default)."
        )
    if settings.auth_secret_is_insecure:
        logger.warning("AUTH_SECRET is insecure — set a strong secret before production.")
    if settings.auto_create_tables:
        import app.models  # noqa: F401

        from app.database.ensure_schema import ensure_sqlite_columns

        Base.metadata.create_all(bind=engine)
        ensure_sqlite_columns(engine)
    yield


app = FastAPI(
    title="VibePrompt",
    description="NLP-based conversational requirements engineering system for agentic AI prompt generation.",
    version="1.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(chat.router)
app.include_router(requirements.router)
app.include_router(ideas.router)
app.include_router(prompts.router)
app.include_router(decisions.router)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if not settings.rate_limit_enabled or request.url.path in {"/health", "/readyz"}:
        return await call_next(request)
    host = request.client.host if request.client else "unknown"
    now = time()
    window = [stamp for stamp in _HITS.get(host, []) if now - stamp < 60]
    if len(window) >= settings.rate_limit_per_minute:
        return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
    window.append(now)
    _HITS[host] = window
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.app_name,
        "llm_configured": settings.llm_configured,
        "providers": provider_status(),
        "environment": settings.environment,
    }


@app.get("/readyz")
def readyz():
    """Production readiness probe — fails when critical config is unsafe."""
    problems = []
    if settings.is_production and settings.auth_secret_is_insecure:
        problems.append("AUTH_SECRET insecure")
    if settings.is_production and not settings.llm_configured:
        problems.append("No LLM provider configured")
    if settings.is_production and settings.cors_origins.strip() == "*":
        problems.append("CORS_ORIGINS is wildcard")
    status = "ready" if not problems else "not_ready"
    code = 200 if not problems else 503
    return JSONResponse(
        {
            "status": status,
            "problems": problems,
            "providers": provider_status(),
            "analytics": analytics_snapshot(),
        },
        status_code=code,
    )
