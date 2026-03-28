// src/graph/nodes/symptomIntake.ts
// Extracts structured symptom entries from the caller's first
// description. Returns SymptomEntry[] that LangGraph ACCUMULATES
// onto state.symptoms via the reducer in state.ts.

import type { GraphState, GraphStateUpdate } from "../state.js";
import type { ConversationTurn, SymptomEntry } from "../../types/callState.js";
import { extractSymptoms } from "../../services/llm.js";

export async function symptomIntake(
  state: GraphState,
  userInput: string
): Promise<GraphStateUpdate> {
  const userTurn: ConversationTurn = {
    role: "user",
    content: userInput,
    timestamp: new Date().toISOString(),
  };

  // LLM extracts structured symptoms from free-text
  const extracted = await extractSymptoms(userInput, state.intakeLanguage);

  const newSymptoms: SymptomEntry[] = extracted.map((desc) => ({
    description: desc,
    collectedAt: "symptom_intake",
    timestamp: new Date().toISOString(),
  }));

  const followUpPrompt = buildFollowUpPrompt(extracted);
  const assistantTurn: ConversationTurn = {
    role: "assistant",
    content: followUpPrompt,
    timestamp: new Date().toISOString(),
  };

  return {
    // ── ACCUMULATED onto state.symptoms by the reducer ──────
    symptoms: newSymptoms,
    conversationHistory: [userTurn, assistantTurn],
    currentNode: "follow_up_questions",
    followUpRound: 1,
  };
}

function buildFollowUpPrompt(symptoms: string[]): string {
  if (symptoms.length === 0) {
    return "I see. Could you tell me more about what you're experiencing? For example, where does it hurt and when did it start?";
  }
  const listed = symptoms.slice(0, 3).join(", ");
  return `I've noted: ${listed}. Can you tell me how long you've been experiencing these symptoms, and how severe the pain is on a scale of 0 to 10?`;
}
