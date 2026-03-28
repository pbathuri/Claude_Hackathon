// src/graph/nodes/finalizeCase.ts
// Builds a FinalizedCase from the COMPLETE graph state.
// The symptom list here proves accumulation works — it contains
// entries from symptom_intake AND all follow_up rounds.

import { v4 as uuidv4 } from "uuid";
import type { GraphState, GraphStateUpdate } from "../state.js";
import type { ConversationTurn, FinalizedCase } from "../../types/callState.js";
import { caseStore } from "../../services/caseStore.js";

export async function finalizeCase(
  state: GraphState
): Promise<GraphStateUpdate> {
  const finalCase: FinalizedCase = {
    caseId: uuidv4(),
    sessionId: state.sessionId,
    callerId: state.callerId,
    intakeChannel: state.intakeChannel,
    intakeLanguage: state.intakeLanguage,
    consentGiven: state.consentGiven ?? false,

    // ── Complete symptom list from ALL nodes ────────────────
    symptoms: state.symptoms,
    symptomSummary: state.symptomSummary ?? buildFallbackSummary(state),
    painScore: state.painScore ?? 0,
    symptomDurationDays: state.symptomDurationDays ?? 1,
    affectedBodyAreas: state.affectedBodyAreas,
    urgencyLevel: state.urgencyLevel ?? "LOW",
    uploadedImageUrls: state.uploadedImages.map((img) => img.url),
    createdAt: new Date().toISOString(),
    rawConversationHistory: state.conversationHistory,
  };

  // Persist to in-memory store (doctor portal fetches from here)
  caseStore.save(finalCase);

  const closingTurn: ConversationTurn = {
    role: "assistant",
    content: `Your intake is complete. Your case ID is ${finalCase.caseId}. A physician will review your case and contact you. Thank you and take care.`,
    timestamp: new Date().toISOString(),
  };

  return {
    conversationHistory: [closingTurn],
    isComplete: true,
    currentNode: "end",
  };
}

function buildFallbackSummary(state: GraphState): string {
  if (state.symptoms.length === 0) return "No symptoms reported.";
  const descriptions = state.symptoms.map((s) => s.description).join("; ");
  return `Patient reported: ${descriptions}`;
}
