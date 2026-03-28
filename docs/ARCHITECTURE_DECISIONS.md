# Architecture Decisions

## ADR-001: SQLite for Hackathon, PostgreSQL for Production

SQLite is used for the hackathon demo for simplicity. Production deployments should use PostgreSQL with Alembic migrations. The database.py engine factory already supports both via DATABASE_URL.

## ADR-002: In-Memory Session State

Session state for active calls (Twilio, web caller) is stored in-memory dicts. This means sessions are lost on restart. For production, migrate to Redis or database-backed sessions.

## ADR-003: Demo Mode as Default

DEMO_MODE=1 is the default, bypassing authentication. This must be explicitly set to 0 for production. The auth middleware logs a warning at startup when demo mode is active.

## ADR-004: Layered Safety Over Single Heuristic

Emergency detection uses 3 tiers (exact keywords, regex patterns, multilingual patterns) rather than a single keyword list. This reduces false negatives on paraphrased emergencies.

## ADR-005: Canonical State Machine

Case status transitions are validated centrally via VALID_TRANSITIONS in domain/enums.py. This prevents invalid state drift across different code paths.

## ADR-006: FHIR as Export, Not Storage

FHIR R4 adapters are export/serialization only. Internal storage uses pragmatic SQLAlchemy models. This avoids FHIR complexity in the hot path while enabling interoperability.

## ADR-007: Feature Flags Over Code Branches

Deployment behavior is controlled via environment-variable feature flags (observability/feature_flags.py) rather than code branches. This supports safe rollout and incident response.

## ADR-008: Knowledge Graph In-Memory with Persistence

The KG runs in-memory for speed but persists to JSON. On restart, it re-seeds from curated data. This is acceptable for the hackathon; production should use a graph database.

## ADR-009: Patient AI Never Diagnoses

All prompts and safety rules enforce that patient-facing AI provides guidance only. The system prompt explicitly forbids diagnosis, prescription, or legal medical judgment.

## ADR-010: Uncertainty as First-Class Concept

The UncertaintyAssessment model tracks multiple uncertainty types with severity levels. This flows through to the doctor portal as explicit warnings rather than being hidden.
