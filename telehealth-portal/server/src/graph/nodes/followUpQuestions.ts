// src/graph/nodes/followUpQuestions.ts
// Asks follow-up questions and collects additional symptom details.
// Runs up to state.maxFollowUpRounds times.
// Returns SymptomEntry[] that ACCUMULATE onto the existing list.

import type { GraphState, GraphStateUpdate } from "../state.js";
import type { ConversationTurn, SymptomEntry } from "../../types/callState.js";
import { extractSymptoms } from "../../services/llm.js";

const FOLLOW_UP_PROMPTS = [
  "Are there any other symptoms? For example, fever, nausea, shortness of breath, or changes in vision?",
  "Have you experienced these symptoms before? Do you have any known allergies or current medications?",
];

export async function followUpQuestions(
  state: GraphState,
  userInput: string
): Promise<GraphStateUpdate> {
  const userTurn: ConversationTurn = {
    role: "user",
    content: userInput,
    timestamp: new Date().toISOString(),
  };

  // Extract any additional symptoms from this follow-up response
  const extracted = await extractSymptoms(userInput, state.intakeLanguage);

  const additionalSymptoms: SymptomEntry[] = extracted.map((desc) => ({
    description: desc,
    collectedAt: "follow_up",
    timestamp: new Date().toISOString(),
  }));

  const nextRound = state.followUpRound + 1;
  const hasMoreRounds = nextRound <= state.maxFollowUpRounds;

  let assistantContent: string;
  let nextNode: string;

  if (hasMoreRounds) {
    const promptIndex = Math.min(state.followUpRound - 1, FOLLOW_UP_PROMPTS.length - 1);
    assistantContent = FOLLOW_UP_PROMPTS[promptIndex] ?? FOLLOW_UP_PROMPTS[FOLLOW_UP_PROMPTS.length - 1]!;
    nextNode = "follow_up_questions";
  } else {
    assistantContent = "Thank you. Now, on a scale of 0 to 10, how would you rate your pain? And which part of your body is most affected?";
    nextNode = "pain_assessment";
  }

  const assistantTurn: ConversationTurn = {
    role: "assistant",
    content: assistantContent,
    timestamp: new Date().toISOString(),
  };

  return {
    // ── ACCUMULATED onto state.symptoms — does NOT replace ───
    symptoms: additionalSymptoms,
    conversationHistory: [userTurn, assistantTurn],
    followUpRound: nextRound,
    currentNode: nextNode,
  };
}
