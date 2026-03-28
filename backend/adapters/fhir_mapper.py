"""
FHIR R4 Resource Mapper — Phase 06 Interoperability.

Maps internal domain models to FHIR R4 JSON resources for interoperability
with hospital systems, health information exchanges, and regulatory reporting.

Resources mapped:
  - Patient → FHIR Patient (anonymized)
  - Case → FHIR Encounter + Condition + Observation
  - Consent → FHIR Consent
  - SymptomRecord → FHIR QuestionnaireResponse
  - DoctorProfile → FHIR Practitioner
  - DoctorResponse → FHIR Communication
  - AuditLog → FHIR AuditEvent

All resources use resource.id = internal UUID for traceability.
PHI is handled per jurisdiction rules — this mapper produces the structure,
the caller is responsible for filtering based on country permissions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_fhir_date(dt: datetime | str | None) -> str | None:
    if not dt:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


# ── Patient ──────────────────────────────────────────────────────────────

def map_patient_to_fhir(
    patient_id: str,
    country_code: str,
    language: str = "en",
    phone_hash: str = "",
) -> dict:
    """Map internal Patient to FHIR Patient resource (anonymized)."""
    return {
        "resourceType": "Patient",
        "id": patient_id,
        "meta": {
            "profile": ["http://hl7.org/fhir/StructureDefinition/Patient"],
            "lastUpdated": _utcnow_iso(),
        },
        "identifier": [
            {
                "system": "urn:who-telehealth:patient-hash",
                "value": phone_hash[:8] + "..." if phone_hash else "",
            }
        ],
        "active": True,
        "address": [
            {
                "country": country_code,
            }
        ],
        "communication": [
            {
                "language": {
                    "coding": [
                        {
                            "system": "urn:ietf:bcp:47",
                            "code": language,
                        }
                    ]
                },
                "preferred": True,
            }
        ],
    }


# ── Encounter (Case) ────────────────────────────────────────────────────

CASE_STATUS_TO_FHIR = {
    "open": "planned",
    "created": "planned",
    "active_intake": "in-progress",
    "intake_complete": "in-progress",
    "pending": "in-progress",
    "pending_review": "in-progress",
    "assigned": "in-progress",
    "in_progress": "in-progress",
    "in_review": "in-progress",
    "resolved": "finished",
    "responded": "finished",
    "closed": "finished",
    "escalated": "in-progress",
    "expired": "cancelled",
}

TRIAGE_TO_FHIR_PRIORITY = {
    "RED": {"code": "EM", "display": "Emergency"},
    "YELLOW": {"code": "UR", "display": "Urgent"},
    "GREEN": {"code": "R", "display": "Routine"},
    "BLACK": {"code": "EM", "display": "Emergency"},
}


def map_case_to_encounter(
    case_id: str,
    patient_id: str,
    status: str,
    triage_level: str = "GREEN",
    country_code: str = "",
    chief_complaint: str = "",
    opened_at: str | datetime | None = None,
    doctor_id: str | None = None,
) -> dict:
    """Map internal Case to FHIR Encounter resource."""
    fhir_status = CASE_STATUS_TO_FHIR.get(status, "unknown")
    priority = TRIAGE_TO_FHIR_PRIORITY.get(triage_level, {"code": "R", "display": "Routine"})

    encounter: dict[str, Any] = {
        "resourceType": "Encounter",
        "id": case_id,
        "meta": {
            "profile": ["http://hl7.org/fhir/StructureDefinition/Encounter"],
            "lastUpdated": _utcnow_iso(),
        },
        "status": fhir_status,
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "VR",
            "display": "Virtual",
        },
        "priority": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ActPriority",
                    **priority,
                }
            ]
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "period": {
            "start": _to_fhir_date(opened_at),
        },
    }

    if chief_complaint:
        encounter["reasonCode"] = [
            {
                "text": chief_complaint,
            }
        ]

    if doctor_id:
        encounter["participant"] = [
            {
                "type": [
                    {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/v3-ParticipationType",
                                "code": "ATND",
                                "display": "attender",
                            }
                        ]
                    }
                ],
                "individual": {"reference": f"Practitioner/{doctor_id}"},
            }
        ]

    return encounter


# ── Condition (from ICD-11 codes) ────────────────────────────────────────

def map_symptoms_to_conditions(
    case_id: str,
    patient_id: str,
    symptoms: list[str],
    icd11_codes: list[str | dict] | None = None,
) -> list[dict]:
    """Map symptoms/ICD-11 codes to FHIR Condition resources."""
    conditions = []
    codes_list = icd11_codes or []

    for i, symptom in enumerate(symptoms):
        condition: dict[str, Any] = {
            "resourceType": "Condition",
            "id": f"{case_id}-condition-{i}",
            "meta": {"lastUpdated": _utcnow_iso()},
            "clinicalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": "active",
                    }
                ]
            },
            "verificationStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                        "code": "unconfirmed",
                        "display": "Unconfirmed",
                    }
                ]
            },
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                            "code": "encounter-diagnosis",
                        }
                    ]
                }
            ],
            "subject": {"reference": f"Patient/{patient_id}"},
            "encounter": {"reference": f"Encounter/{case_id}"},
        }

        # Map ICD-11 code if available
        if i < len(codes_list):
            code_entry = codes_list[i]
            if isinstance(code_entry, str):
                condition["code"] = {
                    "coding": [
                        {
                            "system": "http://id.who.int/icd/release/11/mms",
                            "code": code_entry,
                        }
                    ],
                    "text": symptom,
                }
            elif isinstance(code_entry, dict):
                condition["code"] = {
                    "coding": [
                        {
                            "system": "http://id.who.int/icd/release/11/mms",
                            "code": code_entry.get("code", ""),
                            "display": code_entry.get("title", symptom),
                        }
                    ],
                    "text": symptom,
                }
        else:
            condition["code"] = {"text": symptom}

        conditions.append(condition)

    return conditions


# ── Observation (severity, vitals) ───────────────────────────────────────

def map_severity_to_observation(
    case_id: str,
    patient_id: str,
    severity: int,
) -> dict:
    """Map patient-reported severity to FHIR Observation."""
    return {
        "resourceType": "Observation",
        "id": f"{case_id}-severity",
        "meta": {"lastUpdated": _utcnow_iso()},
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "survey",
                        "display": "Survey",
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "72514-3",
                    "display": "Pain severity - 0-10 verbal numeric rating",
                }
            ],
            "text": "Pain Severity Score",
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "encounter": {"reference": f"Encounter/{case_id}"},
        "valueInteger": severity,
    }


# ── Consent ──────────────────────────────────────────────────────────────

def map_consent_to_fhir(
    patient_id: str,
    case_id: str,
    consent_given: bool,
    country_code: str = "",
) -> dict:
    """Map patient consent to FHIR Consent resource."""
    return {
        "resourceType": "Consent",
        "id": f"{case_id}-consent",
        "meta": {"lastUpdated": _utcnow_iso()},
        "status": "active" if consent_given else "rejected",
        "scope": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/consentscope",
                    "code": "patient-privacy",
                }
            ]
        },
        "category": [
            {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "59284-0",
                        "display": "Consent Document",
                    }
                ]
            }
        ],
        "patient": {"reference": f"Patient/{patient_id}"},
        "dateTime": _utcnow_iso(),
        "policy": [
            {
                "authority": f"urn:who-telehealth:jurisdiction:{country_code}",
            }
        ],
    }


# ── Practitioner (Doctor) ────────────────────────────────────────────────

def map_doctor_to_practitioner(
    doctor_id: str,
    full_name: str,
    specialization: str,
    country_code: str,
    license_number: str = "",
    license_verified: bool = False,
) -> dict:
    """Map internal DoctorProfile to FHIR Practitioner resource."""
    practitioner: dict[str, Any] = {
        "resourceType": "Practitioner",
        "id": doctor_id,
        "meta": {"lastUpdated": _utcnow_iso()},
        "active": True,
        "name": [{"text": full_name}],
        "address": [{"country": country_code}],
    }

    if license_number:
        practitioner["identifier"] = [
            {
                "system": f"urn:who-telehealth:license:{country_code}",
                "value": license_number,
            }
        ]

    if specialization:
        practitioner["qualification"] = [
            {
                "code": {
                    "text": specialization,
                },
            }
        ]

    return practitioner


# ── Communication (Doctor Response) ──────────────────────────────────────

def map_response_to_communication(
    response_id: str,
    case_id: str,
    doctor_id: str,
    patient_id: str,
    guidance_text: str,
    is_emergency_referral: bool = False,
) -> dict:
    """Map DoctorResponse to FHIR Communication resource."""
    return {
        "resourceType": "Communication",
        "id": response_id,
        "meta": {"lastUpdated": _utcnow_iso()},
        "status": "completed",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/communication-category",
                        "code": "notification" if is_emergency_referral else "instruction",
                    }
                ]
            }
        ],
        "priority": "urgent" if is_emergency_referral else "routine",
        "subject": {"reference": f"Patient/{patient_id}"},
        "encounter": {"reference": f"Encounter/{case_id}"},
        "sender": {"reference": f"Practitioner/{doctor_id}"},
        "payload": [
            {
                "contentString": guidance_text,
            }
        ],
    }


# ── AuditEvent ───────────────────────────────────────────────────────────

def map_audit_to_fhir(
    audit_id: int | str,
    action: str,
    actor_id: str = "",
    actor_type: str = "",
    resource_type: str = "",
    resource_id: str = "",
    timestamp: str | datetime | None = None,
) -> dict:
    """Map AuditLog entry to FHIR AuditEvent."""
    action_map = {
        "create": "C",
        "intake_complete": "U",
        "assign": "U",
        "respond": "U",
        "status_change": "U",
        "start": "R",
        "escalate": "U",
    }
    return {
        "resourceType": "AuditEvent",
        "id": str(audit_id),
        "meta": {"lastUpdated": _utcnow_iso()},
        "type": {
            "system": "http://dicom.nema.org/resources/ontology/DCM",
            "code": "110110",
            "display": "Patient Record",
        },
        "action": action_map.get(action, "E"),
        "recorded": _to_fhir_date(timestamp) or _utcnow_iso(),
        "agent": [
            {
                "type": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/extra-security-role-type",
                            "code": actor_type or "humanuser",
                        }
                    ]
                },
                "who": {"display": actor_id or "system"},
                "requestor": actor_type != "system",
            }
        ],
        "entity": [
            {
                "what": {"reference": f"{resource_type}/{resource_id}"},
                "type": {
                    "system": "http://terminology.hl7.org/CodeSystem/audit-entity-type",
                    "code": "2",
                    "display": "System Object",
                },
            }
        ] if resource_id else [],
    }


# ── Bundle builder ───────────────────────────────────────────────────────

def build_case_bundle(
    case_id: str,
    patient_id: str,
    status: str,
    triage_level: str = "GREEN",
    symptoms: list[str] | None = None,
    severity: int = 5,
    icd11_codes: list | None = None,
    country_code: str = "",
    chief_complaint: str = "",
    consent_given: bool = True,
    doctor_id: str | None = None,
    doctor_name: str = "",
    doctor_specialty: str = "",
) -> dict:
    """Build a complete FHIR Bundle for a case (for export/interop)."""
    entries = []

    # Patient
    patient = map_patient_to_fhir(patient_id, country_code)
    entries.append({"resource": patient, "fullUrl": f"urn:uuid:{patient_id}"})

    # Encounter
    encounter = map_case_to_encounter(
        case_id, patient_id, status, triage_level, country_code,
        chief_complaint, doctor_id=doctor_id,
    )
    entries.append({"resource": encounter, "fullUrl": f"urn:uuid:{case_id}"})

    # Consent
    consent = map_consent_to_fhir(patient_id, case_id, consent_given, country_code)
    entries.append({"resource": consent})

    # Conditions
    if symptoms:
        conditions = map_symptoms_to_conditions(case_id, patient_id, symptoms, icd11_codes)
        for cond in conditions:
            entries.append({"resource": cond})

    # Severity observation
    observation = map_severity_to_observation(case_id, patient_id, severity)
    entries.append({"resource": observation})

    # Practitioner
    if doctor_id:
        practitioner = map_doctor_to_practitioner(
            doctor_id, doctor_name, doctor_specialty, country_code,
        )
        entries.append({"resource": practitioner})

    return {
        "resourceType": "Bundle",
        "id": f"bundle-{case_id}",
        "meta": {"lastUpdated": _utcnow_iso()},
        "type": "collection",
        "entry": entries,
    }
