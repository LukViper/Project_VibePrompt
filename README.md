# VibePrompt

VibePrompt is an evidence-tracked conversational requirements-engineering system for coding agents. It maintains auditable ProjectState (requirements, claims, assumptions, evidence, decisions, Grill attacks, trace links), validates it before compilation, and emits an agent-executable prompt as a compiled artifact.

The **specification and reasoning workflow** are the product. The final prompt is a compiled artifact.

## Documentation

| File | Purpose |
|---|---|
| [plan.md](plan.md) | Live build plan vs Master Spec |
| [progress.md](progress.md) | What was actually implemented and verified |
| [docs/product_requirements.md](docs/product_requirements.md) | Product contract |
| [docs/architecture.md](docs/architecture.md) | As-built vs target architecture |
| [docs/ARCHITECTURE_AUDIT.md](docs/ARCHITECTURE_AUDIT.md) | Pre-transformation repository audit (baseline) |
| [docs/GRILL.md](docs/GRILL.md) | Adversarial Grill attacks, responses, blocking |
| [docs/TRACEABILITY.md](docs/TRACEABILITY.md) | TraceLink, lineage, validation |
| [docs/EVALUATION.md](docs/EVALUATION.md) | RQ1–RQ5 experiments, metrics, limitations |
| [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md) | Seeds, configs, how to re-run |
| [docs/RESEARCH_READINESS_REPORT.md](docs/RESEARCH_READINESS_REPORT.md) | Honest readiness checklist |
| [docs/decisions.md](docs/decisions.md) | Architecture decision records |
| [docs/security.md](docs/security.md) | Auth, secrets, readiness |
| [docs/deployment.md](docs/deployment.md) | Local/Docker/production checklist |
| [docs/research_sources.md](docs/research_sources.md) | External sources and licensing notes |
| [docs/literature_review.md](docs/literature_review.md) | NLP research background |

## Layout

```text
backend/          FastAPI, NLP, ProjectState, prompt compiler
mobile_web/       Flutter client (web / Android / iOS)
datasets/         Annotated evaluation data
evaluation/       Metric scripts
docs/             Architecture, decisions, sources
plan.md
progress.md
```

## Run the backend

```bash
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-nlp.txt   # optional NLP stack
python -m spacy download en_core_web_sm
uvicorn app.main:app --reload
```

Set `GEMINI_API_KEY` in `.env` for generation. Classification and similarity do not require it.

## Run the client

```bash
cd mobile_web
flutter pub get
flutter run -d chrome
# or: flutter run -d web-server --web-hostname 0.0.0.0 --web-port 8080
```

## Docker

```bash
cp .env.example .env
docker compose up --build
```

## Current phase

Phase 0 (audit + documentation) is complete. See `progress.md` for the next action (Phase 1 — Core Data Model).
