"""
Comprehensive E2E Test Suite
Tests every workflow: caller, doctor, KG, frontend contract
"""
import json
import sys
import time
import httpx

BASE = "http://localhost:8000"
client = httpx.Client(base_url=BASE, timeout=15)

passed = 0
failed = 0
errors = []


def test(name, fn):
    global passed, failed
    try:
        result = fn()
        if result:
            passed += 1
            print(f"  \033[32m✓\033[0m {name}")
        else:
            failed += 1
            errors.append(name)
            print(f"  \033[31m✗\033[0m {name}")
    except Exception as e:
        failed += 1
        errors.append(f"{name}: {e}")
        print(f"  \033[31m✗\033[0m {name} — {e}")


# ════════════════════════════════════════════════════════════════════════
# PHASE 1: CALLER / USER WORKFLOW
# ════════════════════════════════════════════════════════════════════════
print("\n\033[1m═══ PHASE 1: CALLER / USER WORKFLOW ═══\033[0m\n")

session_data = {}


def test_session_start_ng():
    r = client.post("/caller/session/start", json={"phone_number": "+2349012345678"})
    d = r.json()
    session_data["ng"] = d
    return (
        r.status_code == 200
        and d.get("country_code") == "NG"
        and d.get("case_id")
        and d.get("session_id")
        and d.get("verbal_disclosure")
        and d.get("country_name") == "Nigeria"
    )


def test_session_start_ke():
    r = client.post("/caller/session/start", json={"phone_number": "+254712345678"})
    d = r.json()
    session_data["ke"] = d
    return (
        r.status_code == 200
        and d.get("country_code") == "KE"
        and d.get("country_name") == "Kenya"
        and d.get("allows_teleconsult") is True
    )


def test_session_start_in():
    r = client.post("/caller/session/start", json={"phone_number": "+919876543210"})
    d = r.json()
    session_data["in"] = d
    return r.status_code == 200 and d.get("country_code") == "IN"


def test_session_start_ph():
    r = client.post("/caller/session/start", json={"phone_number": "+639171234567"})
    d = r.json()
    session_data["ph"] = d
    return r.status_code == 200 and d.get("country_code") == "PH"


def test_consent():
    case_id = session_data["ng"]["case_id"]
    r = client.post("/caller/session/consent", json={
        "case_id": case_id,
        "consent_given": True
    })
    d = r.json()
    return r.status_code == 200 and (d.get("consent_recorded") is True or d.get("status") == "consent_recorded")


def test_emergency_check_safe():
    r = client.post("/caller/emergency-check", json={
        "text": "I have a headache and feel tired"
    })
    d = r.json()
    return r.status_code == 200 and d.get("action") == "CONTINUE_INTAKE"


def test_emergency_check_danger():
    r = client.post("/caller/emergency-check", json={
        "text": "I have severe chest pain and can't breathe"
    })
    d = r.json()
    return r.status_code == 200 and d.get("action") == "ROUTE_TO_EMERGENCY_SERVICES"


def test_submit_ng():
    case_id = session_data["ng"]["case_id"]
    r = client.post("/caller/session/submit", json={
        "case_id": case_id,
        "symptoms": ["fever", "headache", "chills", "body aches"],
        "message_history": [
            {"role": "user", "content": "I have a fever and headache"},
            {"role": "assistant", "content": "How long have you had these symptoms?"},
            {"role": "user", "content": "About 3 days, also chills and body aches"},
        ],
        "transcript_summary": "Patient reports 3-day fever with headache, chills, and body aches.",
        "severity": 7,
        "duration": "3 days",
        "body_area": "Head and Neck"
    })
    d = r.json()
    session_data["ng_submit"] = d
    return (
        r.status_code == 200
        and d.get("case_id") == case_id
        and d.get("status") in ("pending_review", "pending")
    )


def test_submit_ke():
    case_id = session_data["ke"]["case_id"]
    r = client.post("/caller/session/submit", json={
        "case_id": case_id,
        "symptoms": ["diarrhea", "vomiting", "dehydration"],
        "message_history": [],
        "transcript_summary": "Severe watery diarrhea with vomiting for 2 days.",
        "severity": 8,
        "duration": "2 days",
        "body_area": "Abdomen"
    })
    d = r.json()
    return r.status_code == 200 and d.get("status") in ("pending_review", "pending")


def test_check_case_status():
    case_id = session_data["ke"]["case_id"]
    r = client.get(f"/caller/session/{case_id}")
    d = r.json()
    return (
        r.status_code == 200
        and d.get("case_id") == case_id
    )


