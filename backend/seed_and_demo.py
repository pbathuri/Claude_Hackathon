"""
Seed data and end-to-end demo script.
Run: python seed_and_demo.py
Demonstrates the full pipeline: phone parsing → permission check → case creation
→ intake → triage → ICD-11 → priority queue → doctor assignment → response → follow-up.
"""
import sys
import json
from datetime import datetime, timezone

from database import init_db, SessionLocal
from models import DoctorProfile, Case, CountryPermission
from services.country_service import (
    parse_phone, check_teleconsult_allowed, get_or_create_patient,
    seed_country_permissions,
)
from services.triage_service import (
    start_triage, PhoneAssessment, triage_from_intake, get_base_score,
    check_emergency_keywords,
)
from services.priority_queue import compute_priority_score, get_queue_snapshot
from services.case_service import (
    create_case, complete_intake, move_to_pending, assign_case,
    start_case, submit_response, schedule_followup, get_case_with_details,
)
from services.icd11_service import search_icd11_sync


def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def seed_doctors(db):
    """Seed sample doctors for the three target countries."""
    doctors = [
        {
            "full_name": "Dr. Adebayo Okafor",
            "email": "adebayo@healthng.org",
            "specialization": "general",
            "country_code": "NG",
            "languages": ["en", "yo"],
            "license_number": "MDCN-12345",
            "medical_school": "University of Lagos",
            "availability": "online",
            "verified": True,
            "license_verified": True,
        },
        {
            "full_name": "Dr. Priya Sharma",
            "email": "priya@healthin.org",
            "specialization": "general",
            "country_code": "IN",
            "languages": ["en", "hi"],
            "license_number": "MCI-67890",
            "medical_school": "AIIMS New Delhi",
            "availability": "online",
            "verified": True,
            "license_verified": True,
        },
        {
            "full_name": "Dr. Maria Santos",
            "email": "maria@healthph.org",
            "specialization": "dermatology",
            "country_code": "PH",
            "languages": ["en", "tl"],
            "license_number": "PRC-11111",
            "medical_school": "University of the Philippines Manila",
            "availability": "online",
            "verified": True,
            "license_verified": True,
        },
        {
            "full_name": "Dr. James Mwangi",
            "email": "james@healthke.org",
            "specialization": "general",
            "country_code": "KE",
            "languages": ["en", "sw"],
            "license_number": "KMPDC-22222",
            "medical_school": "University of Nairobi",
            "availability": "online",
            "verified": True,
            "license_verified": True,
        },
    ]

    created = []
    for doc_data in doctors:
        existing = db.query(DoctorProfile).filter_by(email=doc_data["email"]).first()
        if existing:
            created.append(existing)
            continue
        doc = DoctorProfile(**doc_data)
        db.add(doc)
        db.commit()
        db.refresh(doc)
        created.append(doc)
        print(f"  ✓ Seeded: {doc.full_name} ({doc.country_code}, {doc.specialization})")

    return created


