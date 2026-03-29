# WHO Health Access — Complete Technical Guide

> **Single Source of Truth** for the WHO-Aligned AI Telehealth Platform.
> Last updated: March 29, 2026

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Repository Structure](#3-repository-structure)
4. [Backend (FastAPI)](#4-backend-fastapi)
   - 4.1 Entry Point and Lifecycle
   - 4.2 Configuration
   - 4.3 Database Models
   - 4.4 Routers (API Endpoints)
   - 4.5 Services
   - 4.6 Knowledge Graph
   - 4.7 Safety Engine
   - 4.8 Multilingual System
5. [Doctor Portal (Next.js)](#5-doctor-portal-nextjs)
6. [Web Caller (caller.html)](#6-web-caller-callerhtml)
7. [Data Flow: User to Doctor](#7-data-flow-user-to-doctor)
8. [Data Flow: Doctor Back to Patient](#8-data-flow-doctor-back-to-patient)
9. [External APIs and Integrations](#9-external-apis-and-integrations)
10. [Deployment](#10-deployment)
11. [Environment Variables](#11-environment-variables)
12. [What Is Working](#12-what-is-working)
13. [What Is Missing / To Build](#13-what-is-missing--to-build)
14. [Testing](#14-testing)
15. [Key Design Decisions](#15-key-design-decisions)

---

## 1. Project Overview

This platform provides AI-powered telehealth for underserved populations, aligned with WHO guidelines. A patient calls in (via web browser or Twilio phone call), describes symptoms in any supported language, and the system:

1. Detects their language and translates to English for clinical processing
2. Runs symptoms through a medical Knowledge Graph (Physarum-inspired)
3. Detects emergencies via a layered safety engine
4. Generates empathetic, contextual follow-up questions via Claude AI
5. Translates the response back to the patient's language
6. Speaks the response via ElevenLabs TTS (multilingual)
7. On completion, triages the case (RED/YELLOW/GREEN), maps to ICD-11 codes
8. Submits the case to a priority queue for doctor review
9. Doctors see cases on a real-time dashboard with KG insights, triage breakdown, and explainability layers
10. Doctors respond with guidance, which triggers follow-up scheduling

**Target markets**: India, Philippines, Kenya, Nigeria (with support for 12+ languages).

**Live URLs**:
- Backend: `https://claude-hackathon-u86l.onrender.com`
- Doctor Portal: `https://doctor-portal-flax.vercel.app`
- Web Caller: `https://claude-hackathon-u86l.onrender.com/call`
- API Docs: `https://claude-hackathon-u86l.onrender.com/docs`

---

## 2. Architecture

### High-Level System Diagram

```
Patient (Phone/Web)
       │
       ├─── Web Caller (caller.html)
       │         │
       │         ├── Browser Web Speech API (STT)
       │         ├── OpenAI Whisper API (multilingual STT)
       │         └── ElevenLabs API (multilingual TTS)
       │
       ├─── Twilio Voice (phone calls)
       │         │
       │         ├── Twilio <Gather> (STT)
       │         └── ElevenLabs via <Play> URL (TTS)
       │
       ▼
   FastAPI Backend (Render)
       │
       ├── Language Service (detect + translate via Claude Haiku)
       ├── Knowledge Graph (Physarum-inspired, in-memory + JSON persist)
       ├── Claude Sonnet (conversational AI)
       ├── Safety Engine (red flag detection, 4 layers)
       ├── ICD-11 Mapping (NLM API)
       ├── Triage Engine (START protocol)
       ├── Priority Queue (score-based)
       ├── PostgreSQL / SQLite (Supabase in prod)
       └── Redis (session store, TTS cache, STT segments)
       │
       ▼
   Doctor Portal (Vercel, Next.js)
       │
       ├── Dashboard (stats, charts, live case counts via SSE)
       ├── Case Queue (filterable, sortable, real-time refresh)
       ├── Case Detail (assign, respond, KG insights, explainability)
       └── Knowledge Graph Explorer
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Backend | Python 3.13 + FastAPI | API server, business logic |
| Frontend (Doctor) | Next.js 14 + TypeScript + Tailwind CSS | Doctor dashboard |
| Frontend (Caller) | Vanilla HTML/JS | Patient-facing web caller |
| Database | PostgreSQL (Supabase) / SQLite (dev) | Persistent storage |
| Cache | Redis (RedisLabs) | Sessions, TTS cache, STT segments |
| ORM | SQLAlchemy 2.0 + Alembic | DB models and migrations |
| AI (Conversation) | Anthropic Claude Sonnet | Symptom intake conversation |
| AI (Translation) | Anthropic Claude Haiku | Fast medical translation |
| STT | OpenAI Whisper API | Multilingual speech-to-text |
| TTS | ElevenLabs (eleven_multilingual_v2) | Natural multilingual speech |
| Telephony | Twilio Voice | Inbound phone calls |
| ICD-11 | NLM Clinical Tables API | Symptom-to-code mapping |
| WHO Data | WHO GHO API | Country health indicators |
| Monitoring | Sentry (optional) | Error tracking |
| CI/CD | GitHub Actions | Automated testing |
| Hosting (Backend) | Render | Python web service |
| Hosting (Frontend) | Vercel | Next.js deployment |

---

## 3. Repository Structure

```
Claude_Hackathon/
├── backend/                    # FastAPI application
│   ├── main.py                 # App entry point, lifespan, CORS, router registration
│   ├── config.py               # All env vars, constants, model configs
│   ├── database.py             # SQLAlchemy engine, session, init_db()
│   ├── models.py               # ORM models (Patient, Case, DoctorProfile, etc.)
│   ├── db_types.py             # JSON-compatible column type helper
│   ├── render.yaml             # Render deployment config
│   ├── requirements.txt        # Python dependencies
│   ├── Procfile                # Process command for Render
│   ├── alembic.ini             # Alembic migration config
│   ├── alembic/                # DB migration scripts
│   │   └── versions/           # Migration files (0001_initial, 0002_detected_country)
│   ├── routers/                # API route handlers
│   │   ├── caller.py           # Web caller API (session, ai-turn, submit, STT, TTS)
│   │   ├── twilio_voice.py     # Twilio webhook handlers (voice, gather)
│   │   ├── cases.py            # Case CRUD, queue, SSE stream, FHIR export
│   │   ├── doctors.py          # Doctor profiles
│   │   ├── intake.py           # Direct intake API
│   │   ├── health_data.py      # WHO GHO data
│   │   └── knowledge_graph.py  # KG navigation, backprop, stats, search
│   ├── services/               # Business logic layer
│   │   ├── case_service.py     # Case lifecycle (create → assign → resolve → close)
│   │   ├── country_service.py  # Phone parsing, country detection, permissions
│   │   ├── language_service.py # Language detection, translation (Claude)
│   │   ├── triage_service.py   # START triage, emergency detection, scoring
│   │   ├── icd11_service.py    # ICD-11 lookup via NLM API
│   │   ├── session_store.py    # Redis-backed session/cache (TTS, STT, Twilio)
│   │   ├── browser_stt_store.py# Browser Web Speech segment persistence
│   │   ├── navigator_store.py  # KG navigator per-case cache
│   │   ├── priority_queue.py   # Priority score computation
│   │   ├── scheduler_service.py# APScheduler (expiration, follow-ups, purge)
│   │   ├── explainability.py   # Doctor-facing explainability layers
│   │   └── who_service.py      # WHO GHO API client
│   ├── knowledge_graph/        # Medical Knowledge Graph engine
│   │   ├── graph_engine.py     # Core graph: nodes, edges, Physarum conductivity
│   │   ├── navigator.py        # ConversationNavigator (per-case state machine)
│   │   ├── builder.py          # Graph construction from seed data
│   │   ├── seed_data.py        # Medical seed data (symptoms, conditions, edges)
│   │   ├── backpropagator.py   # Doctor feedback → graph weight updates
│   │   ├── doctor_matcher.py   # Match doctors to cases via graph
│   │   ├── data_pipeline.py    # Optional scraper enrichment
│   │   ├── scraper.py          # Web scraper for medical data
│   │   └── simulation.py       # Graph simulation utilities
│   ├── safety/                 # Clinical safety engine
│   │   ├── red_flag_rules.py   # Layered emergency detection (4 tiers)
│   │   ├── jurisdiction_policy.py # Country tier capabilities
│   │   ├── conversation_guard.py  # Conversation safety rails
│   │   ├── conversation_sufficiency.py # Intake completeness check
│   │   └── uncertainty.py      # Uncertainty quantification
│   ├── security/
│   │   └── twilio_signature.py # Twilio webhook validation
│   ├── auth/
│   │   └── middleware.py       # Auth middleware (demo mode / API key / JWT stub)
│   ├── adapters/
│   │   └── fhir_mapper.py     # FHIR R4 Bundle export
│   ├── schemas/
│   │   └── intake.py          # IntakeData Pydantic schema
│   ├── domain/
│   │   ├── enums.py           # CaseStatus FSM, TriageLevel, UrgencyDisplay
│   │   ├── models_ext.py      # ConversationTurn, ConsentEvent, Extraction tables
│   │   ├── events.py          # Domain event types
│   │   └── schemas.py         # Domain Pydantic schemas
│   ├── observability/
│   │   ├── middleware.py      # Request ID middleware
│   │   └── feature_flags.py   # Feature flag management
│   ├── static/
│   │   └── caller.html        # Web caller UI (patient-facing)
│   └── tests/                 # Test suite
│       ├── unit/              # Unit tests (enums, FHIR, safety)
│       ├── contract/          # API contract tests
│       └── fixtures/          # Golden test data
│
├── doctor-portal/              # Next.js doctor dashboard
│   ├── app/
│   │   ├── page.tsx           # Dashboard (stats, charts, recent cases)
│   │   ├── layout.tsx         # Root layout with sidebar
│   │   ├── globals.css        # Tailwind + custom styles
│   │   ├── cases/
│   │   │   ├── page.tsx       # Case queue (filterable, sortable)
│   │   │   └── [id]/page.tsx  # Case detail (assign, respond, KG panel)
│   │   ├── knowledge-graph/
│   │   │   └── page.tsx       # KG explorer
│   │   └── login/
│   │       └── page.tsx       # Login page (stub)
│   ├── components/            # Reusable UI components
│   │   ├── Sidebar.tsx        # Navigation sidebar
│   │   ├── KGInsightsPanel.tsx # Knowledge Graph insights
│   │   ├── ComplianceBanner.tsx # Clinical advisory banner
│   │   ├── UrgencyBadge.tsx   # RED/YELLOW/GREEN badge
│   │   ├── CountryIndicator.tsx # Country flag + tier
│   │   ├── PriorityBar.tsx    # Visual priority score bar
│   │   ├── RedFlagBadge.tsx   # Red flag indicator pills
│   │   ├── MiniGraph.tsx      # Mini KG visualization
│   │   ├── LanguageBanner.tsx # Translation risk indicator
│   │   ├── PatientEvidencePanel.tsx # Patient's own words
│   │   ├── ExtractionPanel.tsx # Structured fact extraction
│   │   ├── SafetyPanel.tsx    # Safety trigger display
│   │   ├── AmbiguityPanel.tsx # Unresolved items
│   │   ├── StatsCard.tsx      # Dashboard stat cards
│   │   ├── PieChart.tsx       # Urgency distribution
│   │   ├── BarChart.tsx       # Country distribution
│   │   └── LoadingSpinner.tsx # Loading indicator
│   ├── lib/
│   │   ├── api.ts             # Backend API client (fetch + fallback)
│   │   ├── mock-data.ts       # Dev-mode mock data
│   │   └── portal-headers.ts  # Doctor identity header
│   ├── types/
│   │   └── index.ts           # TypeScript interfaces (Case, Doctor, KG, etc.)
│   ├── next.config.mjs        # Next.js config (API URL default)
│   ├── tailwind.config.ts     # Tailwind theme (WHO colors, triage colors)
│   └── .env.production        # Production API URL
│
├── docs/                       # Documentation
│   ├── phases/                 # Phase-by-phase build docs (00-08)
│   ├── ARCHITECTURE_DECISIONS.md
│   ├── DEPLOY.md
│   ├── RUNBOOK.md
│   ├── RISK_REGISTER.md
│   └── WORKFLOW_MAPS.md
│
├── .github/workflows/ci.yml   # GitHub Actions CI
├── Dockerfile                  # Container build
└── README.md                   # Project README
```

---

## 4. Backend (FastAPI)

### 4.1 Entry Point and Lifecycle

**File**: `backend/main.py`

On startup (`lifespan`):
1. `init_db()` — creates tables (SQLite) or expects Alembic (PostgreSQL)
2. `seed_country_permissions(db)` — inserts country permission matrix (NG, IN, PH, KE, ZZ)
3. `start_scheduler()` — APScheduler for case expiration, follow-ups, data purge
4. `init_knowledge_graph()` — builds medical KG from seed data, loads persisted graph

Registered routers:
- `/intake` — direct structured intake
- `/cases` — case CRUD, queue, SSE, FHIR export
- `/doctors` — doctor profiles
- `/health` — WHO GHO data
- `/caller` — web caller API (session, ai-turn, submit, STT, TTS)
- `/kg` — knowledge graph navigation, backprop, stats
- `/twilio` — Twilio voice webhooks

Special routes:
- `GET /` — service info
- `GET /call` — redirects to `static/caller.html`
- `GET /health-check` — liveness probe with dependency status

### 4.2 Configuration

**File**: `backend/config.py`

Every configurable value is loaded from environment variables with sensible defaults:

| Variable | Default | Purpose |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | (empty) | Claude AI for conversation + translation |
| `OPENAI_API_KEY` | (empty) | OpenAI Whisper for multilingual STT |
| `ELEVENLABS_API_KEY` | (empty) | ElevenLabs for TTS |
| `ELEVENLABS_VOICE_ID` | `EXAVITQu4vr4xnSDxMaL` | Default voice (Sarah) |
| `ELEVENLABS_MODEL_ID` | `eleven_multilingual_v2` | Multilingual TTS model |
| `DATABASE_URL` | `sqlite:///./telehealth.db` | DB connection string |
| `REDIS_URL` | (empty) | Redis for sessions/cache |
| `TWILIO_ACCOUNT_SID` | (empty) | Twilio account |
| `TWILIO_AUTH_TOKEN` | (empty) | Twilio webhook validation |
| `TWILIO_PHONE_NUMBER` | (empty) | Twilio number |
| `CONVERSATION_MODEL` | `claude-sonnet-4-20250514` | Primary conversation model |
| `TRANSLATION_MODEL` | `claude-haiku-4-5-20241022` | Translation model |
| `MAX_TURNS_BEFORE_COMPLETE` | `8` | Auto-complete after N turns |
| `MIN_SYMPTOMS_FOR_COMPLETE` | `5` | Auto-complete at N symptoms |
| `STALE_TURNS_FOR_COMPLETE` | `2` | Complete if 2 turns with no new symptoms |
| `GRAPH_CONFIDENCE_THRESHOLD` | `0.7` | Auto-complete when KG confidence exceeds |
| `DEMO_MODE` | `1` | Bypass authentication |
| `ENABLE_KNOWLEDGE_GRAPH` | `true` | Toggle KG system |

### 4.3 Database Models

**File**: `backend/models.py`

| Model | Table | Key Fields | Purpose |
|-------|-------|------------|---------|
| `Patient` | `patients` | `id`, `phone_hash`, `country_code`, `language`, `consent_given` | Patient records (phone hashed for privacy) |
| `Case` | `cases` | `id`, `patient_id`, `status`, `triage_level`, `intake_data` (JSON), `icd11_codes` (JSON), `priority_score`, `conversation_log` (JSON), `triage_breakdown` (JSON), `detected_language` | Core case record with full lifecycle |
| `DoctorProfile` | `doctor_profiles` | `id`, `full_name`, `specialization`, `country_code`, `languages` (JSON), `availability` | Doctor information |
| `SymptomRecord` | `symptom_records` | `case_id`, `symptoms_json`, `icd11_codes`, `severity`, `transcript_text` | Structured symptom data per case |
| `DoctorResponse` | `doctor_responses` | `case_id`, `doctor_id`, `guidance_text`, `is_emergency_referral` | Doctor's clinical guidance |
| `FollowUpSchedule` | `followup_schedules` | `case_id`, `scheduled_at`, `channel`, `status`, `patient_reply` | 24h/48h follow-up tracking |
| `CountryPermission` | `country_permissions` | `country_code` PK, `country_tier`, `permission_tier`, capability flags, `disclaimer_text` | WHO permission matrix |
| `AuditLog` | `audit_log` | `actor_id`, `action`, `resource_type`, `resource_id`, `details` | Append-only audit trail |
| `ImageUpload` | `image_uploads` | `case_id`, `file_path`, `content_type` | Patient image uploads |

Extended models (`domain/models_ext.py`):
- `ConversationTurnRecord` — per-turn transcript with language metadata
- `ConsentEventRecord` — consent audit events
- `ClinicalExtractionRecord` — structured extraction per case
- `OutboxJob` — async job queue for background work

**Case Status State Machine** (from `models.py`):
```
open → intake_complete → pending → assigned → in_progress → resolved → closed
                                  ↘ escalated (timeout or manual)
                                  ↗ (re-queue after expiry)
```

### 4.4 Routers (API Endpoints)

#### 4.4.1 Caller API — `routers/caller.py` (prefix: `/caller`)

This is the primary integration surface for the web caller.

| Method | Path | Purpose | Request Body | Response |
|--------|------|---------|-------------|----------|
| `POST` | `/caller/session/start` | Start new session: parse phone, detect country, create patient + case, build disclosure | `{phone_number, language}` | `{session_id, case_id, country_code, country_tier, verbal_disclosure, ...}` |
| `POST` | `/caller/session/consent` | Record patient consent for capability disclaimer | `{case_id, consent_given}` | `{status, consent_timestamp}` |
| `POST` | `/caller/ai-turn` | Process one conversation turn (the core loop) | `{case_id, user_message, turn_number, collected_symptoms, message_history, language}` | `{ai_message, detected_symptoms, all_symptoms_so_far, is_emergency, should_complete, ...}` |
| `POST` | `/caller/session/submit` | Submit completed conversation for triage + ICD-11 + doctor queue | `{case_id, symptoms, message_history, transcript_summary, severity, duration, ...}` | `{case_id, triage_level, priority_score, icd11_codes, ...}` |
| `GET` | `/caller/session/{case_id}` | Check case status + doctor response | — | Full case data with doctor response if available |
| `GET` | `/caller/disclosure/{cc}` | Get verbal disclosure script for a country | — | `{verbal_disclosure_script, physician_status_bar, capability_card}` |
| `POST` | `/caller/emergency-check` | Quick emergency keyword check | `{text}` | `{is_emergency, red_flags, action}` |
| `POST` | `/caller/stt` | OpenAI Whisper STT (multipart audio upload) | `file` (audio), `language` (optional) | `{text, language}` |
| `POST` | `/caller/tts` | ElevenLabs TTS | `{text}` | Audio stream (audio/mpeg) |
| `POST` | `/caller/browser-stt/push` | Persist browser Web Speech segment | `{case_id, text, is_final, lang}` | `{segment_count, full_text}` |
| `GET` | `/caller/browser-stt/{case_id}` | Get merged browser STT transcript | — | `{segments, full_text}` |
| `DELETE` | `/caller/browser-stt/{case_id}` | Clear STT segments after submit | — | `{status}` |
| `POST` | `/caller/upload-image` | Upload patient image | `file` (image) | `{url, filename}` |

**`/caller/ai-turn` is the most important endpoint.** Its internal pipeline:
1. Detect language from user message (script heuristics + phrase hints)
2. Translate to English if non-English (Claude Haiku)
3. Extract symptoms via KG fuzzy match or keyword list
4. Merge with previously collected symptoms (deduplicate)
5. Run KG navigator: activate symptoms, spread activation, get conditions/questions
6. Run safety engine: 4-layer red flag detection
7. Check completion criteria (symptom count, KG confidence, turn count, stale turns)
8. Extract severity (1-10), duration, body area from English text
9. Generate Claude response (with KG context, anti-repetition, intake progress)
10. Track AI message for anti-repetition across turns
11. Translate response back to user's language
12. Generate clinical summary on completion

#### 4.4.2 Twilio Voice — `routers/twilio_voice.py` (prefix: `/twilio`)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/twilio/voice` | Incoming call webhook — creates case, plays disclosure, opens first Gather |
| `POST` | `/twilio/gather` | Speech result callback — runs same pipeline as `/caller/ai-turn` |
| `GET` | `/twilio/tts-audio` | ElevenLabs audio for Twilio `<Play>` (with Redis cache) |
| `GET` | `/twilio/ready-tone` | Short sine wave "ready" tone WAV for `<Gather>` |

The Twilio path uses TwiML XML responses (`<Gather>`, `<Play>`, `<Say>`, `<Hangup>`). After each turn, the AI response is spoken via ElevenLabs `<Play>` URL, followed by a ready tone inside the next `<Gather>`.

#### 4.4.3 Cases — `routers/cases.py` (prefix: `/cases`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/cases/` | List cases (filterable by status, country, triage) |
| `GET` | `/cases/queue` | Priority queue snapshot |
| `GET` | `/cases/patient-cases` | **Doctor portal endpoint** — all cases in frontend shape |
| `GET` | `/cases/patient-cases/{id}` | **Doctor portal endpoint** — single case detail |
| `GET` | `/cases/stream` | **SSE** — real-time pending case counts |
| `GET` | `/cases/{id}` | Internal case detail |
| `POST` | `/cases/{id}/assign` | Assign doctor to case |
| `POST` | `/cases/{id}/start` | Doctor starts working on case |
| `POST` | `/cases/{id}/respond` | **Doctor submits guidance** — resolves case, schedules follow-ups |
| `POST` | `/cases/{id}/escalate` | Manual escalation to RED |
| `POST` | `/cases/{id}/close` | Close resolved case |
| `POST` | `/cases/{id}/followup-reply` | Patient follow-up reply (1=better, 2=same, 3=worse) |
| `GET` | `/cases/{id}/audit` | Audit trail for case |
| `GET` | `/cases/{id}/fhir` | FHIR R4 Bundle export |

#### 4.4.4 Knowledge Graph — `routers/knowledge_graph.py` (prefix: `/kg`)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/kg/navigate` | Navigate symptoms through KG |
| `POST` | `/kg/query` | Quick symptom query |
| `POST` | `/kg/backpropagate` | Doctor feedback updates graph weights |
| `POST` | `/kg/match-doctors` | Match doctors to case via KG |
| `GET` | `/kg/stats` | Graph statistics (nodes, edges, learned) |
| `GET` | `/kg/hottest-paths` | Most-traversed graph paths |
| `GET` | `/kg/subgraph/{node}` | Subgraph extraction |
| `GET` | `/kg/conditions/{symptom}` | Conditions for a symptom |
| `GET` | `/kg/search` | Search nodes by name |
| `POST` | `/kg/enrich` | Trigger scraper enrichment |
| `POST` | `/kg/decay` | Force global conductivity decay |

#### 4.4.5 Other Routers

- `/doctors/` — CRUD for doctor profiles
- `/health/` — WHO GHO health indicators by country
- `/intake/` — Direct structured intake (bypasses conversation)

### 4.5 Services

#### `case_service.py` — Case Lifecycle

The heart of the data pipeline. Key functions:

- `create_case(db, patient_id, country_code)` — creates case in `open` status with patient alias
- `complete_intake(db, case_id, intake_data, icd11_codes)` — normalizes intake, computes triage, sets priority score, creates SymptomRecord
- `move_to_pending(db, case_id)` — transitions to `pending` (ready for doctor)
- `assign_case(db, case_id, doctor_id)` — assigns doctor
- `submit_response(db, case_id, doctor_id, guidance_text, ...)` — resolves case, creates DoctorResponse
- `schedule_followup(db, case_id, hours)` — creates FollowUpSchedule
- `get_case_for_frontend(db, case_id)` — **maps DB case to doctor portal JSON shape**

The frontend contract shape (returned by `get_case_for_frontend`):
```json
{
  "caseId": "uuid",
  "patientAlias": "PT-1234",
  "country": "India",
  "countryTier": 1,
  "urgency": "High",
  "symptomSummary": "headache and fever for 3 days",
  "painScore": 7,
  "symptomDuration": "3 days",
  "bodyArea": "head",
  "imageUrls": [],
  "consentGiven": true,
  "submittedAt": "2026-03-29T12:00:00Z",
  "aiStructuredNotes": "Patient reports headache, fever...",
  "redFlagIndicators": ["high fever"],
  "priorityScore": 70,
  "status": "pending_review",
  "kgInsights": { "conditions": [...], "recommendedSpecialty": "..." },
  "triageBreakdown": { "base_score": 50, "severity_score": 20, ... },
  "explainability": { "language_banner": {...}, "patient_evidence": [...], ... },
  "conversationLog": { "turns": [...] }
}
```

#### `country_service.py` — Country Detection

Uses the `phonenumbers` library to parse E.164 phone numbers and detect country codes. Maps to the `CountryPermission` matrix.

Seeded countries with tiers:
- **Tier 1** (IN - India): Full diagnosis, treatment; no prescribing
- **Tier 2** (NG - Nigeria): Diagnosis + treatment; no prescribing
- **Tier 3** (PH - Philippines, KE - Kenya): Diagnosis; treatment managed locally
- **Tier 4** (ZZ - Unknown): Guidance only

#### `language_service.py` — Multilingual System

Supports 12 languages: English, Spanish, French, Hindi, Portuguese, Arabic, Swahili, Yoruba, Hausa, Chinese, German, Filipino.

Detection strategy (fast to slow):
1. Script-based heuristic (Devanagari → Hindi, Arabic script → Arabic, CJK → Chinese)
2. Phrase-hint lookup (common medical terms in each language)
3. Default to English

Translation uses Claude Haiku for speed. Disclosure translation uses Claude Sonnet for accuracy (legal text).

Each language has metadata:
- `whisper`: Whisper language code
- `twilio_voice`: Polly voice name (e.g., `Polly.Aditi` for Hindi)
- `twilio_lang`: Twilio STT language code
- `greeting`: Localized greeting text
- `emergency_notice`: Localized emergency message

#### `triage_service.py` — Triage and Scoring

Implements START protocol-inspired triage:

**Emergency detection** uses substring matching against `_EMERGENCY_PHRASES` (e.g., "chest pain", "can't breathe", "suicidal") and regex patterns with word boundaries.

**Priority scoring** (`build_triage_breakdown`) components:
- Base score: RED=100, YELLOW=50, GREEN=10
- Severity: `(severity - 3) * 5`
- Red flags: `count * 15`
- Symptom count bonus
- Duration: acute > chronic
- KG confidence: `confidence * 10`
- Country tier: {1:10, 2:20, 3:30, 4:40}

#### `session_store.py` — Redis Session Management

Redis-backed with in-memory fallback for local dev. Stores:
- Twilio call sessions (case_id, turn, symptoms, message_history, language)
- Case language (per case_id)
- Stale turn counter (for completion heuristics)
- AI message history (for anti-repetition)
- TTS audio cache (keyed by text hash)
- KG navigator snapshots

#### `explainability.py` — Doctor-Facing Explainability

Builds 5 layers for each case:
1. **Language Banner** — detected language, translation confidence, interpreter recommendation
2. **Patient Evidence** — original patient utterances with translations
3. **Extraction Layer** — structured facts with source attribution (patient-reported, AI-extracted, KG-inferred)
4. **Safety Layer** — triage triggers, red flags, KG confidence
5. **Ambiguity Block** — unresolved items, translation artifacts

### 4.6 Knowledge Graph

**Design**: Physarum-inspired (slime mold network optimization). Edges have `conductivity` that strengthens with use and decays over time, causing the graph to naturally evolve toward frequently-traversed diagnostic paths.

**Node types**: SYMPTOM, CONDITION, BODY_SYSTEM, SPECIALTY, RISK_FACTOR, MEDICATION, QUESTION, DEMOGRAPHIC

**Edge types**: PRESENTS_WITH, INDICATES, LOCATED_IN, TREATED_BY, RISK_FOR, MANAGED_WITH, FOLLOW_UP, CONTRAINDICATES, DEMOGRAPHIC_RISK

**Key classes**:
- `MedicalKnowledgeGraph` — the graph structure with nodes, edges, adjacency lists, Physarum flow mechanics
- `ConversationNavigator` — per-conversation state machine that activates symptoms, spreads activation, ranks follow-up questions via chemotaxis scoring, surfaces likely conditions
- `GraphBackpropagator` — updates graph weights based on doctor feedback (confirmed diagnosis reinforces paths)

**Learning loop**: When a doctor confirms a diagnosis and submits a response, `backpropagate` reinforces the edges from the patient's symptoms to the confirmed condition, and the condition to the doctor's specialty. Over time, the graph learns which symptom patterns lead to which diagnoses.

### 4.7 Safety Engine

**File**: `safety/red_flag_rules.py`

4-tier layered detection:

1. **Tier 1 — Exact Keywords (IMMEDIATE)**: "chest pain", "can't breathe", "suicidal thoughts", "stroke symptoms", "severe bleeding", "anaphylaxis" → triggers emergency, stops conversation
2. **Tier 2 — English Regex Patterns**: Compiled regex with word boundaries for nuanced matching (e.g., "seizure" but not "anti-seizure medication")
3. **Tier 3 — Multilingual Patterns**: Language-specific emergency phrases in Spanish, French, Hindi, Arabic, Swahili, Chinese, Hausa
4. **Tier 4 — Knowledge Graph**: If KG activates an emergency condition with score > 0.75, adds a WARNING flag (never IMMEDIATE — prevents false positives from statistical hypotheses)

`RedFlagResult` contains:
- `is_emergency` (bool) — only true for IMMEDIATE severity
- `severity` — IMMEDIATE / URGENT / WARNING
- `flags` — list of detected flag details
- `emergency_numbers` — country-specific numbers

**Critical design decision**: KG flags are WARNING only, never IMMEDIATE. This prevents the graph from false-triggering emergencies (e.g., headache + fever ≠ meningitis emergency). Only explicit patient statements trigger IMMEDIATE.

### 4.8 Multilingual System

The multilingual pipeline:

```
User speaks Hindi → Browser/Whisper STT → Hindi text
                                            ↓
                                    detect_language() → "hi"
                                            ↓
                                    translate_to_english() via Claude Haiku
                                            ↓
                                    English text for clinical processing
                                    (KG traversal, symptom extraction, safety)
                                            ↓
                                    _generate_claude_response() → English response
                                            ↓
                                    translate_from_english() via Claude Haiku
                                            ↓
                                    Hindi response text
                                            ↓
                                    ElevenLabs TTS (eleven_multilingual_v2)
                                            ↓
                                    User hears Hindi speech
```

**Web caller language selection**: The dropdown auto-selects language based on country (India → Hindi, Philippines → Filipino, etc.). Users can manually switch. The selected language is sent as `language` parameter to `/caller/ai-turn`.

**Whisper STT**: When the user presses the Whisper record button, audio is captured and sent to `/caller/stt` which forwards to `OpenAI Whisper API` with optional language hint. Whisper auto-detects language if no hint is provided.

---

## 5. Doctor Portal (Next.js)

**File**: `doctor-portal/`

### Pages

| Route | File | Purpose |
|-------|------|---------|
| `/` | `app/page.tsx` | Dashboard: stats cards, urgency pie chart, country bar chart, recent cases |
| `/cases` | `app/cases/page.tsx` | Case queue: search, filter (urgency, country, status), sort (priority, time, pain), 5s auto-refresh |
| `/cases/[id]` | `app/cases/[id]/page.tsx` | Case detail: patient info, symptoms, red flags, AI notes, KG insights panel, doctor response form |
| `/knowledge-graph` | `app/knowledge-graph/page.tsx` | KG explorer: stats, hottest paths, symptom search |
| `/login` | `app/login/page.tsx` | Login (stub) |

### API Client (`lib/api.ts`)

All backend calls go through `fetchWithFallback` (graceful degradation to empty data) or `fetchStrict` (throws on error). Uses `NEXT_PUBLIC_API_URL` environment variable.

Key functions:
- `getCases()` → `GET /cases/patient-cases`
- `getCase(id)` → `GET /cases/patient-cases/{id}`
- `assignDoctor(caseId)` → `POST /cases/{id}/assign`
- `submitResponse(caseId, payload)` → `POST /cases/{id}/respond`
- `backpropagateCase(caseId, diagnosis, specialty)` → `POST /kg/backpropagate`
- `navigateKG(symptoms)` → `POST /kg/navigate`
- `getKGStats()` → `GET /kg/stats`
- `subscribeCasesStream(onEvent)` → SSE `GET /cases/stream`

### TypeScript Types (`types/index.ts`)

Key interfaces:
- `Case` — matches backend `get_case_for_frontend()` shape exactly
- `Doctor` — doctor profile
- `KGNavigationResult` — conditions, specialty, follow-up questions, graph paths
- `TriageBreakdown` — explainable triage score components
- `CaseExplainability` — language banner, patient evidence, extraction, safety, ambiguity

---

## 6. Web Caller (caller.html)

**File**: `backend/static/caller.html`

Single-page application served at `/call`. Features:

### UI Flow
1. **Dialer Screen**: Country selector (12 countries), phone number input, "Call" button
2. **Connecting Screen**: Animated ring while starting session
3. **Call Screen**: Chat-style message area, speaking indicator, input bar with:
   - Language dropdown (12 languages, auto-selects from country)
   - Camera button (image upload)
   - Text input
   - Whisper record button (multilingual STT)
   - Browser mic button (Web Speech API)
   - Send button
4. **Emergency Overlay**: Red flash with country-specific emergency number
5. **Summary Card**: Case ID, triage level, symptoms, urgency, link to doctor portal

### Audio System
- `beep(freq, dur)` — short Web Audio API tone
- `readyTone()` — ascending two-note tone (660Hz → 880Hz over 1.8s)
- After every AI response (both ElevenLabs and browser fallback), a two-tone beep signals "your turn"
- No spoken "go ahead" or "I'm listening" prompts — clean beep tones only

### Speech-to-Text
Two STT methods:
1. **Browser Web Speech API** (mic button): Uses `webkitSpeechRecognition` with language from dropdown. Real-time interim results shown in preview. Final results sent to `/caller/ai-turn`.
2. **OpenAI Whisper** (Whisper button): Records audio via `MediaRecorder`, sends to `/caller/stt` as multipart. Better for non-English languages.

### Text-to-Speech
ElevenLabs primary with browser `SpeechSynthesis` fallback. The `eleven_multilingual_v2` model speaks any supported language natively.

### Multilingual Greeting
On call start, the greeting is spoken in the user's selected language:
```javascript
const greetings = {
  en: 'Hello! Please describe your symptoms.',
  es: '¡Hola! Por favor describa sus síntomas.',
  hi: 'नमस्ते! कृपया अपने लक्षण बताएं।',
  // ... 9 more languages
};
```

---

## 7. Data Flow: User to Doctor

### Step-by-step: Web Caller Path

```
1. Patient opens /call, selects country + language, enters phone, clicks "Call"
   └─► POST /caller/session/start
       ├── parse_phone() → detect country (phonenumbers library)
       ├── check_teleconsult_allowed() → verify permissions
       ├── get_or_create_patient() → create/find patient record
       ├── create_case() → Case in "open" status
       └── Returns: {case_id, country_code, verbal_disclosure, ...}

2. Frontend auto-accepts consent
   └─► POST /caller/session/consent
       └── Records ConsentEventRecord in DB

3. Patient speaks/types a message (e.g., "मुझे सिरदर्द है" in Hindi)
   └─► POST /caller/ai-turn
       ├── detect_language("मुझे सिरदर्द है") → "hi"
       ├── translate_to_english() → "I have a headache" (Claude Haiku)
       ├── _extract_symptoms_from_text() → ["headache"] (KG or keyword)
       ├── KG navigator: activate "headache", spread to conditions
       ├── Safety engine: no red flags
       ├── Completion check: turn 1, 1 symptom → continue
       ├── _generate_claude_response() → "I understand you have a headache.
       │   How long have you been experiencing this?" (Claude Sonnet)
       ├── translate_from_english() → Hindi response (Claude Haiku)
       └── Returns: {ai_message: "मैं समझता हूं...", detected_symptoms: ["headache"], ...}

4. Frontend speaks response via ElevenLabs TTS
   └─► POST /caller/tts {text: "मैं समझता हूं..."}
       └── ElevenLabs API → audio/mpeg stream → plays in browser
       └── Beep tone after audio ends

5. ... (Repeat turns 3-4 until should_complete = true) ...

6. Frontend receives should_complete=true, waits 3s, then submits
   └─► POST /caller/session/submit
       ├── detect_red_flags() on all text
       ├── Determine triage: RED/YELLOW/GREEN
       ├── map_intake_to_icd11() → ICD-11 codes via NLM API
       ├── KG enrichment: specialty recommendation
       ├── build_triage_breakdown() → explainable priority score
       ├── complete_intake() → sets Case.intake_data, triage, priority
       ├── Store conversation_log on Case
       ├── move_to_pending() → Case.status = "pending"
       └── Returns: {case_id, triage_level, priority_score, icd11_codes, ...}

7. Case appears in doctor portal (auto-refresh every 5s)
   └── Doctor portal: GET /cases/patient-cases
       └── Returns all cases in frontend contract shape
```

### Step-by-step: Twilio Voice Path

```
1. Patient dials Twilio number
   └─► POST /twilio/voice (Twilio webhook)
       ├── Parse caller number → detect country
       ├── Create patient + case
       ├── Build verbal disclosure
       ├── Return TwiML: <Say> disclosure + <Gather> with ready tone

2. Twilio captures speech → POST /twilio/gather
   ├── Detect language from first utterance
   ├── Translate to English
   ├── Same KG + safety + Claude pipeline as web caller
   ├── Translate response back
   ├── Return TwiML: <Play> ElevenLabs audio + <Gather> ready tone

3. ... (Repeat until should_complete or is_emergency) ...

4. On completion:
   ├── _submit_twilio_case() → same triage + ICD-11 pipeline
   ├── Generate clinical note via Claude
   ├── Store conversation_log
   ├── Return TwiML: <Say> completion message + <Hangup>
```

---

## 8. Data Flow: Doctor Back to Patient

```
1. Doctor sees case in portal → clicks "Assign to Me"
   └─► POST /cases/{id}/assign {doctor_id: "portal-doctor"}
       └── Case.status = "assigned"

2. Doctor reviews: symptoms, triage breakdown, KG insights, conversation log

3. Doctor writes guidance + optional diagnosis → clicks "Submit Response"
   └─► POST /cases/{id}/respond
       ├── Creates DoctorResponse record
       ├── Case.status = "resolved"
       └── schedule_followup() at 24h and 48h

4. If diagnosis provided → POST /kg/backpropagate
   ├── Reinforces graph edges from patient symptoms → confirmed condition
   ├── Updates specialty associations
   └── Graph learns for future cases

5. Follow-up scheduling (APScheduler):
   ├── At 24h: FollowUpSchedule.status = "sent" (ready for patient check-in)
   └── At 48h: Second follow-up

6. Patient can check status:
   └─► GET /caller/session/{case_id}
       └── Returns case status + doctor response if available
```

---

## 9. External APIs and Integrations

### Anthropic Claude API

| Usage | Model | Max Tokens | Purpose |
|-------|-------|------------|---------|
| Conversation | `claude-sonnet-4-20250514` | 350 | Symptom intake conversation |
| Translation | `claude-haiku-4-5-20241022` | 500-600 | Fast medical translation |
| Disclosure | `claude-sonnet-4-20250514` | 800 | Legal text translation (higher quality) |
| Clinical note | `claude-sonnet-4-20250514` | 200 | Physician handoff summary |
| Clinical summary | `claude-sonnet-4-20250514` | 100 | One-sentence symptom summary |
| HuggingFace fallback | `mistralai/Mistral-7B-Instruct-v0.3` | 150 | Secondary LLM if Claude fails |

### OpenAI Whisper API
- Endpoint: `POST https://api.openai.com/v1/audio/transcriptions`
- Model: `whisper-1`
- Max file size: 25MB
- Used by: `/caller/stt`

### ElevenLabs TTS API
- Endpoint: `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream`
- Model: `eleven_multilingual_v2`
- Voice: `EXAVITQu4vr4xnSDxMaL` (Sarah)
- Used by: `/caller/tts` (web) and `/twilio/tts-audio` (phone)
- Caching: Redis-backed for Twilio path (keyed by SHA-256 of text)

### NLM Clinical Tables API (ICD-11)
- Endpoint: `GET https://clinicaltables.nlm.nih.gov/api/icd11_codes/v3/search`
- No authentication required
- Returns: ICD-11 codes matching symptom terms
- Used by: `services/icd11_service.py`

### WHO GHO API
- Endpoint: `https://ghoapi.azureedge.net/api`
- Indicators: physicians per 10k, hospital beds, UHC coverage index
- Used by: `routers/health_data.py`

### Twilio Voice
- Webhooks: `/twilio/voice` (incoming), `/twilio/gather` (speech result)
- TwiML: `<Gather>`, `<Play>`, `<Say>`, `<Hangup>`
- Signature validation: `security/twilio_signature.py`

---

## 10. Deployment

### Backend (Render)

**File**: `backend/render.yaml`

```yaml
services:
  - type: web
    runtime: python
    name: who-triage-backend
    rootDir: backend
    buildCommand: pip install -r requirements.txt && python -m alembic upgrade head
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
```

Required Render environment variables (set in dashboard, `sync: false`):
- `DATABASE_URL` — PostgreSQL connection string (Supabase)
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `ELEVENLABS_API_KEY`
- `REDIS_URL`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_API_KEY_SECRET`
- `PUBLIC_BASE_URL` — for Twilio webhook URL construction

### Doctor Portal (Vercel)

- **Framework**: Next.js 14
- **URL**: `https://doctor-portal-flax.vercel.app`
- **Environment**: `NEXT_PUBLIC_API_URL=https://claude-hackathon-u86l.onrender.com`
- **CORS**: Backend allows `https://doctor-portal-flax.vercel.app`

### Database (Supabase)

- PostgreSQL with connection pooling
- Alembic migrations run on deploy (`alembic upgrade head`)
- Local dev uses SQLite (`sqlite:///./telehealth.db`)

### Redis (RedisLabs)

- Used for: session store, TTS cache, browser STT segments, KG navigator snapshots
- Falls back to in-memory dict if `REDIS_URL` not set

---

## 11. Environment Variables

### Backend `.env` (all required for full functionality)

```env
# AI
ANTHROPIC_API_KEY=sk-ant-...          # Claude conversation + translation
OPENAI_API_KEY=sk-proj-...            # Whisper multilingual STT

# Voice
ELEVENLABS_API_KEY=...                # ElevenLabs TTS
ELEVENLABS_VOICE_ID=EXAVITQu4vr4xnSDxMaL
ELEVENLABS_MODEL_ID=eleven_multilingual_v2

# Telephony
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...
TWILIO_API_KEY_SECRET=...

# Data
DATABASE_URL=postgresql://...         # Supabase Postgres
REDIS_URL=redis://...                 # RedisLabs

# Ops
DEMO_MODE=1                           # Bypass auth for demo
SKIP_PIPELINE_ENRICHMENT=1            # Skip scraper on startup
ENABLE_KNOWLEDGE_GRAPH=true           # Enable KG system
```

### Doctor Portal `.env.production`

```env
NEXT_PUBLIC_API_URL=https://claude-hackathon-u86l.onrender.com
```

---

## 12. What Is Working

| Feature | Status | Notes |
|---------|--------|-------|
| Web caller UI | Working | 12 countries, 12 languages, camera, two STT methods |
| Claude AI conversation | Working | KG-guided, anti-repetition, intake progression |
| Language detection | Working | Script heuristics + phrase hints for 12 languages |
| Translation (to/from English) | Working | Claude Haiku for speed |
| ElevenLabs TTS (multilingual) | Working | `eleven_multilingual_v2` speaks any language |
| OpenAI Whisper STT | Working | Multilingual audio transcription |
| Browser Web Speech API | Working | Real-time for supported languages |
| Knowledge Graph | Working | Physarum-inspired, 100+ nodes, seed data |
| KG-guided follow-up questions | Working | Chemotaxis scoring for question relevance |
| Safety engine (4 layers) | Working | Keyword, regex, multilingual, KG-aware |
| Emergency detection | Working | Country-specific numbers, immediate response |
| Country detection | Working | `phonenumbers` library, 4 target markets |
| Verbal disclosure (per country tier) | Working | Capability-based, translatable |
| ICD-11 mapping | Working | NLM API, async |
| Triage scoring | Working | START-inspired, explainable breakdown |
| Case submission | Working | Full pipeline: triage + ICD-11 + KG enrichment |
| Doctor portal dashboard | Working | Live stats, charts, auto-refresh |
| Case queue | Working | Filterable, sortable, real-time |
| Case detail view | Working | Full patient data, KG panel, compliance banner |
| Doctor assign + respond | Working | Creates DoctorResponse, schedules follow-ups |
| KG backpropagation | Working | Doctor diagnosis reinforces graph |
| FHIR R4 export | Working | Full Bundle with Patient, Encounter, Conditions |
| SSE live updates | Working | Real-time case count push |
| Audit trail | Working | Append-only log of all actions |
| Twilio voice webhooks | Working | Full voice call flow with ElevenLabs TTS |
| Redis session management | Working | With in-memory fallback |
| Beep tones (no "go ahead") | Working | Clean audio signals between turns |
| Auto-language from country | Working | India → Hindi, Philippines → Filipino, etc. |

---

## 13. What Is Missing / To Build

### High Priority

| Item | Description | Where to Add |
|------|-------------|-------------|
| **Doctor authentication** | Real login, JWT tokens, role-based access | `auth/middleware.py`, doctor portal login page |
| **Patient notification** | SMS/email when doctor responds | `services/scheduler_service.py` + Twilio SMS |
| **Follow-up mechanism** | Patient receives and replies to follow-up checks | New endpoint + Twilio SMS integration |
| **Rate limiting** | Prevent API abuse on key endpoints | Add `slowapi` middleware to `main.py` |
| **E2E test suite** | Automated tests for full flow | `tests/` directory |
| **CI pipeline fix** | Remove `|| true` from pytest/ruff steps | `.github/workflows/ci.yml` |

### Medium Priority

| Item | Description | Where to Add |
|------|-------------|-------------|
| **TTS caching for web caller** | Redis cache for web TTS (currently only Twilio path) | `routers/caller.py` `/tts` endpoint |
| **WebSocket audio streaming** | Replace HTTP polling with real-time audio | New WebSocket endpoint |
| **Conversation transcript viewer** | Doctor sees full conversation in portal | `doctor-portal/app/cases/[id]/page.tsx` |
| **Image analysis** | AI analysis of uploaded patient images | New service using Claude Vision |
| **Multi-doctor assignment** | Queue-based auto-assignment to available doctors | `services/priority_queue.py` |
| **Doctor-to-doctor referral** | Specialist referral within platform | New workflow |
| **Analytics dashboard** | System-wide metrics (response times, triage distribution) | New portal page |

### Low Priority / Future

| Item | Description |
|------|-------------|
| **Sesame CSM / Pipecat** | Self-hosted voice for lower latency (requires GPU) |
| **HL7 FHIR push** | Push FHIR bundles to hospital EHR systems |
| **WhatsApp integration** | Alternative messaging channel |
| **Offline mode** | Service worker + local storage for unreliable connections |
| **Doctor mobile app** | React Native companion app |
| **Prescription workflow** | For Tier 1 countries where allowed |
| **Data residency enforcement** | Per-country data storage compliance |

### Known Issues

1. **Status enum mismatch**: `models.py` uses lowercase strings (`open`, `pending`) while `domain/enums.py` uses `CaseStatus` enum with different values (`CREATED`, `PENDING_REVIEW`). The router-level code uses the `models.py` strings. This should be unified.

2. **`language_service.py` hardcodes model**: Uses `"claude-haiku-4-5-20241022"` instead of `TRANSLATION_MODEL` from config. Should read from config.

3. **Browser STT language coverage**: Web Speech API doesn't support Swahili, Yoruba, Hausa — only Whisper STT works for these. The UI should guide users to the Whisper button for unsupported languages.

4. **Stale Twilio signature validation**: `SKIP_TWILIO_SIGNATURE` is set to `"0"` in render.yaml but webhook URL may not be configured. Need `PUBLIC_BASE_URL` set correctly.

---

## 14. Testing

### Test Files

| File | Coverage |
|------|----------|
| `tests/unit/test_enums_and_state_machine.py` | CaseStatus FSM transitions |
| `tests/unit/test_safety_engine.py` | Red flag detection, emergency keywords |
| `tests/unit/test_fhir_mappers.py` | FHIR R4 Bundle generation |
| `tests/contract/test_api_contracts.py` | API endpoint contract shapes |
| `tests/test_phases.py` | Phase-specific integration tests |
| `tests/test_language_and_kg_e2e.py` | Language + KG end-to-end |
| `tests/test_voice_conversation_state.py` | Twilio voice state machine |
| `test_e2e.py` | Full end-to-end flow |

### Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

### CI Pipeline

**File**: `.github/workflows/ci.yml`

Runs on push/PR to main. Steps: install deps, ruff lint, pytest.

---

## 15. Key Design Decisions

### Why ElevenLabs over Sesame CSM or Pipecat?

**Decision**: Keep ElevenLabs for TTS.

**Reasoning**:
- Sesame CSM requires CUDA GPU (Render is CPU-only)
- CSM is English-only; ElevenLabs `eleven_multilingual_v2` supports all target languages natively
- ElevenLabs provides consistent voice identity (important for patient trust)
- Production-proven, low latency (<500ms for short utterances)
- No infrastructure changes needed

**Future path**: If GPU hosting becomes available, Sesame CSM or NVIDIA PersonaPlex could be added behind a TTS provider abstraction layer.

### Why Physarum-inspired Knowledge Graph?

**Decision**: Custom graph engine with Physarum conductivity model.

**Reasoning**:
- Real-time navigation without database queries
- Self-optimizing: frequently-traversed paths strengthen naturally
- Doctor feedback (backpropagation) creates a learning loop
- Chemotaxis-based question ranking surfaces the most diagnostically useful questions first
- In-memory with JSON persistence = fast and simple

### Why Claude for Translation instead of Google Translate?

**Decision**: Claude Haiku for all translation.

**Reasoning**:
- Medical terminology requires domain understanding
- Claude preserves clinical nuance better than generic translation APIs
- Single vendor for all AI = simpler ops
- Claude Haiku is fast (~200ms) and cheap
- Legal/consent text uses Claude Sonnet for higher accuracy

### Why Turn-Based Architecture (not streaming)?

**Decision**: HTTP request/response turns, not WebSocket streaming.

**Reasoning**:
- Compatible with Twilio's `<Gather>` / `<Play>` model
- Simpler to implement, debug, and deploy
- Works on Render's free tier (no persistent connections needed for core flow)
- SSE used only for doctor portal live updates (lightweight)

### Why Beep Tones instead of Spoken Prompts?

**Decision**: Short audio beep after AI speaks, not "Go ahead, I'm listening."

**Reasoning**:
- Spoken prompts add 1-2 seconds of unnecessary latency
- Beeps are language-agnostic (work for all 12 languages)
- Creates a more natural phone-call rhythm
- Reduces ElevenLabs API calls (cost saving)
- Patients quickly learn the beep = "your turn" pattern

### Why Redis for Sessions instead of Database?

**Decision**: Redis for ephemeral conversation state, PostgreSQL for persistent records.

**Reasoning**:
- Conversation turns, stale counters, and AI message history are ephemeral
- Redis TTLs automatically clean up abandoned sessions
- TTS cache in Redis avoids re-generating identical audio
- Falls back to in-memory dict for local dev (no Redis dependency)
- Persistent data (cases, patients, responses) goes to PostgreSQL

---

## Appendix: Quick Reference for Developers

### Starting Local Development

```bash
# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env  # Fill in API keys
uvicorn main:app --reload --port 8000

# Doctor Portal
cd doctor-portal
npm install
npm run dev  # Starts on localhost:3001
```

### Key Files to Modify

| Task | Files |
|------|-------|
| Add new language | `services/language_service.py` (SUPPORTED_LANGUAGES), `static/caller.html` (dropdowns) |
| Add new country | `services/country_service.py` (SEED_COUNTRIES), `services/language_service.py` (EMERGENCY_NUMBERS) |
| Modify conversation behavior | `routers/caller.py` (_generate_claude_response system prompt) |
| Change triage scoring | `services/triage_service.py` (build_triage_breakdown) |
| Add new safety rule | `safety/red_flag_rules.py` (EMERGENCY_KEYWORDS or EMERGENCY_PATTERNS) |
| Modify doctor portal UI | `doctor-portal/components/` and `doctor-portal/app/` |
| Add new API endpoint | Create in `routers/`, register in `main.py` |
| Add KG nodes/edges | `knowledge_graph/seed_data.py` |
| Modify case data shape | `services/case_service.py` (get_case_for_frontend), `doctor-portal/types/index.ts` |

### API Testing (curl examples)

```bash
# Start session
curl -X POST http://localhost:8000/caller/session/start \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+911234567890"}'

# AI turn
curl -X POST http://localhost:8000/caller/ai-turn \
  -H "Content-Type: application/json" \
  -d '{"case_id": "...", "user_message": "I have a headache", "turn_number": 1, "language": "en"}'

# Submit case
curl -X POST http://localhost:8000/caller/session/submit \
  -H "Content-Type: application/json" \
  -d '{"case_id": "...", "symptoms": ["headache", "fever"], "severity": 6}'

# Health check
curl http://localhost:8000/health-check

# Get cases (doctor portal)
curl http://localhost:8000/cases/patient-cases
```

---

*This document is the single source of truth for the WHO Health Access platform. Update it as the system evolves.*
