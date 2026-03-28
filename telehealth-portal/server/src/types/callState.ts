// src/types/callState.ts
// ──────────────────────────────────────────────────────────────
// Canonical state types for the LangGraph symptom-collection workflow.
// These types flow through every graph node and are never mutated —
// nodes return partial updates that LangGraph merges via reducers.
// ──────────────────────────────────────────────────────────────

export type UrgencyLevel = "EMERGENCY" | "HIGH" | "MEDIUM" | "LOW";

export type IntakeChannel = "PHONE" | "SMS" | "WEB";

// ── A single collected symptom entry ─────────────────────────
export interface SymptomEntry {
  /** Free-text description extracted by LLM */
  description: string;
  /** Which graph node collected this symptom */
  collectedAt: "symptom_intake" | "follow_up";
  /** ISO timestamp */
  timestamp: string;
}

// ── One turn in the conversation transcript ───────────────────
export interface ConversationTurn {
  role: "system" | "user" | "assistant";
  content: string;
  timestamp: string;
}

// ── Image upload record ───────────────────────────────────────
export interface UploadedImage {
  url: string;
  uploadedAt: string;
}

// ── The runtime state that flows through the graph ───────────
// Mutable fields are optional so partial updates compile cleanly.
export interface CallState {
  // ── Session metadata
  sessionId: string;
  callerId: string;
  intakeChannel: IntakeChannel;
  intakeLanguage: string;
  startedAt: string;

  // ── Consent
  consentGiven: boolean | null;
  consentTimestamp: string | null;

  // ── Accumulated symptoms (CORE — never replaced, only appended)
  symptoms: SymptomEntry[];

  // ── Conversation history (accumulated)
  conversationHistory: ConversationTurn[];

  // ── Pain / body data
  painScore: number | null;           // 0–10
  symptomDurationDays: number | null;
  affectedBodyAreas: string[];

  // ── Images
  uploadedImages: UploadedImage[];
  imageRequestSent: boolean;

  // ── Assessment outputs
  urgencyLevel: UrgencyLevel | null;
  symptomSummary: string | null;

  // ── Control flow
  currentNode: string;
  followUpRound: number;
  maxFollowUpRounds: number;
  isComplete: boolean;
  error: string | null;
}

// ── The finalized case object handed off to the doctor portal ─
export interface FinalizedCase {
  caseId: string;
  sessionId: string;
  callerId: string;
  intakeChannel: IntakeChannel;
  intakeLanguage: string;
  consentGiven: boolean;
  symptoms: SymptomEntry[];
  symptomSummary: string;
  painScore: number;
  symptomDurationDays: number;
  affectedBodyAreas: string[];
  urgencyLevel: UrgencyLevel;
  uploadedImageUrls: string[];
  createdAt: string;
  // The doctor portal maps these into its own PatientCase shape
  rawConversationHistory: ConversationTurn[];
}

// ── Partial update type returned by each graph node ───────────
export type CallStateUpdate = Partial<CallState>;
