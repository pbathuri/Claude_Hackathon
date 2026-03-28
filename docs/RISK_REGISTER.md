# Risk Register

| ID | Risk | Likelihood | Impact | Mitigation | Status |
|----|------|-----------|--------|------------|--------|
| R1 | AI produces diagnostic-sounding language | Medium | Critical | System prompt guardrails + safety rules + clinician review | Mitigated |
| R2 | Emergency missed due to colloquial description | Medium | Critical | 3-tier detection (keywords + patterns + multilingual) | Mitigated |
| R3 | Mock data shown as real patient data | High (if API down) | Critical | Demo mode banner + feature flag + env-gated fallback | Partially mitigated |
| R4 | Unauthorized access to patient data | High (no auth) | Critical | Auth middleware scaffold + demo mode + role checks | Scaffold only |
| R5 | Wrong priority score due to dual formulas | High | High | Score breakdown model + unified computation path | Partially fixed |
| R6 | Translation loses clinical meaning | Medium | High | Original text preserved + uncertainty flags + clarification | Implemented |
| R7 | Session state lost on restart | Certain (in-memory) | Medium | Outbox model created; migration to Redis pending | Acknowledged |
| R8 | SQLite concurrent write failure | Low (single instance) | Medium | PostgreSQL migration path documented | Acknowledged |
| R9 | Twilio webhook forgery | Medium | High | Request signature validation pending | Open |
| R10 | Image upload abuse | Low | Medium | MIME validation + size limits pending | Open |
| R11 | ICD-11 API unavailable | Medium | Low | Graceful fallback to empty codes; case flag pending | Partial |
| R12 | Knowledge graph cold start | Certain (each deploy) | Low | Seeds from curated data in <1s | Accepted |
