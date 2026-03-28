# Phase 03 — Safety Engine

## Objective

Replace keyword-only emergency detection with a layered, deterministic clinical safety system that catches emergencies in multiple languages and provides structured uncertainty tracking.

## Files Created / Modified

| File | Purpose |
|---|---|
| `backend/safety/__init__.py` | Package marker |
| `backend/safety/red_flag_rules.py` | 3-tier emergency detection: exact keywords → regex patterns → multilingual patterns. Severity levels (IMMEDIATE / URGENT / WARNING) with action routing |
| `backend/safety/uncertainty.py` | `UncertaintyAssessment` — tracks insufficient info, translation uncertainty, code-switching, and escalation triggers |
| `backend/safety/jurisdiction_policy.py` | Country-tier policy matrix: what the AI is allowed to do per jurisdiction (diagnose, treat, prescribe, refer) |
| `backend/safety/conversation_sufficiency.py` | Slot-based completeness check: required vs desired fields, turn/symptom thresholds for safe submission |

## Key Design Decisions

1. **Zero false negatives**: The keyword and pattern lists are deliberately broad. A false positive (over-triage) is always preferable to a missed emergency in a telehealth context.
2. **Backward compatibility**: `detect_red_flags` accepts both the new `country_code` parameter and the legacy `language`/`english_text`/`kg_context` kwargs. `check_emergency_keywords` is preserved as a wrapper. `RedFlagResult.should_complete` is a computed property for existing callers.
3. **Multilingual from the start**: Tier 2b patterns cover Spanish, French, Hindi, Arabic, Swahili, Chinese, and Hausa — matching the platform's target populations. Detection runs on original text (not just translations) so it works even when translation fails.
4. **Severity → action mapping**: `IMMEDIATE` routes to emergency services, `URGENT` escalates to doctor, `WARNING` flags for review. Emergency phone numbers are country-aware.
5. **Jurisdiction policy is declarative**: Each country gets a tier (1-4) controlling what the AI may do. Tier 4 (unknown country) defaults to guidance-only — the most conservative posture.
6. **Conversation sufficiency prevents premature submission**: Cases need required slots (complaint, duration, severity) plus symptom count thresholds. An 8-turn timeout forces submission to avoid infinite loops.

## Testing

Existing tests in `backend/tests/test_phases.py` cover:
- English keyword detection (chest pain, suicidal ideation)
- Spanish/Hindi multilingual detection
- Non-emergency text correctly passes through
- `should_complete` flag behavior
