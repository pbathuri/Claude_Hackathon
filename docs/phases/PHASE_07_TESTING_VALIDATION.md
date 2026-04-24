# Phase 07 - Testing & Validation

## Objective

Establish a layered test suite covering domain logic, safety-critical paths, interoperability adapters, and API contract stability.

## Test Structure

```
backend/tests/
├── __init__.py
├── unit/
│   ├── __init__.py
│   ├── test_enums_and_state_machine.py
│   ├── test_safety_engine.py
│   └── test_fhir_mappers.py
├── contract/
│   ├── __init__.py
│   └── test_api_contracts.py
└── fixtures/
    └── golden_cases.json
```

## Coverage Areas

### Unit Tests

| File | Module Under Test | What It Covers |
|------|-------------------|----------------|
| `test_enums_and_state_machine.py` | `domain.enums` | Valid/invalid status transitions, terminal state enforcement, escalation reachability, transition map completeness, triage level enum values |
| `test_safety_engine.py` | `safety.*` | Red-flag keyword detection (chest pain, breathing, stroke, suicidal ideation, pediatric, obstetric), uncertainty assessment levels, conversation sufficiency checks, jurisdiction policy tiers |
| `test_fhir_mappers.py` | `interoperability.fhir_mappers` | Patient, Encounter, Observation, Condition, Consent, and AuditEvent FHIR R4 resource generation |

### Contract Tests

| File | What It Covers |
|------|----------------|
| `test_api_contracts.py` | Response shape validation for `/cases/patient-cases`, `/kg/stats`, `/kg/query`, and `/doctors/` - ensures the backend API matches what `doctor-portal` expects |

### Fixtures

| File | Purpose |
|------|---------|
| `golden_cases.json` | Four curated cases (NG malaria, KE cholera, IN emergency, PH depression) with expected triage, conditions, and specialty for regression testing |

## Running Tests

```bash
# Unit tests only (no server required)
cd backend
python -m pytest tests/unit/ -v

# Contract tests (requires running backend)
TEST_API_URL=http://localhost:8000 python -m pytest tests/contract/ -v

# All tests
python -m pytest tests/ -v
```

## Design Principles

- **Zero false negatives** on safety-critical red-flag detection
- **Contract tests skip gracefully** when the backend is not running (`self.skipTest`)
- **Golden fixtures** provide deterministic regression baselines independent of LLM variability
- **No external dependencies** for unit tests - all run against pure domain logic
