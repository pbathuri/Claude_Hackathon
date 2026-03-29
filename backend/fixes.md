# Backend Bug Fixes

Seven bugs fixed. Each section explains why the fix was necessary, the minimal code change made, and why it does not break the existing workflow.

---

## Fix 1 — FSM Enum Mismatch (`domain/enums.py`, `domain_models/conversation.py`, tests)

### Why it was broken
`CaseStatus` used string values like `"created"`, `"pending_review"`, `"in_review"`, `"responded"` that do not exist in the DB `case_status_enum`. `transition_case_status()` did:

```python
current = CaseStatus(case.status) if case.status in valid_statuses else CaseStatus.CREATED
```

Because no real DB string (e.g. `"open"`, `"pending"`, `"in_progress"`) matched any enum value, `current` always silently fell back to `CaseStatus.CREATED`. Every FSM validation then checked transitions **from CREATED**, not from the case's real status — making the state machine decorative.

### Fix (minimal)
Updated `CaseStatus` string values to exactly match `models.py CASE_STATUS_VALUES`:

| Old enum value | New enum value | DB string |
|---|---|---|
| `"created"` | `"open"` | `"open"` |
| `"pending_review"` | `"pending"` | `"pending"` |
| `"in_review"` | `"in_progress"` | `"in_progress"` |
| `"responded"` | `"resolved"` | `"resolved"` |

Removed enum members with no DB equivalent (`ACTIVE_INTAKE`, `FOLLOWUP_PENDING`, `FOLLOWUP_REPLIED`, `INSUFFICIENT_INFORMATION`) and updated `VALID_TRANSITIONS` accordingly.

`domain_models/conversation.py` had a duplicate `CaseStatus` definition — replaced it with a single import from `domain.enums` so there is now one source of truth.

Test file updated to reference only the surviving enum members.

### Why it does not break the flow
The main flow (`complete_intake`, `move_to_pending`, etc.) sets `case.status` directly with raw strings and **never calls** `transition_case_status()`. Those paths are unaffected. `transition_case_status()` now correctly resolves real DB strings to enum members, so any caller that does use the FSM function will get correct behaviour instead of silent no-ops.

**Files changed:** `domain/enums.py`, `domain_models/conversation.py`, `tests/unit/test_enums_and_state_machine.py`

---

## Fix 2 — Remove `OutboxJob` (`domain/models_ext.py`)

### Why it was broken
`OutboxJob` defined a DB table (`outbox_jobs`) with retry/status/attempts columns implying an async job queue. No code anywhere enqueues jobs into it, polls it, or processes rows from it. The table is created at startup, takes up schema space, and misleads anyone reading the codebase into thinking background jobs are handled.

### Fix (minimal)
Deleted the `OutboxJob` class entirely. Removed the now-unused `Integer` and `Text` SQLAlchemy column imports that were only used by `OutboxJob`.

### Why it does not break the flow
Nothing imports or references `OutboxJob` outside of `models_ext.py` itself. The table is auto-created by SQLAlchemy at startup — removing the class stops the table from being created on a fresh DB, and on an existing DB the empty table simply remains (harmless). No runtime code path touches it.

**Files changed:** `domain/models_ext.py`

---

## Fix 3 & 4 — Write `ConversationTurnRecord` (`routers/caller.py`, `routers/twilio_voice.py`)

### Why it was broken
`ConversationTurnRecord` defined a `conversation_turns` table with per-turn transcript columns (actor type, language, original text, translated text, confidence scores). Neither the browser/LangGraph path (`POST /caller/ai-turn`) nor the Twilio path (`POST /twilio/gather`) ever inserted rows. The entire per-turn audit trail was missing; only a JSON blob in `cases.conversation_log` existed.

### Fix (minimal)
After each AI response is generated in both handlers, two rows are inserted (non-blocking — wrapped in `try/except` so a DB hiccup does not abort the response):

- **Patient turn** — `actor_type="patient"`, stores original text, detected language, and English translation when non-English.
- **AI turn** — `actor_type="assistant"`, stores the translated response and the source language.

`turn_index` is computed as `(turn_number - 1) * 2 + 1` (patient) and `(turn_number - 1) * 2 + 2` (AI), giving a monotonically increasing sequence across a case.

### Why it does not break the flow
The inserts are wrapped in `try/except` with a warning log on failure. A DB error here never raises — the TwiML response or `AITurnResponse` is still returned. Existing `cases.conversation_log` JSON blob is untouched; these rows are additive.

**Files changed:** `routers/caller.py`, `routers/twilio_voice.py`

