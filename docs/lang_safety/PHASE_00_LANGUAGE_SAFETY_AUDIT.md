# Phase 00 - Language Safety & Explainability Audit

**Date:** 2026-03-28
**Scope:** All patient-facing communication, translation pipelines, clinician-facing data, provenance handling

---

## 1. Where Language Is Assumed But Not Stored

| Location | Issue |
|----------|-------|
| `src/graph.py:125-128` | Whisper detects language + probability; logs it but **discards** - never sent to backend |
| `src/main.py:300-308` | Submit payload has **no language field** - backend receives no language metadata from voice pipeline |
| `backend/routers/twilio_voice.py:409-411` | Transcript built from English translations; **original language text overwritten** in message_history |
| `backend/routers/twilio_voice.py:403-478` | `_submit_twilio_case` does not pass `session["language"]` to `complete_intake` |
| `backend/schemas/intake.py` | IntakeData has **no language fields** - symptoms, duration, body_area all assumed English |
| `backend/services/case_service.py:get_case_for_frontend()` | Returns **no language metadata** to doctor portal - `detected_language` on Case is not in response |
| `telehealth-portal/src/types/index.ts` | Case interface has **no language fields** at all |

## 2. Where English Is Implicitly Source of Truth

| Location | Issue |
|----------|-------|
| `src/prompts.py:9-32` | System prompt hardcoded English - LLM always responds in English |
| `src/main.py:53-94` | `_extract_clinical_facts()` uses English-only regex for severity, duration, body area |
| `src/graph.py:145-151` | Emergency keywords English-only - non-English emergencies may not trigger |
| `backend/safety/conversation_guard.py:140-220` | `extract_facts_from_text()` English keyword lists only |
| `backend/services/triage_service.py:92-99` | `EMERGENCY_KEYWORDS` English-only; duplicated from `red_flag_rules.py` |
| `backend/routers/caller.py:280-297` | Emergency detection runs on `all_text` which for non-English callers is the English translation, not original |

## 3. Where Patient Wording Is Overwritten by AI Wording

| Location | Issue |
|----------|-------|
| `src/main.py:277-278` | `transcript_summary` is set to **last assistant message** (`reply_text`), not patient's words |
| `backend/routers/twilio_voice.py:206-209` | `english_speech = translate_to_english(speech_result)` replaces original in message_history |
| `backend/routers/caller.py:955-970` | AI turn pipeline: original user text translated, then **only English stored in message_history** |
| `backend/services/case_service.py:116` | `patient_summary` from intake_data stored as case chief_complaint - could be AI text not patient text |

## 4. Where Translated Text Silently Replaces Original

| Location | Issue |
|----------|-------|
| `backend/routers/twilio_voice.py:208` | `session["message_history"].append({"role":"user","content":english_speech})` - original speech gone |
| `backend/routers/caller.py:941` | For non-English users, `english_text` stored in history but `original user_text` not preserved alongside |
| No location | `ConversationTurn.english_translation` field exists in `domain_models/conversation.py` but **never populated** |

## 5. Where Doctor-Facing Views Hide Provenance

| Location | Issue |
|----------|-------|
| `backend/services/case_service.py:487-530` | `get_case_for_frontend()` returns: `symptomSummary`, `aiStructuredNotes`, `redFlagIndicators` - **no indication which are AI-generated vs patient-reported** |
| `doctor-portal/app/cases/[id]/page.tsx` | AI Structured Notes displayed as plain text - **no "AI-generated" label** |
| `doctor-portal/app/cases/[id]/page.tsx` | Symptom summary displayed - **no indication if this was translated from another language** |
| `doctor-portal/types/index.ts` | `Case` interface has no `detectedLanguage`, `translationUsed`, `originalText`, `translationConfidence` fields |
| `doctor-portal/components/KGInsightsPanel.tsx` | Shows condition probabilities - **no confidence intervals or uncertainty markers** |

## 6. Where Confidence & Uncertainty Are Not Shown

| Location | Issue |
|----------|-------|
| `backend/services/language_service.py:201-229` | `translate_to_english()` returns text or falls back silently - **no confidence score** |
| `backend/services/language_service.py:148-178` | `detect_language()` returns code but **no confidence score** |
| `domain_models/conversation.py:31-38` | `UncertaintyState.TRANSLATION_UNCERTAINTY` exists but **never set anywhere** |
| `domain_models/conversation.py:92-101` | `ExtractedFact.confidence` exists but **never populated** in any code path |
| `backend/routers/caller.py` | Triage breakdown stored but **not sent to doctor portal** in `get_case_for_frontend()` |
| `doctor-portal/` | Zero confidence/uncertainty UI elements anywhere in the portal |

## 7. Where Red-Flag Detection May Fail on Multilingual/Colloquial Input

| Location | Issue |
|----------|-------|
| `src/graph.py:145-151` | 13 English keywords only - a Hindi speaker saying "छाती में दर्द" (chest pain) passes undetected |
| `backend/safety/red_flag_rules.py` | Has multilingual patterns for 7 languages but **coverage is thin** (~6 patterns per language vs ~30 English) |
| `backend/routers/caller.py:270-274` | `detect_red_flags()` called on `all_text` which is already English-translated for non-English callers - multilingual patterns never match |
| `backend/safety/red_flag_rules.py` | No patterns for colloquial/regional terms (e.g., "my chest is paining" in Nigerian English, "mi cabeza explota" in Colombian Spanish) |
| `src/graph.py:139-166` | Voice pipeline emergency check runs **before** translation - if Whisper transcribes in original language, English keywords won't match |

## 8. Where Prompts Need Language-Aware Safety Constraints

| Location | Issue |
|----------|-------|
| `src/prompts.py:9-32` | No instruction to detect or respond in user's language |
| `src/prompts.py:9-32` | No instruction to flag translation ambiguity |
| `backend/routers/caller.py:820-870` | `_generate_claude_response()` system prompt in English only |
| `backend/routers/caller.py:820-870` | Emergency number lookup uses country_code but prompt doesn't instruct model to give emergency advice in user's language |

---

## Summary: Critical Risk Map

```
Patient speaks Hindi → Whisper transcribes in Hindi → Emergency check (English keywords) MISSES IT
→ LLM gets Hindi text + English prompt → Responds in English → Patient may not understand
→ Backend stores English AI response as "transcript_summary" → Doctor sees English text
→ Doctor has NO IDEA patient spoke Hindi → No original text visible → No translation warning
```

**The system appears to work for English speakers but silently degrades for everyone else.**
