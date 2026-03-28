# Operations Runbook

## Startup

### Local Development

```bash
cd backend
cp .env.example .env  # Edit with real API keys
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### Production (Render)

1. Push to GitHub main branch
2. Render auto-deploys from /backend directory
3. Start command: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Required env vars: ANTHROPIC_API_KEY, ELEVENLABS_API_KEY, TWILIO_*, SKIP_PIPELINE_ENRICHMENT=1

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| ANTHROPIC_API_KEY | Yes | "" | Claude API key |
| ELEVENLABS_API_KEY | No | "" | ElevenLabs TTS key |
| DEMO_MODE | No | "1" | Bypass auth when "1" |
| KILL_SWITCH_PATIENT_AI | No | "0" | Disable AI responses when "1" |
| SKIP_PIPELINE_ENRICHMENT | No | "0" | Skip ICD-11/WHO API calls on startup |
| DATABASE_URL | No | sqlite:///./telehealth.db | Database connection string |

## Kill Switches

### Disable Patient AI Responses

Set `KILL_SWITCH_PATIENT_AI=1`. Patients receive a safe fallback message directing them to seek local care.

### Disable TTS

Set `ENABLE_TTS=0`. Web caller falls back to browser speech synthesis.

### Disable Knowledge Graph

Set `ENABLE_KG=0`. Triage operates without graph navigation (keywords only).

## Investigating a Case Timeline

1. GET /cases/{case_id}/audit → returns all audit log entries
2. Check conversation_turns table for raw patient/assistant text
3. Check clinical_extractions table for extracted facts and confidence
4. Check AuditLog for status transitions and actor IDs

## Handling a Bad Response Incident

1. Set KILL_SWITCH_PATIENT_AI=1 to stop new AI responses
2. Identify affected cases via audit log
3. Doctor reviews and corrects any guidance
4. Investigate root cause in conversation turns
5. Re-enable AI after fix verified

## Data Purge

```bash
# Delete local database (reseeds on restart)
rm backend/telehealth.db
# Delete uploaded images
rm -rf backend/static/uploads/*
# Delete KG persistence
rm backend/data/knowledge_graph.json
```

## Rotating API Keys

1. Generate new key in provider dashboard
2. Update in Render environment variables
3. Trigger manual redeploy
4. Old key revoked after new deployment confirmed healthy