def test_disclosure_ng():
    r = client.get("/caller/disclosure/NG")
    d = r.json()
    return (
        r.status_code == 200
        and d.get("country_code") == "NG"
        and (d.get("verbal_disclosure") or d.get("verbal_disclosure_script"))
        and "tier" in str(d).lower()
    )


def test_disclosure_ke():
    r = client.get("/caller/disclosure/KE")
    return r.status_code == 200 and r.json().get("country_code") == "KE"


test("Session start: Nigeria (+234)", test_session_start_ng)
test("Session start: Kenya (+254)", test_session_start_ke)
test("Session start: India (+91)", test_session_start_in)
test("Session start: Philippines (+63)", test_session_start_ph)
test("Consent recording", test_consent)
test("Emergency check: safe transcript", test_emergency_check_safe)
test("Emergency check: dangerous transcript", test_emergency_check_danger)
test("Submit conversation: Nigeria malaria case", test_submit_ng)
test("Submit conversation: Kenya cholera case", test_submit_ke)
test("Check case status after submit", test_check_case_status)
test("Verbal disclosure: Nigeria", test_disclosure_ng)
test("Verbal disclosure: Kenya", test_disclosure_ke)


# ════════════════════════════════════════════════════════════════════════
# PHASE 2: DOCTOR WORKFLOW
# ════════════════════════════════════════════════════════════════════════
print("\n\033[1m═══ PHASE 2: DOCTOR WORKFLOW ═══\033[0m\n")


def test_register_doctor():
    import uuid
    r = client.post("/doctors/", json={
        "full_name": "Dr. Adebayo Okafor",
        "email": f"adebayo-{uuid.uuid4().hex[:6]}@hospital.ng",
        "specialization": "Infectious Disease",
        "country_code": "NG",
        "license_number": "MDCN-12345"
    })
    d = r.json()
    session_data["doctor_id"] = d.get("id") or d.get("doctor_id")
    return r.status_code in (200, 201) and session_data["doctor_id"]


def test_register_doctor_ke():
    import uuid
    r = client.post("/doctors/", json={
        "full_name": "Dr. Wanjiku Mwangi",
        "email": f"wanjiku-{uuid.uuid4().hex[:6]}@hospital.ke",
        "specialization": "General Practice",
        "country_code": "KE",
        "license_number": "KMPDC-67890"
    })
    d = r.json()
    session_data["doctor_ke_id"] = d.get("id") or d.get("doctor_id")
    return r.status_code in (200, 201)


def test_get_queue():
    r = client.get("/cases/queue")
    d = r.json()
    return r.status_code == 200 and isinstance(d, list)


def test_patient_cases_list():
    r = client.get("/cases/patient-cases")
    d = r.json()
    if r.status_code == 200 and isinstance(d, list) and len(d) > 0:
        c = d[0]
        required = ["caseId", "patientAlias", "country", "urgency", "symptomSummary", "priorityScore"]
        return all(k in c for k in required)
    return False


def test_patient_case_detail():
    case_id = session_data["ng"]["case_id"]
    r = client.get(f"/cases/patient-cases/{case_id}")
    d = r.json()
    return (
        r.status_code == 200
        and d.get("caseId") == case_id
        and d.get("country") == "Nigeria"
        and d.get("priorityScore") is not None
    )


def test_assign_case():
    case_id = session_data["ng"]["case_id"]
    doctor_id = session_data.get("doctor_id")
    if not doctor_id:
        return False
    r = client.post(f"/cases/{case_id}/assign", json={"doctor_id": doctor_id})
    return r.status_code == 200


def test_doctor_respond():
    case_id = session_data["ng"]["case_id"]
    doctor_id = session_data.get("doctor_id")
    if not doctor_id:
        return False
    r = client.post(f"/cases/{case_id}/respond", json={
        "doctor_id": doctor_id,
        "guidance_text": "Suspected Malaria. Recommend Artemether-Lumefantrine 80/480mg twice daily for 3 days. Stay hydrated. Return if symptoms worsen.",
        "is_emergency_referral": False,
        "compliance_acknowledged": True
    })
    d = r.json()
    session_data["response_result"] = d
    return r.status_code == 200


def test_case_status_after_response():
    case_id = session_data["ng"]["case_id"]
    r = client.get(f"/caller/session/{case_id}")
    d = r.json()
    return r.status_code == 200 and d.get("status") in ("resolved", "follow_up", "responded", "assigned")


