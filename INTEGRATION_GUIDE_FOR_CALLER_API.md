# Integration Guide: caller-api <-> backend

The backend is running at `http://localhost:8000`. Your caller-api talks to it via 4 HTTP calls — 3 required, 1 optional. Below is exactly where each call goes in your existing code, with copy-paste snippets.

---

## Your current flow (what exists today)

```
[/chat POST]
    │
    ├── parse form fields (symptoms, message_history, audio/text)
    │
    ├── graph.ainvoke(initial_state)
    │       router → speech_to_text → human_interaction → text_to_speech → continue_gate
    │
    └── return JSON { transcript, message, symptoms, message_history, conversation_complete }
```

**The gap:** When `conversation_complete=true`, the symptoms go nowhere. No case gets created, no triage runs, no doctor ever sees it. The four integration points below close that gap.

---

## What to add, file by file

### 1. `src/config.py` — add the backend URL

Add this field inside your `Configuration` class (after `piper_voice`, around line 73):

```python
# ── Backend API ────────────────────────────────────────────
backend_url: str = Field(
    default="http://localhost:8000",
    description="Base URL of the telehealth backend API",
)
```

---

### 2. `src/main.py` — the three integration points

Your `/chat` endpoint needs changes in three places. Here's the exact location for each.

#### 2a. Add httpx import (top of file, after line 8)

```python
import httpx
```

#### 2b. Add a `phone_number` and `case_id` form field to `/chat` (line 88-93)

Your `/chat` signature currently takes `audio`, `text`, `symptoms`, `message_history`. Add two more:

```python
@app.post("/chat")
async def chat(
    request:         Request,
    audio:           Optional[UploadFile] = File(default=None),
    text:            Optional[str]        = Form(default=None),
    symptoms:        str                  = Form(default="[]"),
    message_history: str                  = Form(default="[]"),
    phone_number:    Optional[str]        = Form(default=None),   # NEW — pass on first turn
    case_id:         Optional[str]        = Form(default=None),   # NEW — pass on every turn after first
):
```

#### 2c. Before the graph runs (line 136, after `initial_state` is built) — start session on first turn

This is where you call the backend to register the caller. Insert this block right after line 144 (`"conversation_complete": False,`) and before the `# ── Run graph` comment on line 146:

```python
    # ── Backend integration: start session on first turn ─────────────
    cfg: Configuration = request.app.state.cfg
    backend = cfg.backend_url

    if phone_number and not case_id:
        # First turn — register with backend, get country/tier/disclaimer
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{backend}/caller/session/start", json={
                "phone_number": phone_number,
            })
        if r.status_code == 200:
            session_data = r.json()
            case_id = session_data["case_id"]

            # Play the disclaimer as the first assistant message via TTS
            # The verbal_disclosure field is a ready-to-read script
            disclosure = session_data.get("verbal_disclosure", "")
            if disclosure:
                initial_state["message_history"] = prev_history + [
                    {"role": "assistant", "content": disclosure}
                ]

            # Record consent (patient heard the disclaimer)
            await client.post(f"{backend}/caller/session/consent", json={
                "case_id": case_id,
                "consent_given": True,
            })

            logger.info("[Backend] Session started | case_id=%s | country=%s | tier=%d",
                        case_id, session_data.get("country_name"), session_data.get("country_tier"))
        elif r.status_code == 403:
            # Country not supported — tell caller and hang up
            error_data = r.json().get("detail", {})
            return JSONResponse(content={
                "transcript": None,
                "message": f"We're sorry, telehealth is not yet available in {error_data.get('country', 'your region')}. Please contact local health services.",
                "symptoms": [],
                "message_history": prev_history,
                "audio": None,
                "conversation_complete": True,
                "turns": len(prev_history),
                "case_id": None,
            })
```

#### 2d. After the graph runs and `conversation_complete=true` (line 175, after `response_body` is built) — submit to backend

Insert this block right after line 183 (`"turns": len(history),`) and before the final `logger.info` on line 185:

```python
    # ── Backend integration: submit completed conversation ───────────
    if response_body["conversation_complete"] and case_id:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(f"{backend}/caller/session/submit", json={
                    "case_id":              case_id,
                    "symptoms":             response_body["symptoms"],
                    "message_history":      history,
                    "transcript_summary":   reply_text,
                    "severity":             5,      # TODO: extract from conversation
                    "duration":             "",     # TODO: extract from conversation
                    "body_area":            "",     # TODO: extract from conversation
                })
            if r.status_code == 200:
                backend_result = r.json()
                response_body["backend_case"] = backend_result
                logger.info(
                    "[Backend] Case submitted | case_id=%s | triage=%s | priority=%.0f",
                    backend_result["case_id"],
                    backend_result["triage_level"],
                    backend_result["priority_score"],
                )
        except Exception as exc:
            logger.error("[Backend] Submit failed (non-blocking): %s", exc)

    # Always include case_id in response so the frontend can track it
    response_body["case_id"] = case_id
```

---

### 3. `src/graph.py` — optional: add emergency check after STT

This is optional but valuable. After Whisper transcribes audio, check for emergency keywords before the LLM even runs. If the caller says "chest pain" or "can't breathe", you can short-circuit immediately.

