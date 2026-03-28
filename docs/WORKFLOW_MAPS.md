# Workflow Maps

## 1. Inbound Voice Intake

```mermaid
sequenceDiagram
    participant C as Caller
    participant T as Twilio
    participant B as Backend
    participant KG as Knowledge Graph
    participant AI as Claude AI
    
    C->>T: Dials +1 478 812 5405
    T->>B: POST /twilio/voice (From, CallSid)
    B->>B: parse_phone → country_code
    B->>B: check_teleconsult_allowed
    B->>B: create_case (status: created)
    B-->>T: TwiML: Say disclosure + Gather
    T-->>C: Speaks verbal disclosure
    C->>T: Speaks symptoms
    T->>B: POST /twilio/gather (SpeechResult)
    B->>B: detect_red_flags(text)
    B->>KG: extract_symptoms + navigate
    B->>AI: generate_response(KG context)
    AI-->>B: Follow-up question
    B-->>T: TwiML: Say response + Gather
    Note over C,T: Repeat 3-5 turns
    B->>B: check_sufficiency
    B->>B: submit_case (triage + ICD-11)
    B->>B: transition: active_intake → pending_review
    B-->>T: TwiML: Summary + Hangup
```

## 2. Emergency Short-Circuit

```mermaid
flowchart TD
    A[Patient speaks] --> B{detect_red_flags}
    B -->|IMMEDIATE| C[Emergency path]
    B -->|URGENT| D[Escalation path]
    B -->|NONE| E[Continue intake]
    C --> F[Submit case as RED]
    C --> G[TwiML: Call emergency services]
    C --> H[Hangup]
    D --> I[Flag for urgent review]
    D --> J[Continue with warning]
    E --> K[KG navigation + AI response]
```

## 3. Structured Extraction and Case Finalization

```mermaid
flowchart LR
    A[Raw conversation turns] --> B[Symptom extraction via KG]
    A --> C[Severity/duration regex extraction]
    A --> D[Red flag detection]
    B --> E[ClinicalExtraction artifact]
    C --> E
    D --> E
    E --> F[Triage level computation]
    E --> G[ICD-11 mapping]
    F --> H[ScoreBreakdown]
    G --> H
    H --> I[Case finalized: pending_review]
```

## 4. Image Upload and Review

```mermaid
sequenceDiagram
    participant P as Patient
    participant W as Web/SMS
    participant B as Backend
    participant D as Doctor Portal
    
    P->>W: Opens upload link
    P->>B: POST /caller/upload-image (file)
    B->>B: Validate MIME, size
    B->>B: Store with case_id binding
    B-->>P: Upload success confirmation
    D->>B: GET /cases/patient-cases/{id}
    B-->>D: Case with image URLs
    D->>D: Display images in case detail
```

## 5. Doctor Assignment and Response

```mermaid
stateDiagram-v2
    [*] --> pending_review
    pending_review --> assigned: Doctor assigns
    assigned --> in_review: Doctor opens case
    in_review --> responded: Doctor submits guidance
    responded --> followup_pending: Follow-up scheduled
    responded --> closed: No follow-up needed
    assigned --> expired: SLA timeout
    expired --> pending_review: Requeue
```

## 6. Expiration and Requeue

```mermaid
flowchart TD
    A[Scheduler checks assigned cases] --> B{Assigned > SLA?}
    B -->|Yes| C[transition: assigned → expired]
    C --> D[Audit log: expiration]
    D --> E[Requeue: expired → pending_review]
    E --> F[Priority boost: +10 wait bonus]
    B -->|No| G[Continue monitoring]
```

## 7. Follow-up Scheduling and Reply

```mermaid
sequenceDiagram
    participant B as Backend
    participant P as Patient
    participant D as Doctor
    
    B->>B: Schedule follow-up at 24h/48h
    B->>B: Create OutboxJob (type: followup_sms)
    B->>P: Send follow-up prompt
    P->>B: Reply: better/same/worse
    alt Worse
        B->>B: Create new case or escalate
        B->>D: Notification: patient worse
    else Better/Same
        B->>B: Record reply
        B->>B: transition: followup_pending → closed
    end
```

## 8. Privacy Retention and Deletion

```mermaid
flowchart TD
    A[Retention scheduler] --> B{Case age > retention period?}
    B -->|Yes| C[Purge conversation transcripts]
    C --> D[Purge uploaded images]
    D --> E[Minimize patient record]
    E --> F[Audit: retention_purge]
    B -->|No| G[Skip]
```

## 9. Service-to-Service Auth

```mermaid
flowchart LR
    A[Caller API] -->|X-API-Key header| B[Auth Middleware]
    C[Doctor Portal] -->|X-Doctor-ID header| B
    D[Twilio] -->|Request signature| B
    B -->|Demo mode?| E{DEMO_MODE}
    E -->|Yes| F[Allow all + log warning]
    E -->|No| G{Validate credentials}
    G -->|Valid| H[Set actor context]
    G -->|Invalid| I[401 Unauthorized]
```

## 10. Incident / Degraded Mode / Kill Switch

```mermaid
flowchart TD
    A[KILL_SWITCH_PATIENT_AI=1] --> B[Patient AI responses disabled]
    B --> C[Return safe fallback message]
    C --> D[Route to human immediately]
    E[External API failure] --> F{ENABLE_EXTERNAL_APIS?}
    F -->|Disabled| G[Use cached/local data]
    F -->|Enabled but failing| H[Retry with backoff]
    H --> I{Max retries?}
    I -->|Yes| J[Degrade gracefully]
    I -->|No| H
```