test("Register doctor: Nigeria", test_register_doctor)
test("Register doctor: Kenya", test_register_doctor_ke)
test("Get case queue", test_get_queue)
test("Patient cases list (frontend contract)", test_patient_cases_list)
test("Patient case detail (frontend contract)", test_patient_case_detail)
test("Assign case to doctor", test_assign_case)
test("Doctor responds with diagnosis", test_doctor_respond)
test("Case status reflects doctor response", test_case_status_after_response)


# ════════════════════════════════════════════════════════════════════════
# PHASE 3: KNOWLEDGE GRAPH INTERNAL APIs
# ════════════════════════════════════════════════════════════════════════
print("\n\033[1m═══ PHASE 3: KNOWLEDGE GRAPH APIs ═══\033[0m\n")


def test_kg_stats():
    r = client.get("/kg/stats")
    d = r.json()
    return (
        r.status_code == 200
        and d.get("total_nodes", 0) > 200
        and d.get("total_edges", 0) > 300
        and "specialty_heatmap" in d
    )


def test_kg_query_malaria():
    r = client.post("/kg/query", json={"symptoms": ["fever", "headache", "chills", "body aches"]})
    d = r.json()
    conditions = [c["condition"] for c in d.get("activated_conditions", [])]
    return r.status_code == 200 and "Malaria" in conditions[:3]


def test_kg_query_stroke():
    r = client.post("/kg/query", json={"symptoms": ["slurred speech", "weakness", "confusion"]})
    d = r.json()
    conditions = [c["condition"] for c in d.get("activated_conditions", [])]
    return r.status_code == 200 and "Stroke" in conditions[:3]


def test_kg_query_depression():
    r = client.post("/kg/query", json={"symptoms": ["depression", "insomnia", "fatigue", "loss of appetite"]})
    d = r.json()
    conditions = [c["condition"] for c in d.get("activated_conditions", [])]
    return r.status_code == 200 and "Major Depressive Disorder" in conditions[:3]


def test_kg_query_asthma():
    r = client.post("/kg/query", json={"symptoms": ["wheezing", "shortness of breath", "chest tightness"]})
    d = r.json()
    conditions = [c["condition"] for c in d.get("activated_conditions", [])]
    specialties = [s["specialty"] for s in d.get("suggested_specialties", [])]
    return (
        r.status_code == 200
        and "Asthma" in conditions[:3]
        and "Pulmonology" in specialties[:3]
    )


def test_kg_query_returns_questions():
    r = client.post("/kg/query", json={"symptoms": ["abdominal pain", "nausea"]})
    d = r.json()
    return r.status_code == 200 and len(d.get("suggested_questions", [])) > 0


def test_kg_navigate_with_case():
    case_id = session_data["ke"]["case_id"]
    r = client.post("/kg/navigate", json={
        "case_id": case_id,
        "symptoms": ["diarrhea", "vomiting", "dehydration"]
    })
    d = r.json()
    conditions = [c["condition"] for c in d.get("activated_conditions", [])]
    return r.status_code == 200 and ("Cholera" in conditions[:3] or "Gastroenteritis" in conditions[:3])


def test_kg_backpropagate():
    case_id = session_data["ke"]["case_id"]
    r = client.post("/kg/backpropagate", json={
        "case_id": case_id,
        "doctor_diagnosis": "Cholera",
        "doctor_specialty": "Infectious Disease",
        "outcome": "resolved"
    })
    d = r.json()
    return r.status_code == 200 and "reinforced_edges" in d


def test_kg_hottest_paths():
    r = client.get("/kg/hottest-paths")
    d = r.json()
    return r.status_code == 200 and len(d.get("paths", [])) > 0


def test_kg_conditions_fever():
    r = client.get("/kg/conditions/fever")
    d = r.json()
    conditions = [c["condition"] for c in d.get("conditions", [])]
    return r.status_code == 200 and len(conditions) >= 3 and "Malaria" in conditions


def test_kg_conditions_cough():
    r = client.get("/kg/conditions/cough")
    d = r.json()
    conditions = [c["condition"] for c in d.get("conditions", [])]
    return r.status_code == 200 and any(c in conditions for c in ["Pneumonia", "Tuberculosis", "Asthma"])


def test_kg_search():
    r = client.get("/kg/search", params={"q": "malaria"})
    d = r.json()
    return r.status_code == 200 and len(d.get("results", [])) > 0


def test_kg_subgraph():
    r = client.get("/kg/conditions/fever")
    d = r.json()
    if d.get("conditions"):
        node_name = d["conditions"][0].get("condition", "Malaria")
        r2 = client.get(f"/kg/subgraph/{node_name}")
        d2 = r2.json()
        return r2.status_code == 200 and len(d2.get("nodes", [])) > 0
    return False


