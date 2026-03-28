// src/graph/state.ts
// ──────────────────────────────────────────────────────────────
// LangGraph state schema for the symptom-collection workflow.
//
// CRITICAL ARCHITECTURE NOTE — Array Accumulation:
// ─────────────────────────────────────────────────
// By default, LangGraph REPLACES array fields on every node update.
// This silently destroys symptoms collected in earlier nodes when a
// later node (e.g. follow_up) returns new SymptomEntry values.
//
// The fix is explicit accumulation reducers on every array field:
//
//   symptoms: Annotation<SymptomEntry[]>({
//     reducer: (existing, update) => [...existing, ...update],
//     default: () => [],
//   })
//
// With this reducer, each node appends to the array rather than
// replacing it. The FinalizedCase built at the end therefore
// contains the COMPLETE symptom list from ALL rounds of questioning.
// ──────────────────────────────────────────────────────────────

import { Annotation } from "@langchain/langgraph";
import type {
  SymptomEntry,
  ConversationTurn,
  UploadedImage,
  UrgencyLevel,
  IntakeChannel,
} from "../types/callState.js";

// ── Accumulation helper — merges incoming array onto existing ─
function accumulate<T>(existing: T[], incoming: T[]): T[] {
  return [...existing, ...incoming];
}

// ── Replace helper — standard LangGraph last-write-wins ───────
function replace<T>(existing: T, incoming: T): T {
  // explicit no-op replacement (same as default behavior, but clear)
  void existing;
  return incoming;
}

// ── LangGraph state schema ────────────────────────────────────
export const CallStateAnnotation = Annotation.Root({
  // ── Session metadata (replace — set once at session start)
  sessionId: Annotation<string>({
    reducer: replace,
    default: () => "",
  }),
  callerId: Annotation<string>({
    reducer: replace,
    default: () => "",
  }),
  intakeChannel: Annotation<IntakeChannel>({
    reducer: replace,
    default: () => "PHONE" as IntakeChannel,
  }),
  intakeLanguage: Annotation<string>({
    reducer: replace,
    default: () => "en",
  }),
  startedAt: Annotation<string>({
    reducer: replace,
    default: () => new Date().toISOString(),
  }),

  // ── Consent (replace — single determination)
  consentGiven: Annotation<boolean | null>({
    reducer: replace,
    default: () => null,
  }),
  consentTimestamp: Annotation<string | null>({
    reducer: replace,
    default: () => null,
  }),

  // ── Symptoms (ACCUMULATE — core fix)
  // Each node that collects symptoms appends; never replaces.
  symptoms: Annotation<SymptomEntry[]>({
    reducer: accumulate,
    default: () => [],
  }),

  // ── Conversation history (ACCUMULATE — preserves full transcript)
  conversationHistory: Annotation<ConversationTurn[]>({
    reducer: accumulate,
    default: () => [],
  }),

  // ── Pain / body data (replace — single assessment)
  painScore: Annotation<number | null>({
    reducer: replace,
    default: () => null,
  }),
  symptomDurationDays: Annotation<number | null>({
    reducer: replace,
    default: () => null,
  }),
  affectedBodyAreas: Annotation<string[]>({
    reducer: replace,
    default: () => [],
  }),

  // ── Images (ACCUMULATE — patient may upload multiple)
  uploadedImages: Annotation<UploadedImage[]>({
    reducer: accumulate,
    default: () => [],
  }),
  imageRequestSent: Annotation<boolean>({
    reducer: replace,
    default: () => false,
  }),

  // ── Assessment outputs (replace — final LLM determination)
  urgencyLevel: Annotation<UrgencyLevel | null>({
    reducer: replace,
    default: () => null,
  }),
  symptomSummary: Annotation<string | null>({
    reducer: replace,
    default: () => null,
  }),

  // ── Control flow (replace)
  currentNode: Annotation<string>({
    reducer: replace,
    default: () => "policy_notice",
  }),
  followUpRound: Annotation<number>({
    reducer: replace,
    default: () => 0,
  }),
  maxFollowUpRounds: Annotation<number>({
    reducer: replace,
    default: () => 2,
  }),
  isComplete: Annotation<boolean>({
    reducer: replace,
    default: () => false,
  }),
  error: Annotation<string | null>({
    reducer: replace,
    default: () => null,
  }),
});

// ── Exported type alias for node signatures ───────────────────
export type GraphState = typeof CallStateAnnotation.State;
export type GraphStateUpdate = typeof CallStateAnnotation.Update;
