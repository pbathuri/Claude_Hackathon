// src/graph/nodes/policyNotice.ts
// Reads the consent/policy script and injects it as the first
// assistant turn. No LLM call — deterministic system message.

import type { GraphState, GraphStateUpdate } from "../state.js";
import type { ConversationTurn } from "../../types/callState.js";

const POLICY_SCRIPT = `Hello, thank you for calling the TeleHealth intake line.
This call is part of a WHO-affiliated telehealth service.
Before we begin, I need to inform you:
1. This consultation is for informational and triage purposes only.
2. All information you share will be reviewed by a licensed physician.
3. This call may be recorded for quality assurance.
4. Depending on your location, the services available to you may be limited.
Do you consent to proceed with this intake? Please say YES or NO.`;

export async function policyNotice(
  _state: GraphState
): Promise<GraphStateUpdate> {
  const turn: ConversationTurn = {
    role: "assistant",
    content: POLICY_SCRIPT,
    timestamp: new Date().toISOString(),
  };

  return {
    conversationHistory: [turn],
    currentNode: "collect_consent",
  };
}
