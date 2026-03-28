"""
Claude API-powered medical intake agent with tool_use for structured output.
Multi-turn conversation collects symptoms, history, medications, allergies,
then outputs a structured intake record with triage classification.
"""
import json
from dataclasses import dataclass, field

import anthropic

from config import ANTHROPIC_API_KEY, INTAKE_MODEL, INTAKE_MAX_TOKENS


SYSTEM_PROMPT = """You are a medical intake assistant for a WHO-aligned telehealth platform serving underserved populations.

⚠️ CRITICAL SAFETY RULES:
1. You are NOT a doctor. You CANNOT diagnose, prescribe, or treat.
2. Every response must include: "I am not a doctor. This is for intake only."
3. EMERGENCY DETECTION — If the patient reports ANY of these, IMMEDIATELY
   set triage_level to "RED" and say "Please call emergency services now":
   - Chest pain or tightness
   - Difficulty breathing / shortness of breath
   - Signs of stroke (face drooping, arm weakness, slurred speech)
   - Severe bleeding or major trauma
   - Loss of consciousness or unresponsiveness
   - Suicidal thoughts or self-harm
   - Allergic reaction with throat swelling
4. NEVER speculate on diagnosis. NEVER say "it could be X."
5. Be empathetic, clear, and use simple language.

INTAKE FLOW — ask one question at a time:
Step 1: Greet, state disclaimer, ask main complaint
Step 2: Duration ("When did this start?")
Step 3: Severity (1-10 scale)
Step 4: Associated symptoms
Step 5: Medical history (chronic conditions)
Step 6: Current medications
Step 7: Allergies
Step 8: Call record_intake tool with structured data

When calling record_intake, also identify:
- body_area: the primary body area affected (Head, Chest, Abdomen, Limbs, Skin, Back, General)
- red_flag_indicators: any concerning symptoms (e.g. "Persistent pain", "Fever", "Breathing difficulty", "Bleeding")

TRIAGE CLASSIFICATION:
- RED: Life-threatening → tell patient to call emergency services
- YELLOW: Urgent but stable (high fever >39°C, persistent vomiting, etc.)
- GREEN: Non-urgent (mild symptoms, routine questions)"""


INTAKE_TOOL = {
    "name": "record_intake",
    "description": "Records structured patient intake data. Call after completing the full intake flow.",
    "input_schema": {
        "type": "object",
        "properties": {
            "main_symptom": {"type": "string", "description": "Primary complaint"},
            "duration": {"type": "string", "description": "How long symptoms have lasted"},
            "severity": {
                "type": "integer", "minimum": 1, "maximum": 10,
                "description": "Patient-reported severity 1-10",
            },
            "associated_symptoms": {
                "type": "array", "items": {"type": "string"},
                "description": "Other symptoms mentioned",
            },
            "medical_history": {
                "type": "array", "items": {"type": "string"},
                "description": "Chronic conditions or past issues",
            },
            "current_medications": {
                "type": "array", "items": {"type": "string"},
                "description": "Medications currently taking",
            },
            "allergies": {
                "type": "array", "items": {"type": "string"},
                "description": "Known allergies",
            },
            "triage_level": {
                "type": "string", "enum": ["RED", "YELLOW", "GREEN"],
                "description": "Urgency classification",
            },
            "recommended_specialty": {
                "type": "string",
                "description": "Medical specialty best suited (e.g. general, cardiology, dermatology)",
            },
            "patient_summary": {
                "type": "string",
                "description": "Brief clinical summary for the reviewing doctor",
            },
            "body_area": {
                "type": "string",
                "description": "Primary body area affected (e.g. Head, Abdomen, Chest, Limbs, Skin, General)",
            },
            "red_flag_indicators": {
                "type": "array", "items": {"type": "string"},
                "description": "Any red-flag symptoms detected (e.g. Persistent pain, Fever, Breathing difficulty)",
            },
        },
        "required": ["main_symptom", "severity", "triage_level", "patient_summary", "body_area"],
    },
}


@dataclass
class IntakeSession:
    session_id: str
    messages: list = field(default_factory=list)
    intake_data: dict | None = None
    is_complete: bool = False
    is_emergency: bool = False


class MedicalIntakeAgent:
    """Manages multi-turn intake conversations via Claude API."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.sessions: dict[str, IntakeSession] = {}

    def get_or_create_session(self, session_id: str) -> IntakeSession:
        if session_id not in self.sessions:
            self.sessions[session_id] = IntakeSession(session_id=session_id)
        return self.sessions[session_id]

    def process_message(self, session_id: str, user_msg: str) -> str:
        """
        Process one user message in the intake conversation.
        Returns the assistant's text response.
        """
        session = self.get_or_create_session(session_id)
        session.messages.append({"role": "user", "content": user_msg})

        response = self.client.messages.create(
            model=INTAKE_MODEL,
            max_tokens=INTAKE_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=[INTAKE_TOOL],
            messages=session.messages,
        )

        text_output = ""
        for block in response.content:
            if block.type == "text":
                text_output += block.text
            elif block.type == "tool_use":
                # Claude called record_intake — intake is complete
                session.intake_data = block.input
                session.is_complete = True
                session.is_emergency = block.input.get("triage_level") == "RED"

                # Acknowledge the tool call to get a final patient-facing message
                session.messages.append({
                    "role": "assistant",
                    "content": response.content,
                })
                session.messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({
                            "status": "recorded",
                            "case_id": session_id,
                        }),
                    }],
                })

                followup = self.client.messages.create(
                    model=INTAKE_MODEL,
                    max_tokens=512,
                    system=SYSTEM_PROMPT,
                    tools=[INTAKE_TOOL],
                    messages=session.messages,
                )
                for fb in followup.content:
                    if fb.type == "text":
                        text_output += fb.text

                return text_output

        # Not complete yet — store assistant turn for context
        session.messages.append({"role": "assistant", "content": response.content})
        return text_output

    def get_intake_result(self, session_id: str) -> dict | None:
        """Return structured intake data if the session is complete."""
        session = self.sessions.get(session_id)
        if session and session.is_complete:
            return session.intake_data
        return None

    def cleanup_session(self, session_id: str):
        """Remove a completed session to free memory."""
        self.sessions.pop(session_id, None)


# Module-level singleton
intake_agent = MedicalIntakeAgent()
