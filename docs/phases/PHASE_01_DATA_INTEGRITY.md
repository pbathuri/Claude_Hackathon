# Phase 01 — Data Integrity

## Objective

Ensure every piece of clinical data flowing through the platform is typed, validated, traceable, and auditable. Replace stringly-typed constants with canonical enums so invalid values are caught at the boundary, not in production logs.

## Files Changed

| File | Change |
|---|---|
| `backend/domain/__init__.py` | New package marker |
| `backend/domain/enums.py` | Canonical enums (`CaseStatus`, `TriageLevel`, `UrgencyDisplay`, `ActorType`, `UncertaintyLevel`, `ConsentType`, `SourceChannel`, `ExtractionProvenance`) and valid state-transition map |
| `backend/domain/schemas.py` | Pydantic models (`ConversationTurn`, `ExtractedFact`, `ClinicalExtraction`, `ScoreBreakdown`, `ConsentEvent`) |
| `backend/domain/events.py` | Domain event types for audit/event-bus (`CaseStatusChanged`, `EmergencyDetected`, `TriageCompleted`, `DoctorResponseSubmitted`) |
| `backend/domain/models_ext.py` | Extended SQLAlchemy tables (`conversation_turns`, `consent_events`, `clinical_extractions`, `outbox_jobs`) |
| `backend/database.py` | Imports extended models so `init_db()` creates the new tables |

## Key Decisions

1. **str-Enums** — All enums inherit `(str, Enum)` so they serialize cleanly in JSON/Pydantic without custom encoders while still being type-checkable.
2. **ExtractedFact provenance** — Every clinical fact carries `provenance` and `confidence` so downstream consumers (doctors, auditors) know whether a value was patient-reported, AI-extracted, or clinician-authored.
3. **Consent as first-class records** — `ConsentEventRecord` is a separate table (not a boolean flag on Patient) to support multi-version consent, per-channel tracking, and GDPR/data-law audit trails.
4. **Outbox pattern** — `OutboxJob` enables reliable async work (notifications, follow-ups) without losing tasks on crashes; retry semantics are built into the schema.
