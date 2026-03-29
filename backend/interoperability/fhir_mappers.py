"""
FHIR R4 mapping adapters for health data interoperability.

Maps internal domain models to FHIR R4 resources for:
- Patient
- Encounter
- Observation (symptoms)
- Condition (diagnoses)
- Consent
- Practitioner
- QuestionnaireResponse
- AuditEvent

These are export/serialization adapters — they do not modify the database.
Designed per HL7 FHIR R4 (https://www.hl7.org/fhir/r4/summary.html).

Canonical case-bundle export for this codebase lives in
`adapters.fhir_mapper.build_case_bundle` (used by `/cases/{id}/fhir`).
This module remains for standalone resource helpers and interoperability tests.
"""
from datetime import datetime
from typing import Optional

def map_patient_to_fhir(patient_id: str, country_code: str, language: str = "en", 
                         alias: str = "", consent_given: bool = False) -> dict:
    """Map internal patient to FHIR Patient resource."""
    return {
        "resourceType": "Patient",
        "id": patient_id,
        "meta": {"profile": ["http://hl7.org/fhir/StructureDefinition/Patient"]},
        "identifier": [{"system": "urn:who-triage:patient", "value": alias or patient_id[:8]}],
        "active": True,
        "communication": [{"language": {"coding": [{"system": "urn:ietf:bcp:47", "code": language}], "text": language}, "preferred": True}],
        "address": [{"country": country_code}],
    }

def map_encounter_to_fhir(case_id: str, patient_id: str, status: str = "in-progress",
                           class_code: str = "VR", opened_at: str = "", 
                           country_code: str = "") -> dict:
    """Map internal case to FHIR Encounter resource."""
    fhir_status_map = {
        "created": "planned", "active_intake": "in-progress", "intake_complete": "in-progress",
        "pending_review": "in-progress", "assigned": "in-progress", "in_review": "in-progress",
        "responded": "finished", "closed": "finished", "expired": "cancelled",
        "escalated": "in-progress",
    }
    return {
        "resourceType": "Encounter",
        "id": case_id,
        "status": fhir_status_map.get(status, "in-progress"),
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": class_code, "display": "virtual"},
        "subject": {"reference": f"Patient/{patient_id}"},
        "period": {"start": opened_at or datetime.utcnow().isoformat()},
        "location": [{"location": {"display": country_code}}] if country_code else [],
    }

def map_symptom_to_observation(case_id: str, patient_id: str, symptom: str,
                                severity: Optional[int] = None, icd11_code: str = "",
                                provenance: str = "patient_reported") -> dict:
    """Map a symptom to FHIR Observation resource."""
    obs = {
        "resourceType": "Observation",
        "status": "preliminary" if provenance == "ai_extracted" else "registered",
        "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "survey"}]}],
        "code": {"text": symptom},
        "subject": {"reference": f"Patient/{patient_id}"},
        "encounter": {"reference": f"Encounter/{case_id}"},
        "note": [{"text": f"provenance: {provenance}"}],
    }
    if icd11_code:
        obs["code"]["coding"] = [{"system": "http://id.who.int/icd/entity", "code": icd11_code}]
    if severity is not None:
        obs["valueInteger"] = severity
    return obs

def map_condition_to_fhir(case_id: str, patient_id: str, diagnosis: str,
                           icd11_code: str = "", clinician_id: str = "",
                           verification: str = "provisional") -> dict:
    """Map a diagnosis to FHIR Condition resource."""
    cond = {
        "resourceType": "Condition",
        "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
        "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": verification}]},
        "code": {"text": diagnosis},
        "subject": {"reference": f"Patient/{patient_id}"},
        "encounter": {"reference": f"Encounter/{case_id}"},
    }
    if icd11_code:
        cond["code"]["coding"] = [{"system": "http://id.who.int/icd/entity", "code": icd11_code}]
    if clinician_id:
        cond["asserter"] = {"reference": f"Practitioner/{clinician_id}"}
    return cond

def map_consent_to_fhir(patient_id: str, consent_type: str = "data_processing",
                         accepted: bool = True, timestamp: str = "",
                         language: str = "en") -> dict:
    """Map consent event to FHIR Consent resource."""
    return {
        "resourceType": "Consent",
        "status": "active" if accepted else "rejected",
        "scope": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/consentscope", "code": "patient-privacy"}]},
        "category": [{"coding": [{"system": "http://loinc.org", "code": "59284-0", "display": "Consent"}]}],
        "patient": {"reference": f"Patient/{patient_id}"},
        "dateTime": timestamp or datetime.utcnow().isoformat(),
        "policy": [{"uri": f"urn:who-triage:consent:{consent_type}:v1.0"}],
    }

def map_practitioner_to_fhir(doctor_id: str, name: str, specialization: str,
                              country_code: str, license_number: str = "",
                              verified: bool = False) -> dict:
    """Map doctor to FHIR Practitioner resource."""
    return {
        "resourceType": "Practitioner",
        "id": doctor_id,
        "active": True,
        "name": [{"text": name}],
        "qualification": [{"code": {"text": specialization}}],
        "identifier": [{"system": f"urn:who-triage:license:{country_code}", "value": license_number}] if license_number else [],
    }

def map_audit_event(action: str, actor_id: str, case_id: str = "",
                     outcome: str = "0", detail: str = "") -> dict:
    """Map to FHIR AuditEvent resource."""
    return {
        "resourceType": "AuditEvent",
        "type": {"system": "http://dicom.nema.org/resources/ontology/DCM", "code": "110110", "display": "Patient Record"},
        "action": action[0].upper() if action else "R",
        "recorded": datetime.utcnow().isoformat(),
        "outcome": outcome,
        "agent": [{"who": {"display": actor_id}, "requestor": True}],
        "entity": [{"what": {"reference": f"Encounter/{case_id}"}, "detail": [{"type": "description", "valueString": detail}]}] if case_id else [],
    }
