# Phase 04 - Workflow Reliability

## Objective

Prevent illegal state transitions and guarantee that every case status change is validated against a finite state machine before persistence. Add an auditable transition wrapper so the system can never silently corrupt case lifecycle data.

## Files Changed

| File | Change |
|---|---|
| `backend/domain/enums.py` | `VALID_TRANSITIONS` dict and `validate_transition()` function define the legal FSM |
| `backend/services/case_service.py` | New `transition_case_status()` validates target state, applies the change, and writes an audit log entry |

## Key Decisions

1. **Additive, not rewriting** - `transition_case_status` is a new function that existing callers can adopt incrementally. Existing functions (`move_to_pending`, `assign_case`, etc.) are untouched so the running system keeps working during rollout.
2. **FSM as data** - The transition map is a plain dict, not code branches. This makes it trivial to visualize, test, and extend without touching control flow.
3. **CLOSED is terminal** - Once a case reaches `closed`, no transitions are allowed. Re-opening requires creating a new linked case (preserving the audit chain).
4. **Graceful fallback** - If a case carries a legacy status not in the enum, `transition_case_status` defaults to `CREATED` rather than crashing, giving existing data a migration path.
