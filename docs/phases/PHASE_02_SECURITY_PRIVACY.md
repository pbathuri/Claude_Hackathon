# Phase 02 — Security & Privacy

## Objective

Establish authentication, authorization, and request traceability for the WHO telehealth backend without breaking the existing demo-mode workflow.

## Files Created / Modified

| File | Purpose |
|---|---|
| `backend/auth/__init__.py` | Package marker |
| `backend/auth/middleware.py` | Auth scaffold: demo mode, API key, doctor header, role gates |
| `backend/observability/__init__.py` | Package marker |
| `backend/observability/middleware.py` | `RequestIDMiddleware` — injects `X-Request-ID`, logs method/path/status/elapsed |
| `backend/main.py` | Added `RequestIDMiddleware` after CORS; added `DEMO_MODE` feature flag with startup warning |

## Key Design Decisions

1. **Demo-mode first**: `DEMO_MODE=1` (default) bypasses all auth so the hackathon demo keeps working. Production flips this off and supplies `API_KEYS` / doctor auth headers.
2. **Three auth schemes**: API key for service-to-service, `X-Doctor-ID` header for portal, future JWT slot. All coexist via `get_current_actor` dependency.
3. **Request IDs**: Every response carries `X-Request-ID`. Callers can supply their own; otherwise a UUID prefix is generated. This ties structured logs end-to-end across voice pipeline → backend → doctor portal.
4. **No secrets in code**: API keys loaded from environment; valid key set is comma-separated in `API_KEYS` env var.

## What This Does NOT Do (Yet)

- Real JWT validation (needs `python-jose` or equivalent)
- Rate limiting / IP throttling
- Data-at-rest encryption beyond SQLite defaults
- Audit log persistence (currently stdout only)
