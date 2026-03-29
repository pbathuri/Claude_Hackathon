"""
Twilio voice: ordered demographic intake + helpers for duration/body extraction.
Timeouts scaled to 80% of prior defaults (see GATHER_* / READY_TONE_*).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# 80% of typical Twilio defaults (5s wait → 4s; 2s tone → 1.6s)
GATHER_TIMEOUT_SEC = 4
GATHER_SPEECH_TIMEOUT = "4"
READY_TONE_DURATION_SEC = 1.6

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


def format_e164_for_speech(e164: str) -> str:
    """Speakable form of E.164 (digit by digit with pauses)."""
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
    if any(w in low for w in ("yes", "yeah", "yep", "correct", "right", "sure", "confirm")):
        return True
    if any(w in low for w in ("no", "nope", "wrong", "incorrect", "not correct", "not right")):
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
    d = re.sub(r"\D", "", speech or "")
    return d


def extract_duration_from_speech(speech: str) -> str:
    t = speech or ""
    m = re.search(r"(\d+\s*(?:days?|weeks?|months?|hours?|years?))", t, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m2 = re.search(r"since\s+(yesterday|last\s+\w+)", t, re.IGNORECASE)
    if m2:
        return f"since {m2.group(1)}"
    return ""


def extract_body_area_from_speech(speech: str) -> str:
    low = (speech or "").lower()
    for kw, label in _BODY_KEYWORDS:
        if kw in low:
            return label
    return ""


async def claude_parse_dob(speech: str, api_key: str, model: str) -> str:
    if not api_key or not (speech or "").strip():
        return ""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        r = client.messages.create(
            model=model,
            max_tokens=120,
            system=(
                'Parse the patient\'s spoken date of birth. Reply with JSON only: '
                '{"dob":"YYYY-MM-DD"} if you can infer a full date, else {"dob":""}. '
                "Accept formats like year month day spoken."
            ),
            messages=[{"role": "user", "content": speech[:500]}],
        )
        raw = (r.content[0].text or "").strip()
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            j = json.loads(raw[start:end])
            dob = (j.get("dob") or "").strip()
            if re.match(r"^\d{4}-\d{2}-\d{2}$", dob):
                return dob
    except Exception as exc:
        logger.warning("[Twilio] DOB parse failed: %s", exc)
    return ""


async def advance_twilio_demographics(
    session: dict[str, Any],
    english_speech: str,
    *,
    anthropic_api_key: str,
    intake_model: str,
) -> tuple[str, str]:
    """
    Process one demographic step. Mutates session (patient_* fields).
    Returns (assistant_message_english, next_phase).
    next_phase is one of: gender, name, dob, phone_confirm, phone_retry, delivery, symptoms
    """
    phase = session.get("intake_phase", "symptoms")
    speech = (english_speech or "").strip()
    e164 = session.get("caller_e164", "") or ""

    if phase == "gender":
        session["patient_gender"] = parse_gender(speech)
        return (
            "Thank you. Please state your full name.",
            "name",
        )

    if phase == "name":
        session["patient_name"] = speech[:200] if speech else "Not provided"
        return (
            "Please state your date of birth. Say the 4-digit year, then 2-digit month, "
            "then 2-digit day. For example: 1990, 03, 15.",
            "dob",
        )

    if phase == "dob":
        dob = await claude_parse_dob(speech, anthropic_api_key, intake_model)
        session["patient_dob"] = dob or ""
        spoken_num = format_e164_for_speech(e164)
        return (
            f"We have your phone number on file as {spoken_num}. Is this correct? Please say yes or no.",
            "phone_confirm",
        )

    if phase == "phone_confirm":
        yn = parse_yes_no(speech)
        if yn is True:
            session["patient_phone"] = e164
            session["patient_phone_confirmed"] = True
            return (
                "How would you like to receive your results from the doctor? "
                "Say 1 for Voice Message, 2 for Text or SMS, or 3 for Phone Call.",
                "delivery",
            )
        if yn is False:
            return (
                "Please say your correct phone number, including country code if you know it.",
                "phone_retry",
            )
        return (
            "I didn't catch that. Is the number we have on file correct? Please say yes or no.",
            "phone_confirm",
        )

    if phase == "phone_retry":
        digits = extract_phone_digits(speech)
        session["patient_phone"] = f"+{digits}" if digits else e164
        session["patient_phone_confirmed"] = bool(digits)
        return (
            "How would you like to receive your results from the doctor? "
            "Say 1 for Voice Message, 2 for Text or SMS, or 3 for Phone Call.",
            "delivery",
        )

    if phase == "delivery":
        pref = parse_delivery(speech)
        if not pref:
            return (
                "Please say 1 for Voice Message, 2 for Text or SMS, or 3 for Phone Call.",
                "delivery",
            )
        session["delivery_preference"] = pref
        return (
            "Now please describe your symptoms and what brought you to call today.",
            "symptoms",
        )

    return ("Please continue.", phase)


async def claude_symptom_summary_and_fill(
    transcript: str,
    symptoms: list[str],
    *,
    patient_gender: str,
    patient_name: str,
    patient_dob: str,
    patient_phone: str,
    delivery_preference: str,
    duration_guess: str,
    body_guess: str,
    severity: int,
    api_key: str,
    model: str,
) -> dict[str, str]:
    """
    Produce 2–3 sentence clinical symptom_summary and normalize duration / body_area via Claude.
    Returns keys: symptom_summary, duration, body_area.
    """
    out = {
        "symptom_summary": "",
        "duration": duration_guess or "",
        "body_area": body_guess or "",
    }
    if not api_key:
        sym = ", ".join(symptoms) if symptoms else "unspecified symptoms"
        out["symptom_summary"] = (
            f"Patient reports {sym}. "
            f"Duration: {duration_guess or 'unspecified'}. "
            f"Location: {body_guess or 'unspecified'}. Severity: {severity}/10."
        )
        return out
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        user_block = (
            f"Symptoms: {', '.join(symptoms)}\n"
            f"Severity (1-10): {severity}\n"
            f"Duration (extracted): {duration_guess or 'unknown'}\n"
            f"Body area (extracted): {body_guess or 'unknown'}\n"
            f"Gender: {patient_gender}\nName: {patient_name}\nDOB: {patient_dob}\n"
            f"Phone: {patient_phone}\nDelivery pref: {delivery_preference}\n\n"
            f"Call transcript (excerpt):\n{transcript[:6000]}"
        )
        r = client.messages.create(
            model=model,
            max_tokens=500,
            system=(
                "You are a clinical documentation assistant. Return JSON only with keys:\n"
                '  "symptom_summary": string, 2-3 sentences for a physician, no diagnosis;\n'
                '  "duration": string, concise (e.g. "3 days", "1 week") or "" if unknown;\n'
                '  "body_area": string, one or two words (e.g. "chest", "abdomen") or "".\n'
                "Use the transcript to improve duration and body if the extracted values are empty."
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
        sym = ", ".join(symptoms) if symptoms else "unspecified symptoms"
        out["symptom_summary"] = (
            f"Patient reports {sym}. "
            f"Duration: {out['duration'] or 'unspecified'}. "
            f"Body area: {out['body_area'] or 'unspecified'}. Pain severity {severity}/10."
        )
    return out
