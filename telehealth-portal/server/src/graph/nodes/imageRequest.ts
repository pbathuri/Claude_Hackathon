// src/graph/nodes/imageRequest.ts
// Offers to send a secure image upload link via SMS.
// Patient may accept or decline — either path continues to urgency assessment.

import type { GraphState, GraphStateUpdate } from "../state.js";
import type { ConversationTurn } from "../../types/callState.js";

const ACCEPT_KEYWORDS = ["yes", "yeah", "sure", "ok", "okay", "send", "please"];
const DECLINE_KEYWORDS = ["no", "nope", "skip", "pass", "don't", "dont", "not"];

function wantsImage(input: string): boolean {
  const lower = input.toLowerCase();
  for (const word of DECLINE_KEYWORDS) {
    if (lower.includes(word)) return false;
  }
  for (const word of ACCEPT_KEYWORDS) {
    if (lower.includes(word)) return true;
  }
  return false;
}

export async function imageRequest(
  state: GraphState,
  userInput: string
): Promise<GraphStateUpdate> {
  const userTurn: ConversationTurn = {
    role: "user",
    content: userInput,
    timestamp: new Date().toISOString(),
  };

  const wants = wantsImage(userInput);

  let assistantContent: string;
  let imageRequestSent = false;

  if (wants && state.callerId) {
    // In production: trigger SMS via Twilio/etc. with a signed upload URL.
    // For the hackathon: simulate sending.
    assistantContent = `I've sent a secure photo upload link to your number. You have 10 minutes to upload. We'll proceed regardless — please continue with the assessment.`;
    imageRequestSent = true;
  } else {
    assistantContent = "No problem. We'll proceed without images.";
  }

  const assistantTurn: ConversationTurn = {
    role: "assistant",
    content: assistantContent,
    timestamp: new Date().toISOString(),
  };

  return {
    conversationHistory: [userTurn, assistantTurn],
    imageRequestSent,
    currentNode: "urgency_assessment",
  };
}
