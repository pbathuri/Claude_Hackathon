// src/graph/nodes/collectConsent.ts
// Parses the caller's YES/NO consent response.
// On refusal: marks isComplete=true and logs denial in history.

import type { GraphState, GraphStateUpdate } from "../state.js";
import type { ConversationTurn } from "../../types/callState.js";

const AFFIRMATIVES = new Set(["yes", "yeah", "yep", "sure", "ok", "okay", "agree", "consent", "proceed"]);
const NEGATIVES = new Set(["no", "nope", "refuse", "deny", "stop", "cancel", "disagree"]);

function parseConsent(userInput: string): boolean | null {
  const normalized = userInput.toLowerCase().trim();
  for (const word of AFFIRMATIVES) {
    if (normalized.includes(word)) return true;
  }
  for (const word of NEGATIVES) {
    if (normalized.includes(word)) return false;
  }
  return null; // ambiguous — treat as needing re-prompt
}

export async function collectConsent(
  _state: GraphState,
  userInput: string
): Promise<GraphStateUpdate> {
  const userTurn: ConversationTurn = {
    role: "user",
    content: userInput,
    timestamp: new Date().toISOString(),
  };

  const decision = parseConsent(userInput);

  if (decision === false) {
    const refusalTurn: ConversationTurn = {
      role: "assistant",
      content: "I understand. You have chosen not to consent. This call will now end. Thank you.",
      timestamp: new Date().toISOString(),
    };
    return {
      conversationHistory: [userTurn, refusalTurn],
      consentGiven: false,
      consentTimestamp: new Date().toISOString(),
      isComplete: true,
      currentNode: "end",
    };
  }

  if (decision === null) {
    // Ambiguous — ask again
    const clarifyTurn: ConversationTurn = {
      role: "assistant",
      content: "I'm sorry, I didn't catch that. Please say YES to proceed or NO to decline.",
      timestamp: new Date().toISOString(),
    };
    return {
      conversationHistory: [userTurn, clarifyTurn],
      currentNode: "collect_consent",
    };
  }

  // Consented
  const ackTurn: ConversationTurn = {
    role: "assistant",
    content: "Thank you for consenting. Let's begin. Please describe your main symptoms or what brings you in today.",
    timestamp: new Date().toISOString(),
  };

  return {
    conversationHistory: [userTurn, ackTurn],
    consentGiven: true,
    consentTimestamp: new Date().toISOString(),
    currentNode: "symptom_intake",
  };
}
