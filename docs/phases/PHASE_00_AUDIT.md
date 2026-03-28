# Phase 00 — Repo Audit and Target Architecture

## Objective
Deep, file-specific audit of the entire codebase identifying data corruption risks, contract mismatches, security gaps, safety failures, dead code, and production blockers. Produces a proposed target architecture with module boundaries.

## Audit Date
2026-03-28

## Clinical Context References Applied
- WHO SMART Guidelines (machine-readable, testable guideline logic)
- AHRQ Telehealth Patient Safety (remote diagnostic limits, escalation)
- AHRQ Patient-Clinician-AI Triad (explicit role separation)
- FDA CDS Software guidance (regulatory boundary awareness)
- NIST AI RMF (governance spine for AI components)
- npj Digital Medicine symptom checker review (low accuracy evidence base)
- CHEMM START context (field triage, not routine telehealth)

---

## Critical Findings Summary

### Tier 1 — Data Corruption / Silent Harm

| ID | Finding | Files | Severity |
|----|---------|-------|----------|
| D1 | `twilio_voice._submit_twilio_case` hardcodes `severity: 5`, `duration: ""`, `body_area: ""` — clinical data loss | `backend/routers/twilio_voice.py:340-344` | CRITICAL |
| D2 | `src/main.py` uses last assistant reply as `transcript_summary` — doctor sees AI text, not patient facts | `src/main.py` submit block | CRITICAL |
| D3 | Two different priority formulas: `complete_intake` vs `caller.submit_conversation` overwrite each other | `backend/services/case_service.py`, `backend/routers/caller.py` | CRITICAL |
| D4 | Portal `fetchWithFallback` returns mock data on ANY error — production can show fictitious patients | `doctor-portal/lib/api.ts` | CRITICAL |
| D5 | `Doctor.availability` is `boolean` in TypeScript but `string` in API — dashboard status always truthy | `doctor-portal/types/index.ts` | HIGH |
| D6 | Portal assigns `doctor_id = "portal-doctor"` — may not exist server-side | `doctor-portal/app/cases/[id]/page.tsx` | HIGH |
| D7 | `triage_from_intake` defaults invalid triage to GREEN — can downgrade unsafe AI output | `backend/services/triage_service.py` | HIGH |
| D8 | `priority_queue.get_next_case_for_doctor` bypasses `assign_case` — no audit, no verification | `backend/services/priority_queue.py` | HIGH |

### Tier 2 — Security / Privacy

| ID | Finding | Files |
|----|---------|-------|
| S1 | No authentication on any backend route — entire API is public | All routers |
| S2 | No Twilio request signature validation — forged webhooks create cases | `twilio_voice.py` |
| S3 | Unsupported country falls back to Nigeria — permission bypass | `twilio_voice.py:79-87` |
| S4 | `POST /doctors/{id}/verify` unauthenticated — anyone can verify doctors | `doctors.py` |
| S5 | Image upload not bound to case/session — orphan files, no MIME validation | `caller.py:768-778` |
| S6 | Phone SHA-256 without salt — weak pseudonymization | `country_service.py` |
| S7 | No migration framework — `create_all` only | `database.py` |
| S8 | `consent_given` is boolean only — no versioning, timestamp, or channel | `models.py` |

### Tier 3 — Safety / Clinical

| ID | Finding | Files |
|----|---------|-------|
| C1 | Emergency detection is keyword-only — misses paraphrases, colloquial terms | `triage_service.py`, `graph.py` |
| C2 | Emergency keyword lists duplicated and divergent between backend and src | `triage_service.py`, `src/graph.py` |
| C3 | `start_triage` (START protocol) is never called from any intake path | `triage_service.py` |
| C4 | No "insufficient information" pathway — system always produces a triage level | All intake paths |
| C5 | No structured separation: patient-reported vs AI-extracted vs rule-output vs clinician-conclusion | Models, case_service |
| C6 | FHIR export defaults `consent_given: True` when patient missing | `cases.py` |
| C7 | BLACK triage maps to "Low" urgency in portal — dangerous semantics | `case_service.py` |
| C8 | Scheduler escalates without audit log entries | `scheduler_service.py` |

### Tier 4 — Operability

