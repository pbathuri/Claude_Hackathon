// src/graph/nodes/painAssessment.ts
// Parses pain score (0-10), symptom duration, and affected body areas
// from the caller's response. Deterministic parsing with LLM fallback.

import type { GraphState, GraphStateUpdate } from "../state.js";
import type { ConversationTurn } from "../../types/callState.js";
import { extractPainData } from "../../services/llm.js";

export async function painAssessment(
  _state: GraphState,
  userInput: string
): Promise<GraphStateUpdate> {
  const userTurn: ConversationTurn = {
    role: "user",
    content: userInput,
    timestamp: new Date().toISOString(),
  };

  // Try simple regex first, fall back to LLM extraction
  const painScore = extractPainScoreSimple(userInput) ?? (await extractPainData(userInput)).painScore;
  const durationDays = extractDurationSimple(userInput) ?? (await extractPainData(userInput)).durationDays;
  const bodyAreas = extractBodyAreasSimple(userInput);

  const assistantTurn: ConversationTurn = {
    role: "assistant",
    content: "I understand. Would you be able to take a photo of the affected area? I'll send a secure link to your phone. If not, please say no.",
    timestamp: new Date().toISOString(),
  };

  return {
    conversationHistory: [userTurn, assistantTurn],
    painScore: painScore ?? 0,
    symptomDurationDays: durationDays ?? 1,
    affectedBodyAreas: bodyAreas,
    currentNode: "image_request",
  };
}

function extractPainScoreSimple(input: string): number | null {
  const match = input.match(/\b([0-9]|10)\b/);
  if (!match) return null;
  const score = parseInt(match[1]!, 10);
  return score >= 0 && score <= 10 ? score : null;
}

function extractDurationSimple(input: string): number | null {
  const dayMatch = input.match(/(\d+)\s*day/i);
  if (dayMatch) return parseInt(dayMatch[1]!, 10);
  const weekMatch = input.match(/(\d+)\s*week/i);
  if (weekMatch) return parseInt(weekMatch[1]!, 10) * 7;
  const hourMatch = input.match(/(\d+)\s*hour/i);
  if (hourMatch) return Math.max(1, Math.round(parseInt(hourMatch[1]!, 10) / 24));
  if (/yesterday/i.test(input)) return 1;
  if (/this morning|today/i.test(input)) return 1;
  return null;
}

const BODY_AREA_KEYWORDS: string[] = [
  "head", "neck", "chest", "back", "abdomen", "stomach", "arm", "leg",
  "foot", "feet", "hand", "wrist", "knee", "hip", "shoulder", "throat",
  "eye", "ear", "nose", "skin", "lower back", "upper back",
];

function extractBodyAreasSimple(input: string): string[] {
  const lower = input.toLowerCase();
  return BODY_AREA_KEYWORDS.filter((area) => lower.includes(area));
}