---

## Fix 5 — Write `ClinicalExtractionRecord` (`services/case_service.py`)

### Why it was broken
`ClinicalExtractionRecord` defined a `clinical_extractions` table for structured per-case extraction data (confidence scores, triage scoring JSON, uncertainty flags). `complete_intake()` — the single function called when a case finishes intake — never inserted a row. The table stayed empty.

### Fix (minimal)
Added a guarded insert at the end of `complete_intake()`, after `SymptomRecord` is written:

```python
existing_extraction = db.query(ClinicalExtractionRecord).filter_by(case_id=case_id).first()
if not existing_extraction:
    db.add(ClinicalExtractionRecord(
        case_id=case_id,
        extraction_json=intake_data,
        overall_confidence=float(intake_data.get("graph_confidence", 0.0)),
        extraction_complete=True,
        uncertainty_flags=intake_data.get("uncertainty_flags", []),
        scoring_json={"triage": triage, "priority_score": case.priority_score},
    ))
```

The existence check guards against the `unique=True` constraint on `case_id` if `complete_intake` were ever called twice for the same case.

### Why it does not break the flow
The insert is part of the same `db.commit()` that already commits `SymptomRecord` and the audit log entry — no extra commit required. The `intake_data` dict is already normalised at this point in the function, so accessing `.get()` keys is safe.

**Files changed:** `services/case_service.py`

---

## Fix 6 — HuggingFace Fallback Dead Code (`config.py`, `routers/caller.py`)

### Why it was broken
`_call_huggingface_medical()` existed as a "secondary LLM fallback" in `_generate_claude_response()`, but the calling code would only reach it after Claude failed — and at that point `ai_response` was already `None`, causing the function to skip directly to `_generate_fallback_message()`. The HF call was reachable in theory but was gated by no flag and would silently fire on any Claude outage, sending patient data to an external model the operator may not have consented to use.

### Fix (minimal)
Added one config constant (default `false`):

```python
# config.py
ENABLE_HUGGINGFACE_FALLBACK = os.getenv("ENABLE_HUGGINGFACE_FALLBACK", "false").lower() in ("1", "true", "yes")
```

Wrapped the HF block in `_generate_claude_response()` with `if ENABLE_HUGGINGFACE_FALLBACK:`. When the flag is off (default), the code path goes: Claude → rule-based fallback, exactly as it was implicitly behaving before.

### Why it does not break the flow
Default is `false`, so runtime behaviour is identical to before. Operators who want the HF fallback can set `ENABLE_HUGGINGFACE_FALLBACK=true` in their environment along with a valid `HF_TOKEN`.

**Files changed:** `config.py`, `routers/caller.py`

---

## Fix 7 — KG Disabled Degrades Silently (`routers/caller.py`)

### Why it was broken
When `ENABLE_KNOWLEDGE_GRAPH=false` (or the KG fails to load), `POST /caller/ai-turn` fell back to a hardcoded list of 19 English symptom keywords with no change to the response shape. The caller (browser simulator, LangGraph agent) had no way to know whether it was receiving graph-guided responses or a dumb keyword scan, making the degradation invisible.

### Fix (minimal)
Added one field to `AITurnResponse`:

```python
kg_mode: str = "full"  # "full" | "keyword_only" | "disabled"
```

Set before the return in `ai_conversation_turn`:

```python
if graph is not None:
    kg_mode = "full"
elif is_knowledge_graph_enabled():
    kg_mode = "keyword_only"   # KG configured but unavailable at runtime
else:
    kg_mode = "disabled"       # ENABLE_KNOWLEDGE_GRAPH=false
```

### Why it does not break the flow
`kg_mode` is an additive field on the response Pydantic model with a default of `"full"`. Existing clients that ignore it are unaffected. Clients that inspect it can adapt their UI or logging accordingly.

**Files changed:** `routers/caller.py`

---

## Summary Table

| # | File(s) changed | Lines added / removed |
|---|---|---|
| 1 | `domain/enums.py`, `domain_models/conversation.py`, `tests/unit/test_enums_and_state_machine.py` | ~15 removed, ~18 added |
| 2 | `domain/models_ext.py` | 15 removed, 1 changed |
| 3 & 4 | `routers/caller.py`, `routers/twilio_voice.py` | ~30 added (non-blocking try/except blocks) |
| 5 | `services/case_service.py` | ~10 added |
| 6 | `config.py`, `routers/caller.py` | 3 added, 1 changed (indent) |
| 7 | `routers/caller.py` | 6 added |