| ID | Finding | Files |
|----|---------|-------|
| O1 | No idempotency on session/start, submit, assign, respond | All mutation routes |
| O2 | All session state in-memory — lost on restart | `caller.py`, `twilio_voice.py`, `intake_service.py` |
| O3 | No request IDs or structured logging | `main.py` |
| O4 | No feature flags for KG, external APIs, demo mocks | All |
| O5 | Follow-up "sent" is stub — no actual SMS/notification | `scheduler_service.py` |
| O6 | Case status is free-form string — no DB constraint or state machine | `models.py` |

---

## Target Architecture

```
backend/
  main.py                           # App factory, middleware, startup
  config.py                         # Environment-driven settings
  database.py                       # Engine, sessions, migration support
  
  domain/                           # Domain models and enums
    models.py                       # SQLAlchemy ORM models
    enums.py                        # CaseStatus, TriageLevel, Tier, Role, UncertaintyState
    schemas.py                      # Pydantic request/response models
    events.py                       # Domain event definitions
  
  services/                         # Business logic (no HTTP concerns)
    case_service.py                 # Case lifecycle, state machine, scoring
    triage_service.py               # Layered safety engine
    country_service.py              # Permission matrix, phone parsing
    intake_service.py               # Claude intake orchestration
    icd11_service.py                # ICD-11 mapping with failure tracking
    priority_service.py             # Unified priority computation
    language_service.py             # Detection, translation, uncertainty
    notification_service.py         # SMS/notification abstraction
    audit_service.py                # Structured audit logging
  
  safety/                           # Clinical safety engine
    red_flag_rules.py               # Deterministic emergency detection
    uncertainty.py                  # Structured uncertainty states
    jurisdiction_policy.py          # Country-tier action constraints
    conversation_sufficiency.py     # Slot completeness checking
  
  auth/                             # Authentication and authorization
    middleware.py                   # Request auth middleware
    roles.py                        # Role definitions and checks
    tokens.py                       # API key / JWT management
  
  routers/                          # HTTP layer only
    caller.py                       # Caller API endpoints
    twilio_voice.py                 # Twilio webhooks
    cases.py                        # Case management
    doctors.py                      # Doctor management
    knowledge_graph.py              # KG endpoints
    health_data.py                  # WHO/ICD data
  
  knowledge_graph/                  # Self-evolving medical KG (existing)
    graph_engine.py
    navigator.py
    backpropagator.py
    doctor_matcher.py
    builder.py
    seed_data.py
    data_pipeline.py
    simulation.py
  
  interoperability/                 # FHIR adapters
    fhir_patient.py
    fhir_encounter.py
    fhir_observation.py
    fhir_condition.py
    fhir_consent.py
    fhir_practitioner.py
  
  jobs/                             # Background job abstraction
    outbox.py                       # Outbox pattern for reliable side effects
    scheduler.py                    # APScheduler wrapper
    tasks.py                        # Task definitions
  
  observability/                    # Structured logging, metrics, tracing
    logging.py
    metrics.py
    middleware.py
  
  migrations/                       # Alembic migrations
    env.py
    versions/
  
  tests/                            # Comprehensive test suite
    unit/
    contract/
    integration/
    adverse/
    fixtures/

doctor-portal/                      # Canonical doctor-facing application (Next.js)
patient-portal/                     # Lightweight patient-facing web (from telehealth-portal)
src/                                # Caller voice/SMS pipeline (LangGraph)
```

## Module Boundaries

| Module | Owns | Does NOT Own |
|--------|------|-------------|
| `domain/` | Models, enums, schemas, events | HTTP routing, business logic |
| `services/` | Business rules, state transitions, scoring | HTTP concerns, templates |
| `safety/` | Red flags, uncertainty, jurisdiction constraints | Case persistence, routing |
| `auth/` | Identity, roles, token validation | Business logic |
| `routers/` | HTTP request/response, validation | Business rules |
| `jobs/` | Side effects, retries, scheduling | Domain logic |
| `interoperability/` | FHIR mapping, terminology | Persistence, HTTP |
| `observability/` | Logging, metrics, tracing | Business logic |
| `knowledge_graph/` | Graph operations, navigation, learning | Case persistence |

---

## Files Changed
- None (audit only)

## Schema Changes
- None (audit only)

## API Contract Changes
- None (audit only)

## Backward Compatibility
- N/A

## Tests Added
- None (audit only)

## Risks Closed
- Visibility into all critical issues

## Remaining Gaps
- Everything identified above — addressed in Phases 01-08
