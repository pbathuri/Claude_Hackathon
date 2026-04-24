# Phase 08 - Deployment Operations

## Objective
Feature flags for safe deployment, environment separation (demo vs production), and operational kill switches.

## Files Created
- `backend/observability/__init__.py`
- `backend/observability/feature_flags.py`

## Feature Flags

| Flag | Default | Purpose |
|---|---|---|
| `DEMO_MODE` | `1` (on) | Enables demo-safe behavior, relaxed auth, sample data |
| `ENABLE_KG` | `1` (on) | Knowledge graph navigation and backpropagation |
| `ENABLE_EXTERNAL_APIS` | `1` (on) | ICD-11 API, external LLM calls |
| `ENABLE_TTS` | `1` (on) | Text-to-speech via Twilio/ElevenLabs |
| `ENABLE_BACKGROUND_JOBS` | `1` (on) | Async workers for case processing |
| `ENABLE_MOCK_FALLBACK` | `0` (off) | Return mock data when services are unavailable |
| `KILL_SWITCH_PATIENT_AI` | `0` (off) | Emergency disable of all patient-facing AI |

## Usage
```python
from backend.observability.feature_flags import FeatureFlags

if FeatureFlags.DEMO_MODE:
    # skip real auth, use sample data
    ...

if FeatureFlags.KILL_SWITCH_PATIENT_AI:
    return {"error": "Service temporarily unavailable"}
```

`FeatureFlags.summary()` returns a dict of all flags and their current boolean values for health check endpoints.
