"""
Twilio voice: strict sequential intake (one question per <Gather> callback).
Gather timeouts: prior short values × 1.2 (see GATHER_* / READY_TONE_*).
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

logger = logging.getLogger(__name__)

# ×1.2 on prior values (2→2.4→3s, "2"→"3", 1.0→1.2s tone)
GATHER_TIMEOUT_SEC = 3
GATHER_SPEECH_TIMEOUT = "3"
READY_TONE_DURATION_SEC = 1.2

Action = Literal["gather_next", "submit_case", "consent_refused"]

_COMMON_SYMPTOM_WORDS = [
    "fever", "headache", "cough", "nausea", "vomiting", "diarrhea",
    "fatigue", "dizziness", "chest pain", "abdominal pain", "rash",
    "sore throat", "body aches", "chills", "shortness of breath",
    "back pain", "joint pain", "loss of appetite", "weight loss",
    "pain", "bleeding", "swelling", "weakness",
]

_BODY_KEYWORDS = [
    ("chest", "chest"),
    ("head", "head"),
    ("abdomen", "abdomen"),
    ("stomach", "abdomen"),
    ("belly", "abdomen"),
    ("back", "back"),
    ("neck", "neck"),
    ("throat", "throat"),
    ("leg", "leg"),
    ("arm", "arm"),
    ("joint", "joints"),
    ("skin", "skin"),
    ("ear", "ear"),
    ("nose", "nose"),
    ("eye", "eye"),
    ("pelvis", "pelvis"),
    ("groin", "groin"),
    ("foot", "foot"),
    ("ankle", "ankle"),
    ("hand", "hand"),
    ("wrist", "wrist"),
    ("shoulder", "shoulder"),
    ("hip", "hip"),
    ("face", "face"),
]


@dataclass
class IntakeStepResult:
    reply_en: str
    next_phase: str
    action: Action


def format_e164_for_speech(e164: str) -> str:
    digits = re.sub(r"\D", "", e164 or "")
    if not digits:
        return "your number on file"
    return ", ".join(digits)


def parse_gender(speech: str) -> str:
    low = (speech or "").lower()
    if any(w in low for w in ("female", "woman", "girl")):
        return "female"
    if any(w in low for w in ("male", "man", "boy")):
        return "male"
    return "unspecified"


def parse_yes_no(speech: str) -> bool | None:
    low = (speech or "").lower()
    if any(w in low for w in ("yes", "yeah", "yep", "correct", "right", "sure", "confirm", "i consent", "consent")):
        return True
    if any(w in low for w in ("no", "nope", "wrong", "incorrect", "not correct", "not right", "don't", "do not")):
        return False
    return None


def parse_delivery(speech: str) -> str | None:
    low = (speech or "").lower()
    if re.search(r"\b1\b|^1\s|one|voice\s*message", low):
        return "voice_message"
    if re.search(r"\b2\b|^2\s|two|text|sms", low):
        return "sms"
    if re.search(r"\b3\b|^3\s|three|phone\s*call", low):
        return "phone_call"
    return None


def extract_phone_digits(speech: str) -> str:
    return re.sub(r"\D", "", speech or "")


def extract_duration_from_speech(speech: str) -> str:
    t = speech or ""
    m = re.search(r"(\d+\s*(?:days?|weeks?|months?|hours?|years?))", t, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m2 = re.search(r"since\s+(yesterday|last\s+\w+)", t, re.IGNORECASE)
    if m2:
        return f"since {m2.group(1)}"
    return (t or "").strip()[:120]


def extract_body_area_from_speech(speech: str) -> str:
    low = (speech or "").lower()
    for kw, label in _BODY_KEYWORDS:
        if kw in low:
            return label
    return (speech or "").strip()[:120]


def parse_age(speech: str) -> int | None:
    for m in re.finditer(r"\b(\d{1,3})\b", speech or ""):
        n = int(m.group(1))
        if 1 <= n <= 120:
            return n
    return None


def parse_pain_0_10(speech: str) -> int | None:
    m = re.search(r"\b(10|[0-9])\b", speech or "")
    if not m:
        return None
    n = int(m.group(1))
    return n if 0 <= n <= 10 else None


def symptoms_from_chief_text(chief: str) -> list[str]:
    low = (chief or "").lower()
    found = [s for s in _COMMON_SYMPTOM_WORDS if s in low]
    if found:
        return list(dict.fromkeys(found))
    words = [w.strip(".,!?") for w in low.split() if len(w) > 2]
    return list(dict.fromkeys(words[:8])) if words else ["unspecified symptom"]


def parse_allergies_speech(speech: str) -> str | None:
    """
    Canonical no-allergy value is '0' (also accept none/nkda spoken as no allergies).
    Otherwise returns spoken allergy text. None = not understood / empty.
    """
    raw = (speech or "").strip()
    if not raw:
        return None
    low = raw.lower()
    if low in ("0", "zero", "none", "no", "no allergies", "no allergy", "nkda", "no known", "no known allergies"):
        return "0"
    if re.fullmatch(r"0+", low):
        return "0"
    return raw[:500]


def parse_medication_list(speech: str) -> list[str]:
    low = (speech or "").lower().strip()
    if not low:
        return []
    if low in ("none", "no", "no medications", "not taking", "nothing"):
        return []
    return [s.strip() for s in re.split(r"[,;]", speech) if s.strip()][:30]


async def advance_twilio_intake_step(
    session: dict[str, Any],
    english_speech: str,
    *,
    anthropic_api_key: str,
    intake_model: str,
    graph: Any | None = None,
    case_id: str | None = None,
) -> IntakeStepResult:
    """
    One step per Twilio Gather callback. Mutates session.
    Pre-consent phases use concise professional copy; post-consent uses supportive / KG+Claude dialog.
    """
    phase = session.get("intake_phase", "name")
    speech = (english_speech or "").strip()
    e164 = session.get("caller_e164", "") or ""
    cid = case_id or str(session.get("case_id") or "")

    if phase == "name":
        if not speech:
            return IntakeStepResult(
                "I didn't catch your name. Please say your full name clearly.",
                "name",
                "gather_next",
            )
        session["patient_name"] = speech[:200]
        return IntakeStepResult(
            "How old are you? Please say your age.",
            "age",
            "gather_next",
        )

    if phase == "age":
        age = parse_age(speech)
        if age is None:
            return IntakeStepResult(
                "I didn't catch that. How old are you? Please say your age as a number.",
                "age",
                "gather_next",
            )
        session["patient_age"] = age
        return IntakeStepResult(
            "Are you male or female? Please say male or female.",
            "gender",
            "gather_next",
        )

    if phase == "gender":
        if not speech:
            return IntakeStepResult(
                "I didn't catch that. Are you male or female? Please say male or female.",
                "gender",
                "gather_next",
            )
        session["patient_gender"] = parse_gender(speech)
        spoken_num = format_e164_for_speech(e164)
        return IntakeStepResult(
            f"We have your phone number on file as {spoken_num}. Is this correct? Please say yes or no.",
            "phone_confirm",
            "gather_next",
        )

    # Legacy in-flight sessions that still have intake_phase "dob" — skip removed step
    if phase == "dob":
        spoken_num = format_e164_for_speech(e164)
        return IntakeStepResult(
            f"We have your phone number on file as {spoken_num}. Is this correct? Please say yes or no.",
            "phone_confirm",
            "gather_next",
        )

    if phase == "phone_confirm":
        yn = parse_yes_no(speech)
        if yn is True:
            session["patient_phone"] = e164
            session["patient_phone_confirmed"] = True
            return IntakeStepResult(
                "Do you consent to the collection and use of your personal information "
                "for medical purposes? Please say yes or no.",
                "consent",
                "gather_next",
            )
        if yn is False:
            return IntakeStepResult(
                "Please say your correct phone number, including country code if you know it.",
                "phone_retry",
                "gather_next",
            )
        return IntakeStepResult(
            "I didn't catch that. Is the number we have on file correct? Please say yes or no.",
            "phone_confirm",
            "gather_next",
        )

    if phase == "phone_retry":
        digits = extract_phone_digits(speech)
        session["patient_phone"] = f"+{digits}" if digits else e164
        session["patient_phone_confirmed"] = bool(digits)
        return IntakeStepResult(
            "Do you consent to the collection and use of your personal information "
            "for medical purposes? Please say yes or no.",
            "consent",
            "gather_next",
        )

    if phase == "consent":
        yn = parse_yes_no(speech)
        if yn is True:
            session["intake_consent_granted"] = True
            session["tone_mode"] = "supportive"
            from services.twilio_clinical_dialog import warm_post_consent_chief_prompt

            chief_q = await warm_post_consent_chief_prompt(
                anthropic_api_key=anthropic_api_key,
                intake_model=intake_model,
            )
            return IntakeStepResult(chief_q, "sq_chief", "gather_next")
        if yn is False:
            return IntakeStepResult(
                "Understood. Your information will not be stored. Thank you for calling. Goodbye.",
                "consent_denied",
                "consent_refused",
            )
        return IntakeStepResult(
            "Please say yes if you consent, or no if you do not.",
            "consent",
            "gather_next",
        )

    if phase == "sq_chief":
        if not speech:
            return IntakeStepResult(
                "I didn't catch that. What is your main symptom or reason for calling today?",
                "sq_chief",
                "gather_next",
            )
        session["sq_chief_text"] = speech[:500]
        session["collected_symptoms"] = symptoms_from_chief_text(speech)
        session["cd_turn"] = 0
        session.setdefault("question_queue", [])
        from services.twilio_clinical_dialog import advance_clinical_dialog_step, clinical_sufficiency_met

        out = await advance_clinical_dialog_step(
            session,
            speech,
            anthropic_api_key=anthropic_api_key,
            intake_model=intake_model,
            graph=graph,
            case_id=cid,
        )
        session["clinical_sufficiency"] = {"met": clinical_sufficiency_met(session)}
        return out

    if phase == "clinical_dialog":
        from services.twilio_clinical_dialog import advance_clinical_dialog_step, clinical_sufficiency_met

        result = await advance_clinical_dialog_step(
            session,
            speech,
            anthropic_api_key=anthropic_api_key,
            intake_model=intake_model,
            graph=graph,
            case_id=cid,
        )
        session["clinical_sufficiency"] = {"met": clinical_sufficiency_met(session)}
        return result

    if phase == "sq_body":
        session["twilio_stored_body_area"] = extract_body_area_from_speech(speech) or (speech or "").strip()[:120]
        return IntakeStepResult(
            "On a scale of zero to ten, how severe is the pain or discomfort? Zero is none, ten is the worst.",
            "sq_pain",
            "gather_next",
        )

    if phase == "sq_pain":
        pain = parse_pain_0_10(speech)
        if pain is None:
            return IntakeStepResult(
                "Please say a number from zero to ten for your pain level.",
                "sq_pain",
                "gather_next",
            )
        session["twilio_pain_score"] = pain
        return IntakeStepResult(
            "How long have you had these symptoms? For example: two days, one week, or three hours.",
            "sq_duration",
            "gather_next",
        )

    if phase == "sq_duration":
        session["twilio_stored_duration"] = extract_duration_from_speech(speech) or (speech or "").strip()[:120]
        return IntakeStepResult(
            "Do you have any known allergies? If yes, please say the name of your allergy. "
            "If you have NO allergies, please say zero.",
            "sq_allergies",
            "gather_next",
        )

    if phase == "sq_allergies":
        al = parse_allergies_speech(speech)
        if al is None:
            return IntakeStepResult(
                "I didn't catch that. Do you have any known allergies? If yes, say the name of your allergy. "
                "If you have NO allergies, please say zero.",
                "sq_allergies",
                "gather_next",
            )
        session["allergies_text"] = al
        return IntakeStepResult(
            "What medications are you currently taking? Or say none.",
            "sq_meds",
            "gather_next",
        )

    if phase == "sq_meds":
        session["medications_list"] = parse_medication_list(speech)
        return IntakeStepResult(
            "How would you like to receive your results from the doctor? "
            "Say 1 for Voice Message, 2 for Text or SMS, or 3 for Phone Call.",
            "sq_delivery",
            "gather_next",
        )

    if phase == "sq_delivery":
        pref = parse_delivery(speech)
        if not pref:
            return IntakeStepResult(
                "Please say 1 for Voice Message, 2 for Text or SMS, or 3 for Phone Call.",
                "sq_delivery",
                "gather_next",
            )
        session["delivery_preference"] = pref
        return IntakeStepResult(
            "Thank you. Your information has been recorded and will be reviewed by a physician. Goodbye.",
            "done",
            "submit_case",
        )

    return IntakeStepResult(
        "Please call back to start your intake again.",
        "done",
        "gather_next",
    )


async def claude_symptom_summary_and_fill(
    transcript: str,
    symptoms: list[str],
    *,
    patient_gender: str,
    patient_name: str,
    patient_dob: str,
    patient_phone: str,
    patient_age: int | None,
    delivery_preference: str,
    duration_guess: str,
    body_guess: str,
    severity: int,
    allergies: str,
    medications: list[str],
    chief_text: str,
    api_key: str,
    model: str,
) -> dict[str, str]:
    out = {
        "symptom_summary": "",
        "duration": duration_guess or "",
        "body_area": body_guess or "",
    }
    age_s = str(patient_age) if patient_age is not None else ""
    _al = (allergies or "").strip()
    al_display = "no known allergies" if _al in ("0", "none", "") else _al
    if not api_key:
        sym = ", ".join(symptoms) if symptoms else "unspecified symptoms"
        out["symptom_summary"] = (
            f"{chief_text or sym}. Allergies: {al_display}. "
            f"Meds: {', '.join(medications) or 'none reported'}. "
            f"Duration: {duration_guess or 'unspecified'}. Body: {body_guess or 'unspecified'}. "
            f"Pain {severity}/10. Age {age_s}."
        )
        return out
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        user_block = (
            f"Chief concern: {chief_text}\n"
            f"Symptoms (tags): {', '.join(symptoms)}\n"
            f"Severity (0-10): {severity}\n"
            f"Duration: {duration_guess or 'unknown'}\n"
            f"Body area: {body_guess or 'unknown'}\n"
            f"Allergies: {al_display}\n"
            f"Medications: {', '.join(medications) or 'none'}\n"
            f"Age: {age_s} Gender: {patient_gender} DOB: {patient_dob} Phone: {patient_phone}\n"
            f"Delivery: {delivery_preference}\n\n"
            f"Transcript excerpt:\n{transcript[:6000]}"
        )
        r = client.messages.create(
            model=model,
            max_tokens=500,
            system=(
                "You are a clinical documentation assistant. Return JSON only with keys:\n"
                '  "symptom_summary": string, 2-3 sentences for a physician, no diagnosis;\n'
                '  "duration": string, concise, or "";\n'
                '  "body_area": string, short, or "".\n'
            ),
            messages=[{"role": "user", "content": user_block}],
        )
        raw = (r.content[0].text or "").strip()
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start >= 0 and end > start:
            j = json.loads(raw[start:end])
            out["symptom_summary"] = (j.get("symptom_summary") or "").strip()
            if j.get("duration"):
                out["duration"] = str(j["duration"]).strip()
            if j.get("body_area"):
                out["body_area"] = str(j["body_area"]).strip()
    except Exception as exc:
        logger.warning("[Twilio] symptom_summary JSON failed: %s", exc)
    if not out["symptom_summary"]:
        sym = ", ".join(symptoms) if symptoms else chief_text or "unspecified"
        out["symptom_summary"] = (
            f"Patient reports {sym}. Pain {severity}/10. "
            f"Duration: {out['duration'] or 'unspecified'}. "
            f"Body: {out['body_area'] or 'unspecified'}."
        )
    return out
