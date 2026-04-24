# Phase 06 - FHIR Interoperability

## Objective
Provide FHIR R4 export adapters so internal domain models can be serialized into standards-compliant health data resources. These are read-only mapping functions - they do not modify the database.

## Files Created
- `backend/interoperability/__init__.py`
- `backend/interoperability/fhir_mappers.py`

## Resources Mapped

| Internal Concept | FHIR R4 Resource | Mapper Function |
|---|---|---|
| Patient/caller | Patient | `map_patient_to_fhir` |
| Case | Encounter | `map_encounter_to_fhir` |
| Symptom | Observation | `map_symptom_to_observation` |
| Diagnosis | Condition | `map_condition_to_fhir` |
| Consent event | Consent | `map_consent_to_fhir` |
| Doctor | Practitioner | `map_practitioner_to_fhir` |
| System action | AuditEvent | `map_audit_event` |

## Design Decisions
- Status mapping aligns internal `CaseStatusType` values to FHIR Encounter statuses (`planned`, `in-progress`, `finished`, `cancelled`).
- ICD-11 codes use the WHO ICD entity URI system (`http://id.who.int/icd/entity`).
- Observation provenance is tracked via notes (`patient_reported` vs `ai_extracted`).
- All mappers are pure functions with no side effects or database access.