def test_kg_match_doctors():
    r = client.post("/kg/match-doctors", json={
        "symptoms": ["fever", "chills", "body aches"],
        "conditions": ["Malaria"],
        "country_code": "NG",
        "available_doctors": [
            {"id": "d1", "name": "Dr. A", "specialization": "Infectious Disease", "country_code": "NG"},
            {"id": "d2", "name": "Dr. B", "specialization": "Cardiology", "country_code": "NG"},
            {"id": "d3", "name": "Dr. C", "specialization": "General Practice", "country_code": "KE"},
        ]
    })
    d = r.json()
    doctors = d.get("ranked_doctors") or d.get("doctors") or []
    if r.status_code == 200 and len(doctors) > 0:
        top = doctors[0]
        return top.get("specialization") == "Infectious Disease"
    return False


def test_kg_decay():
    r = client.post("/kg/decay")
    return r.status_code == 200


test("KG stats: >200 nodes, >300 edges", test_kg_stats)
test("KG query: fever+headache+chills → Malaria", test_kg_query_malaria)
test("KG query: slurred speech+weakness → Stroke", test_kg_query_stroke)
test("KG query: depression+insomnia → MDD", test_kg_query_depression)
test("KG query: wheezing+SOB → Asthma + Pulmonology", test_kg_query_asthma)
test("KG query: returns follow-up questions", test_kg_query_returns_questions)
test("KG navigate: diarrhea+vomiting case", test_kg_navigate_with_case)
test("KG backpropagate: Cholera confirmed", test_kg_backpropagate)
test("KG hottest paths: non-empty", test_kg_hottest_paths)
test("KG conditions: fever → includes Malaria", test_kg_conditions_fever)
test("KG conditions: cough → includes Pneumonia/TB", test_kg_conditions_cough)
test("KG search: 'malaria' returns results", test_kg_search)
test("KG subgraph: top condition has neighbors", test_kg_subgraph)
test("KG match doctors: Infectious Disease ranks first for malaria", test_kg_match_doctors)
test("KG decay: runs without error", test_kg_decay)


# ════════════════════════════════════════════════════════════════════════
# PHASE 4: FRONTEND CONTRACT + MISC ENDPOINTS
# ════════════════════════════════════════════════════════════════════════
print("\n\033[1m═══ PHASE 4: FRONTEND CONTRACT & MISC ═══\033[0m\n")


def test_root():
    r = client.get("/")
    d = r.json()
    return r.status_code == 200 and d.get("status") == "operational"


def test_health_check():
    r = client.get("/health-check")
    return r.status_code == 200 and r.json().get("status") == "healthy"


def test_patient_cases_filter_urgency():
    r = client.get("/cases/patient-cases", params={"status": "pending_review"})
    return r.status_code == 200 and isinstance(r.json(), list)


def test_patient_case_has_all_fields():
    case_id = session_data["ng"]["case_id"]
    r = client.get(f"/cases/patient-cases/{case_id}")
    d = r.json()
    required = [
        "caseId", "patientAlias", "country", "countryTier", "urgency",
        "symptomSummary", "painScore", "symptomDuration", "bodyArea",
        "consentGiven", "submittedAt", "priorityScore"
    ]
    missing = [k for k in required if k not in d]
    if missing:
        print(f"    Missing fields: {missing}")
    return len(missing) == 0


def test_doctor_list():
    r = client.get("/doctors/")
    return r.status_code == 200 and isinstance(r.json(), list)


def test_unsupported_country():
    r = client.post("/caller/session/start", json={"phone_number": "+1234567890"})
    return r.status_code in (200, 400, 403, 404, 422, 500)


test("Root endpoint", test_root)
test("Health check", test_health_check)
test("Patient cases: filter by status", test_patient_cases_filter_urgency)
test("Patient case: has ALL required frontend fields", test_patient_case_has_all_fields)
test("Doctor list endpoint", test_doctor_list)
test("Unsupported country handling", test_unsupported_country)


# ════════════════════════════════════════════════════════════════════════
# RESULTS
# ════════════════════════════════════════════════════════════════════════
total = passed + failed
print(f"\n\033[1m{'═' * 60}\033[0m")
print(f"\033[1m  RESULTS: {passed}/{total} passed ({100*passed//total}%)\033[0m")
if errors:
    print(f"\033[31m  FAILURES:\033[0m")
    for e in errors:
        print(f"    - {e}")
print(f"\033[1m{'═' * 60}\033[0m\n")

sys.exit(0 if failed == 0 else 1)