In `speech_to_text` (around line 134, after `return {"transcript": transcript, "audio_input": None}`), you could add an emergency-check node. But the simpler approach is to do it in `main.py` after the graph returns — the backend `/caller/emergency-check` endpoint is fast enough.

If you want it mid-graph, add this as a new node between `speech_to_text` and `human_interaction`:

```python
async def emergency_check(state: MainState, config: RunnableConfig) -> dict:
    """Check transcript for life-threatening keywords before LLM processes it."""
    transcript = state.get("transcript")
    if not transcript:
        return {}

    # This list matches the backend — keep in sync
    EMERGENCY_KEYWORDS = [
        "chest pain", "chest tightness", "can't breathe", "cannot breathe",
        "difficulty breathing", "shortness of breath", "stroke",
        "face drooping", "arm weakness", "slurred speech",
        "severe bleeding", "unconscious", "unresponsive",
        "suicidal", "self-harm", "throat swelling",
    ]
    lower = transcript.lower()
    if any(kw in lower for kw in EMERGENCY_KEYWORDS):
        logger.warning("[Emergency] Detected in transcript: %r", transcript)
        return {
            "conversation_complete": True,
            "message_history": [{
                "role": "assistant",
                "content": "This sounds like it could be a medical emergency. "
                           "Please call emergency services immediately. "
                           "If you are in Kenya, call 999. "
                           "If you are in Nigeria, call 112. "
                           "If you are in India, call 112.",
            }],
        }
    return {}
```

Then wire it into `build_graph()`:

```python
g.add_node("emergency_check", emergency_check)
g.add_edge("speech_to_text", "emergency_check")
g.add_edge("emergency_check", "human_interaction")
# Remove the old direct edge:
# g.add_edge("speech_to_text", "human_interaction")  ← delete this line
```

---

### 4. `src/prompts.py` — update system prompt with safety rules

Your current `human_interaction_prompt` system message (line 9) is generic. Update it to include the safety rules that the backend enforces, so the LLM and backend stay aligned:

```python
human_interaction_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are a medical intake assistant for a WHO-aligned telehealth platform. "
                "You are NOT a doctor. You CANNOT diagnose, prescribe, or treat. "
                "Never say 'it could be X' or speculate on conditions. "
                "Your job is to collect symptoms clearly and empathetically.\n\n"
                "EMERGENCY: If the patient mentions chest pain, difficulty breathing, "
                "stroke symptoms, severe bleeding, loss of consciousness, or self-harm, "
                "immediately tell them to call emergency services.\n\n"
                "Ask clarifying questions to gather symptoms. "
                "If a voice transcript is provided, treat it as the patient's latest "
                "spoken input. Always return a user-facing message and the updated symptom list.\n\n"
                "Try to collect: main complaint, duration, severity (1-10), "
                "other symptoms, medical history, medications, allergies."
            ),
        ),
        (
            "human",
            (
                "Symptoms collected so far: {symptoms}\n\n"
                "Latest voice transcript (if any): {transcript}\n\n"
                "Continue the intake conversation."
            ),
        ),
    ]
)
```

---

## Summary: what calls happen when

```
Turn 1 (first call arrives):
  caller-api /chat  ──POST──>  backend /caller/session/start   (phone_number)
                     <──────   { case_id, verbal_disclosure, country_tier, disclaimer }
                     ──POST──>  backend /caller/session/consent (case_id)
                     then runs graph normally

Turns 2-N (conversation continues):
  caller-api /chat runs graph normally
  (optional: POST /caller/emergency-check after each STT for safety)

Final turn (conversation_complete=true):
  caller-api /chat  ──POST──>  backend /caller/session/submit  (case_id, symptoms, history)
                     <──────   { triage_level, priority_score, icd11_codes, urgency }
  Case is now in the doctor queue.

Later (patient wants to check status):
                     ──GET───>  backend /caller/session/{case_id}
                     <──────   { status, doctorResponse, followUps }
```

---

## What you do NOT need to build

- Triage logic — backend handles it
- ICD-11 code mapping — backend handles it
- Priority scoring — backend handles it
- Country detection — backend does it from the phone number
- Disclaimer/disclosure text — backend generates the exact verbal script per SDD Section 6.4.1
- Case lifecycle — backend manages open -> pending -> assigned -> resolved -> closed

---

## How to test without the backend running

Your code works standalone today — nothing breaks if the backend is down. The `httpx` calls in `main.py` are wrapped in try/except. If the backend is unreachable, the conversation still runs, symptoms still get collected, the user still hears responses — it just doesn't create a case in the system.

## How to test with the backend running

```bash
# Terminal 1: start backend
cd backend && uvicorn main:app --reload --port 8000

# Terminal 2: start caller-api
cd Claude_Hackathon-caller-api && uvicorn src.main:app --reload --port 8001

# Terminal 3: test
python src/live_test.py --url http://localhost:8001 --smoke
```

The smoke test in `live_test.py` works as-is. After the conversation completes, check the backend:
```bash
curl http://localhost:8000/cases/patient-cases | python -m json.tool
```

---

## Backend API docs

Once the backend is running: http://localhost:8000/docs

All caller-api endpoints are grouped under the **caller-api** tag.
