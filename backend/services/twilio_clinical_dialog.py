"""
Post-consent clinical dialog: KG-guided follow-up questions with a supportive (nurse-like) tone via Claude.

Runs after chief complaint (phase clinical_dialog). Exits to fixed tail (allergies → meds → delivery)
when clinical sufficiency is met or max turns reached. Preserves session keys used by _submit_twilio_case.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from services.twilio_intake_flow import (
    IntakeStepResult,
    extract_body_area_from_speech,
    extract_duration_from_speech,
    parse_pain_0_10,
    symptoms_from_chief_text,
)

logger = logging.getLogger(__name__)

MAX_CLINICAL_TURNS = 8
MAX_REPLY_CHARS = 420
MAX_CHIEF_PROMPT_CHARS = 220

_PRO_CHIEF_FALLBACK = (
    "What is your main symptom or reason for calling today? Please describe it in a few words."
)


async def warm_post_consent_chief_prompt(*, anthropic_api_key: str, intake_model: str) -> str:
    """Deterministic warm post-consent prompt — no LLM call to keep latency near zero.

    Claude is used later in the clinical_dialog phase where the conversation is already open
    and small latencies are tolerable.
    """
    return (
        "Thank you for your consent. I'm here to help. "
        "Can you tell me your main symptom or reason for calling today?"
    )


@dataclass
class _ClinicalExtract:
    body_area: str | None
    pain_0_10: int | None
    duration_text: str | None
    associated_symptom: str | None


def _parse_clinical_json(raw: str) -> tuple[str, _ClinicalExtract, bool]:
    """Returns (reply_spoken_english, extract, done_dialog)."""
    start, end = raw.find("{"), raw.rfind("}") + 1
    if start < 0 or end <= start:
        return (
            "Thank you. Can you tell me a bit more about what you're feeling?",
            _ClinicalExtract(None, None, None, None),
            False,
        )
    try:
        j = json.loads(raw[start:end])
    except json.JSONDecodeError:
        return (
            "I want to make sure we help you. What else should the doctor know?",
            _ClinicalExtract(None, None, None, None),
            False,
        )
    reply = (j.get("reply_spoken") or j.get("reply") or "").strip()
    if len(reply) > MAX_REPLY_CHARS:
        reply = reply[: MAX_REPLY_CHARS - 3] + "..."
    ex = _ClinicalExtract(
        body_area=(j.get("body_area") or "").strip() or None,
        pain_0_10=j.get("pain_0_10") if isinstance(j.get("pain_0_10"), int) else None,
        duration_text=(j.get("duration") or "").strip() or None,
        associated_symptom=(j.get("associated_symptom") or "").strip() or None,
    )
    if ex.pain_0_10 is not None and not (0 <= ex.pain_0_10 <= 10):
        ex = _ClinicalExtract(ex.body_area, None, ex.duration_text, ex.associated_symptom)
    done = bool(j.get("done_dialog"))
    return reply or "What else would you like the doctor to know?", ex, done


def _merge_extract_into_session(session: dict[str, Any], ex: _ClinicalExtract, speech: str) -> None:
    if ex.body_area:
        session["twilio_stored_body_area"] = ex.body_area[:120]
    elif speech:
        b = extract_body_area_from_speech(speech) or speech.strip()[:120]
        if b:
            session["twilio_stored_body_area"] = b
    if ex.pain_0_10 is not None:
        session["twilio_pain_score"] = ex.pain_0_10
    else:
        p = parse_pain_0_10(speech)
        if p is not None:
            session["twilio_pain_score"] = p
    if ex.duration_text:
        session["twilio_stored_duration"] = ex.duration_text[:120]
    else:
        d = extract_duration_from_speech(speech)
        if d:
            session["twilio_stored_duration"] = d
    if ex.associated_symptom:
        assoc = list(session.get("collected_symptoms") or [])
        if ex.associated_symptom not in assoc:
            assoc.append(ex.associated_symptom[:80])
            session["collected_symptoms"] = assoc[:20]


def clinical_sufficiency_met(session: dict[str, Any]) -> bool:
    """Enough for remote triage tail: body + pain + duration present."""
    body = (session.get("twilio_stored_body_area") or "").strip()
    pain = session.get("twilio_pain_score")
    dur = (session.get("twilio_stored_duration") or "").strip()
    return bool(body) and pain is not None and bool(dur)


async def advance_clinical_dialog_step(
    session: dict[str, Any],
    english_speech: str,
    *,
    anthropic_api_key: str,
    intake_model: str,
    graph: Any | None,
    case_id: str,
) -> IntakeStepResult:
    """
    One turn in clinical_dialog. Updates session; may transition to sq_allergies when done.
    """
    speech = (english_speech or "").strip()
    if not speech:
        return IntakeStepResult(
            "I'm sorry, I didn't hear you. Could you say that again?",
            "clinical_dialog",
            "gather_next",
        )

    session["cd_turn"] = int(session.get("cd_turn") or 0) + 1
    cd_turn = session["cd_turn"]

    # Refresh symptoms from latest utterance
    if speech:
        tags = symptoms_from_chief_text(speech)
        cur = list(session.get("collected_symptoms") or [])
        for t in tags:
            if t not in cur:
                cur.append(t)
        session["collected_symptoms"] = cur[:25]

    kg_questions: list[str] = []
    kg_conditions: list[str] = []
    if graph is not None:
        try:
            from services.navigator_store import get_navigator, persist_navigator

            nav = get_navigator(case_id, graph)
            ctx = nav.process_symptoms(session.get("collected_symptoms") or [])
            persist_navigator(case_id, nav)
            for q in ctx.get("suggested_questions", [])[:5]:
                if isinstance(q, dict):
                    t = (q.get("question") or q.get("text") or "").strip()
                else:
                    t = str(q).strip()
                if t:
                    kg_questions.append(t[:200])
            for c in ctx.get("activated_conditions", [])[:5]:
                if isinstance(c, dict):
                    nm = (c.get("condition") or c.get("name") or "").strip()
                else:
                    nm = str(c).strip()
                if nm:
                    kg_conditions.append(nm)
            session["kg_snapshot"] = {
                "suggested_questions": kg_questions[:5],
                "activated_conditions": kg_conditions[:5],
            }
            qlist = list(session.get("question_queue") or [])
            for q in kg_questions[:4]:
                if q not in qlist:
                    qlist.append(q)
            session["question_queue"] = qlist[:30]
        except Exception as exc:
            logger.warning("[Twilio] clinical_dialog KG failed: %s", exc)

    if not anthropic_api_key:
        # Scripted fallback
        if clinical_sufficiency_met(session):
            return IntakeStepResult(_allergies_prompt_supportive(), "sq_allergies", "gather_next")
        if cd_turn >= MAX_CLINICAL_TURNS:
            return IntakeStepResult(
                "What part of your body is most affected, and how long has this been going on?",
                "sq_body",
                "gather_next",
            )
        return IntakeStepResult(
            "What part of your body is most affected, and when did this start?",
            "clinical_dialog",
            "gather_next",
        )

    try:
        import asyncio
        import anthropic

        client = anthropic.Anthropic(api_key=anthropic_api_key, timeout=10.0)
        chief = (session.get("sq_chief_text") or "").strip()
        sys_prompt = (
            "You are a warm, experienced triage nurse on a phone call. The patient cannot be seen in person. "
            "Use ethos (trust), pathos (care), logos (brief reason each question helps the doctor). "
            "Reply in JSON only:\n"
            '{ "reply_spoken": string (under 380 chars, one short paragraph, spoken English), '
            '"body_area": string or null, "pain_0_10": integer 0-10 or null, "duration": string or null, '
            '"associated_symptom": string or null, "done_dialog": boolean }\n'
            "Set done_dialog true only if you have enough from context OR after offering enough follow-ups; "
            "the system will still ask allergies and medications in fixed steps.\n"
            "Suggested KG follow-ups (use or adapt one): "
            + json.dumps(kg_questions[:4])
            + "\nActivated context: "
            + json.dumps(kg_conditions[:4])
        )
        user_block = (
            f"Chief concern: {chief}\n"
            f"Symptoms so far: {', '.join(session.get('collected_symptoms') or [])}\n"
            f"Known body area: {session.get('twilio_stored_body_area') or 'unknown'}\n"
            f"Pain score: {session.get('twilio_pain_score')}\n"
            f"Duration: {session.get('twilio_stored_duration') or 'unknown'}\n"
            f"Latest patient words: {speech[:800]}\n"
            f"Turn {cd_turn} of {MAX_CLINICAL_TURNS}."
        )

        def _call_claude():
            return client.messages.create(
                model=intake_model,
                max_tokens=500,
                system=sys_prompt,
                messages=[{"role": "user", "content": user_block}],
            )

        r = await asyncio.wait_for(asyncio.to_thread(_call_claude), timeout=12.0)
        raw = (r.content[0].text or "").strip()
        reply, ex, done_flag = _parse_clinical_json(raw)
        _merge_extract_into_session(session, ex, speech)
    except Exception as exc:
        logger.warning("[Twilio] clinical_dialog Claude failed: %s", exc)
        if clinical_sufficiency_met(session):
            return IntakeStepResult(_allergies_prompt_supportive(), "sq_allergies", "gather_next")
        if cd_turn >= MAX_CLINICAL_TURNS:
            return IntakeStepResult(
                "What part of your body is most affected, and how long has this been going on?",
                "sq_body",
                "gather_next",
            )
        return IntakeStepResult(
            "I'm sorry, I didn't quite get that. Where is the discomfort, and how bad is it from zero to ten?",
            "clinical_dialog",
            "gather_next",
        )

    if done_flag or clinical_sufficiency_met(session):
        return IntakeStepResult(_allergies_prompt_supportive(), "sq_allergies", "gather_next")

    if cd_turn >= MAX_CLINICAL_TURNS:
        return IntakeStepResult(
            "What part of your body is most affected, and how long has this been going on?",
            "sq_body",
            "gather_next",
        )

    return IntakeStepResult(reply, "clinical_dialog", "gather_next")


def _allergies_prompt_supportive() -> str:
    return (
        "Do you have any known allergies? If yes, please say the name of your allergy. "
        "If you have NO allergies, please say zero."
    )