def run_demo():
    print_section("WHO-ALIGNED AI TELEHEALTH BACKEND — END-TO-END DEMO")

    # Initialize
    print("\n[1] Initializing database...")
    init_db()
    db = SessionLocal()

    # Seed
    print("\n[2] Seeding country permissions...")
    seed_country_permissions(db)
    perms = db.query(CountryPermission).all()
    for p in perms:
        print(f"  ✓ {p.country_name} ({p.country_code}): tier={p.permission_tier}")

    print("\n[3] Seeding doctor profiles...")
    doctors = seed_doctors(db)

    # ── SCENARIO: Nigerian patient calls with persistent headache ──
    print_section("SCENARIO: Nigerian Patient — Persistent Headache")

    # Step 1: Phone parsing
    print("\n[4] Parsing phone number: +2348012345678")
    phone_info = parse_phone("+2348012345678")
    print(f"  Country: {phone_info['country_name']} ({phone_info['country_code']})")
    print(f"  E.164: {phone_info['e164']}")

    # Step 2: Permission check
    print("\n[5] Checking teleconsult permissions for Nigeria...")
    perms_check = check_teleconsult_allowed(db, "NG")
    print(f"  Allowed: {perms_check['allowed']}")
    print(f"  Tier: {perms_check['permission_tier']}")
    print(f"  Requires local doctor: {perms_check['requires_local_doctor']}")
    print(f"  Disclaimer: {perms_check['disclaimer'][:80]}...")

    # Step 3: Create patient + case
    print("\n[6] Creating patient and case...")
    patient = get_or_create_patient(db, phone_info["e164"], "NG", "en")
    print(f"  Patient ID: {patient.id[:12]}...")

    case = create_case(
        db, patient_id=patient.id, country_code="NG",
        chief_complaint="Persistent headache for 3 days",
        permission_tier="limited",
    )
    print(f"  Case ID: {case.id[:12]}...")
    print(f"  Status: {case.status}")

    # Step 4: Simulate intake completion (normally done via Claude API)
    print("\n[7] Simulating Claude intake completion...")
    intake_data = {
        "main_symptom": "persistent headache",
        "duration": "3 days",
        "severity": 6,
        "associated_symptoms": ["mild fever", "neck stiffness"],
        "medical_history": ["malaria (2023)"],
        "current_medications": [],
        "allergies": [],
        "triage_level": "YELLOW",
        "recommended_specialty": "general",
        "body_area": "Head",
        "red_flag_indicators": ["Persistent pain", "Fever"],
        "patient_summary": (
            "33-year-old Nigerian patient with persistent headache for 3 days, "
            "severity 6/10, with mild fever and neck stiffness. "
            "History of malaria in 2023. No current medications or known allergies."
        ),
    }
    print(f"  Intake data: {json.dumps(intake_data, indent=2)}")

    # Step 5: ICD-11 mapping
    print("\n[8] Mapping symptoms to ICD-11 codes...")
    for symptom in ["headache", "fever", "neck stiffness"]:
        codes = search_icd11_sync(symptom, max_results=2)
        print(f"  '{symptom}' → {codes}")

    icd11_flat = search_icd11_sync("headache", 3) + search_icd11_sync("fever", 2)

    # Step 6: Complete intake
    print("\n[9] Completing intake and setting triage...")
    case = complete_intake(db, case.id, intake_data, icd11_flat)
    print(f"  Triage: {case.triage_level}")
    print(f"  Priority score: {case.priority_score}")
    print(f"  ICD-11 codes: {case.icd11_codes}")

    # Step 7: Move to pending
    case = move_to_pending(db, case.id)
    print(f"  Status: {case.status}")

    # Step 8: Triage demo
    print_section("START TRIAGE DEMO")

    assessments = [
        ("Walking patient", PhoneAssessment(can_walk=True, is_breathing=True)),
        ("Not breathing, no response to reposition",
         PhoneAssessment(can_walk=False, is_breathing=False, breathing_after_reposition=False)),
        ("Breathing but fast (RR=35)",
         PhoneAssessment(can_walk=False, is_breathing=True, respiratory_rate=35)),
        ("Stable but can't walk",
         PhoneAssessment(can_walk=False, is_breathing=True, respiratory_rate=18,
                        capillary_refill_over_2s=False, can_follow_commands=True)),
    ]
    for desc, assessment in assessments:
        result = start_triage(assessment)
        print(f"  {desc}: → {result}")

    # Step 9: Priority queue
    print_section("PRIORITY QUEUE")

    # Create a second case (Indian patient) for queue demo
    patient2 = get_or_create_patient(db, "+919876543210", "IN", "hi")
    case2 = create_case(db, patient2.id, "IN", "Skin rash for 1 week", "regulated")
    complete_intake(db, case2.id, {
        "main_symptom": "skin rash",
        "severity": 4,
        "triage_level": "GREEN",
        "recommended_specialty": "dermatology",
        "body_area": "Skin",
        "red_flag_indicators": [],
        "patient_summary": "Indian patient with skin rash for 1 week, severity 4/10.",
    }, search_icd11_sync("skin rash", 2))
    move_to_pending(db, case2.id)

    # Create a third case (Kenyan patient — matches teammate's example contract)
    patient3 = get_or_create_patient(db, "+254712345678", "KE", "en")
    patient3.consent_given = True
    db.commit()
    case3 = create_case(db, patient3.id, "KE",
                        "Fever and persistent abdominal pain for 3 days", "emerging")
    complete_intake(db, case3.id, {
        "main_symptom": "Fever and persistent abdominal pain",
        "duration": "3 days",
        "severity": 7,
        "associated_symptoms": ["decreased appetite", "abdominal tenderness"],
        "medical_history": [],
        "current_medications": [],
        "allergies": [],
        "triage_level": "YELLOW",
        "recommended_specialty": "general",
        "body_area": "Abdomen",
        "red_flag_indicators": ["Persistent pain", "Fever"],
        "patient_summary": (
            "Caller reports worsening pain and decreased appetite."
        ),
    }, search_icd11_sync("abdominal pain", 2) + search_icd11_sync("fever", 2))
    move_to_pending(db, case3.id)

    print("\n[10] Queue snapshot (from Nigerian GP perspective):")
    ng_doctor = doctors[0]
    queue = get_queue_snapshot(db, ng_doctor.id)
    for item in queue:
        print(f"  Case {item['case_id'][:12]}... | {item['triage_level']} | "
              f"{item['country_code']} | score={item['priority_score']:.0f}")

    # Step 10: Doctor assignment
    print_section("DOCTOR ASSIGNMENT & RESPONSE")

    print(f"\n[11] Assigning case to Dr. {ng_doctor.full_name}...")
    case = assign_case(db, case.id, ng_doctor.id)
    print(f"  Status: {case.status}")
    print(f"  Assigned at: {case.assigned_at}")

    print(f"\n[12] Doctor starts working on case...")
    case = start_case(db, case.id, ng_doctor.id)
    print(f"  Status: {case.status}")

    print(f"\n[13] Doctor submits guidance...")
    response = submit_response(
        db, case.id, ng_doctor.id,
        guidance_text=(
            "Based on the symptoms described (persistent headache with fever and "
            "neck stiffness), I recommend the patient visit the nearest health "
            "facility for evaluation. These symptoms may require a malaria test "
            "and neurological assessment. In the meantime, stay hydrated and "
            "monitor temperature. If fever exceeds 39°C or neck stiffness "
            "worsens, seek emergency care immediately."
        ),
        is_emergency_referral=False,
        compliance_acknowledged=True,
    )
    print(f"  Response ID: {response.id[:12]}...")
    print(f"  Case status: resolved")

    # Step 11: Follow-up scheduling
    print(f"\n[14] Scheduling follow-ups at 24h and 48h...")
    fu1 = schedule_followup(db, case.id, hours=24, channel="sms")
    fu2 = schedule_followup(db, case.id, hours=48, channel="sms")
    print(f"  Follow-up 1: {fu1.scheduled_at} via {fu1.channel}")
    print(f"  Follow-up 2: {fu2.scheduled_at} via {fu2.channel}")

    # Step 12: Emergency keyword detection
    print_section("EMERGENCY KEYWORD DETECTION")
    test_messages = [
        "I have a headache",
        "I'm having chest pain and difficulty breathing",
        "My child has a rash",
        "I feel like hurting myself",
    ]
    for msg in test_messages:
        is_emergency = check_emergency_keywords(msg)
        flag = "🚨 EMERGENCY" if is_emergency else "✓ Non-urgent"
        print(f"  \"{msg}\" → {flag}")

    # Step 13: Full case detail
    print_section("FULL CASE DETAIL")
    detail = get_case_with_details(db, case.id)
    print(json.dumps(detail, indent=2, default=str))

    # Step 14: Frontend contract output
    print_section("FRONTEND CONTRACT (Doctor Portal Shape)")
    from services.case_service import get_case_for_frontend, get_all_cases_for_frontend
    frontend_case = get_case_for_frontend(db, case.id)
    print(json.dumps(frontend_case, indent=2, default=str))

    print("\n  All cases (frontend format):")
    all_frontend = get_all_cases_for_frontend(db)
    for fc in all_frontend:
        print(f"  {fc['caseId'][:12]}... | {fc['patientAlias']} | {fc['country']} "
              f"(tier {fc['countryTier']}) | {fc['urgency']} | score={fc['priorityScore']}")

    # Audit trail
    print_section("AUDIT TRAIL")
    from models import AuditLog
    audits = (
        db.query(AuditLog)
        .filter(AuditLog.resource_type == "case", AuditLog.resource_id == case.id)
        .order_by(AuditLog.timestamp.asc())
        .all()
    )
    for a in audits:
        print(f"  [{a.timestamp}] {a.action} by {a.actor_type} — {a.details}")

    db.close()
    print_section("DEMO COMPLETE")
    print("\nAll systems operational. Run 'uvicorn main:app --reload' to start the API.")
    print("API docs available at http://localhost:8000/docs")


if __name__ == "__main__":
    run_demo()
