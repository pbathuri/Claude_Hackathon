# Phase 05 - Portal Sync

## Objective
Fix type mismatches between backend and doctor portal, add demo mode awareness, and align case status enums to the full lifecycle.

## Files Changed
- `doctor-portal/types/index.ts` - type definitions
- `doctor-portal/lib/api.ts` - API client with fallback logic

## Contract Changes

### Doctor.availability
- **Before:** `boolean`
- **After:** `string` (`"online" | "offline" | "busy"`)
- **Reason:** Backend returns a string status, not a boolean. The portal was coercing truthy/falsy which masked "busy" states.

### CaseStatusType (new)
Added a union type covering the full case lifecycle:
```
created → active_intake → intake_complete → pending_review → assigned → in_review → responded → closed
```
Plus branching states: `followup_pending`, `followup_replied`, `escalated`, `expired`, `insufficient_information`.

Replaces the previous `"pending" | "assigned" | "resolved"` which only covered 3 of 13 states.

### Demo Mode Awareness
- `_isUsingMockData` flag set to `true` when `fetchWithFallback` catches an error and returns mock data.
- Exported via `isUsingMockData()` so UI components can display a demo banner.
