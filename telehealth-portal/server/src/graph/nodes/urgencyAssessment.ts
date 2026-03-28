// src/graph/nodes/urgencyAssessment.ts
// LLM classifies urgency from the COMPLETE accumulated symptom list.
// This is the node that proves the accumulation fix works — it reads
// ALL symptoms from all previous rounds, not just the last batch.

import type { GraphState, GraphStateUpdate } from "../state.js";
import type { ConversationTurn } from "../../types/callState.js";
import { classifyUrgency, summarizeSymptoms } from "../../services/llm.js";

export async function urgencyAssessment(
  state: GraphState
): Promise<GraphStateUpdate> {
  // ── Read ALL accumulated symptoms ────────────────────────
  const allSymptoms = state.symptoms;

  if (allSymptoms.length === 0) {
    return {
      urgencyLevel: "LOW",
      symptomSummary: "No symptoms reported.",
      currentNode: "finalize_case",
    };
  }

  const symptomDescriptions = allSymptoms.map((s) => s.description);

  const [urgencyLevel, summary] = await Promise.all([
    classifyUrgency(symptomDescriptions, state.painScore, state.symptomDurationDays),
    summarizeSymptoms(symptomDescriptions),
  ]);

  const assistantTurn: ConversationTurn = {
    role: "assistant",
    content: `Thank you for providing all of this information. I've completed your intake assessment. A licensed physician will review your case shortly. ${urgencyLevel === "EMERGENCY" ? "Given the severity of your symptoms, please seek immediate emergency care." : "Please remain available and we will follow up with you."}`,
    timestamp: new Date().toISOString(),
  };

  return {
    conversationHistory: [assistantTurn],
    urgencyLevel,
    symptomSummary: summary,
    currentNode: "finalize_case",
  };
}
