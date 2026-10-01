# Security

## Principles

- Provider API keys exist only on the server (`.env`), never in Flutter.
- LLM output is never treated as privileged executable instructions.
- Projects owned by a user require matching bearer tokens.
- Guest projects are ephemeral and isolated by guest identity.

## Auth

- Guest continue: HMAC bearer token, `is_guest=true`
- Register/login: PBKDF2 password hashes + HMAC bearer token
- `AUTH_SECRET` must be strong in production (`ENVIRONMENT=production` refuses insecure defaults)
- `AUTH_TOKEN_TTL_HOURS` controls expiry

## HTTP protections

- Rate limiting (`RATE_LIMIT_ENABLED`, `RATE_LIMIT_PER_MINUTE`)
- Security headers: `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`
- HSTS enabled when `ENVIRONMENT=production`
- Prompt-injection heuristic in preprocessing

## Readiness

- `GET /health` — liveness + provider status
- `GET /readyz` — readiness; returns 503 when production config is unsafe

## Analytics privacy

Product events are allow-listed counters without message bodies (`app/services/analytics.py`).
