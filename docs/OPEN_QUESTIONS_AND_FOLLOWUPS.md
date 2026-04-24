# Open Questions and Follow-ups

## Production Readiness

1. PostgreSQL migration with Alembic - required before multi-instance deployment
2. Redis for session state - in-memory sessions lost on restart
3. Real SMS delivery - follow-up "sent" is currently a stub
4. Twilio request signature validation - webhook forgery protection
5. Image upload binding to cases with tokens - orphan file prevention
6. Doctor identity verification workflow - KYC integration needed

## Clinical Validation

1. Emergency detection false negative rate on real-world paraphrases
2. Triage accuracy benchmarking against telephone protocol gold standard
3. Translation accuracy for clinically sensitive terms (pain, breathing, consciousness)
4. Symptom checker accuracy per Wallace et al. systematic review baseline

## Regulatory

1. FDA CDS software classification - is this non-device CDS per 520(o)(1)(E)?
2. Country-specific data protection compliance (NDPA Nigeria, DPDP India, DPA Kenya)
3. WHO SMART Guidelines alignment audit for intake pathways
4. HIPAA applicability if US patients are served

## Architecture

1. Graph database migration for KG (Neo4j / Amazon Neptune)
2. Event-driven architecture for case lifecycle (replacing polling)
3. CDN for uploaded medical images
4. Horizontal scaling strategy for backend
5. FHIR endpoint exposure for EHR integration partners
