// src/services/llm.ts
// Claude API service — all LLM calls go through here.
// Designed to be mockable in tests: set LLM_MOCK=true env var
// or call setLlmMock() to inject stub responses.

import Anthropic from "@anthropic-ai/sdk";
import type { UrgencyLevel } from "../types/callState.js";

// ── Mock interface for testing ────────────────────────────────
export interface LlmMock {
  extractSymptoms?: (input: string, language: string) => Promise<string[]>;
  extractPainData?: (input: string) => Promise<{ painScore: number; durationDays: number }>;
  classifyUrgency?: (symptoms: string[], painScore: number | null, durationDays: number | null) => Promise<UrgencyLevel>;
  summarizeSymptoms?: (symptoms: string[]) => Promise<string>;
}

let activeMock: LlmMock | null = null;

export function setLlmMock(mock: LlmMock | null): void {
  activeMock = mock;
}

// ── Lazy client initialisation ────────────────────────────────
let _client: Anthropic | null = null;
function getClient(): Anthropic {
  if (!_client) {
    _client = new Anthropic({ apiKey: process.env["ANTHROPIC_API_KEY"] });
  }
  return _client;
}

async function askClaude(prompt: string, systemPrompt: string): Promise<string> {
  const resp = await getClient().messages.create({
    model: "claude-haiku-4-5-20251001",
    max_tokens: 512,
    system: systemPrompt,
    messages: [{ role: "user", content: prompt }],
  });
  const block = resp.content[0];
  if (!block || block.type !== "text") throw new Error("Unexpected Claude response format");
  return block.text.trim();
}

// ── extractSymptoms ───────────────────────────────────────────
// Returns an array of symptom description strings from free text.
export async function extractSymptoms(input: string, language: string): Promise<string[]> {
  if (activeMock?.extractSymptoms) return activeMock.extractSymptoms(input, language);

  const system = `You are a medical intake AI. Extract a JSON array of symptom descriptions from the patient input.
Return ONLY a valid JSON array of strings. No markdown, no explanation.
Example: ["headache", "fever for 2 days", "nausea"]
Language hint: ${language}`;

  const raw = await askClaude(input, system);

  try {
    const parsed: unknown = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return (parsed as unknown[]).filter((x): x is string => typeof x === "string");
    }
  } catch {
    // fallback: treat whole input as single symptom
  }
  return input.length > 0 ? [input.substring(0, 200)] : [];
}

// ── extractPainData ───────────────────────────────────────────
export async function extractPainData(
  input: string
): Promise<{ painScore: number; durationDays: number }> {
  if (activeMock?.extractPainData) return activeMock.extractPainData(input);

  const system = `Extract pain score (0-10) and duration in days from patient input.
Return ONLY valid JSON: {"painScore": <number>, "durationDays": <number>}
If not mentioned use: {"painScore": 0, "durationDays": 1}`;

  const raw = await askClaude(input, system);

  try {
    const parsed = JSON.parse(raw) as { painScore?: unknown; durationDays?: unknown };
    return {
      painScore: typeof parsed.painScore === "number" ? parsed.painScore : 0,
      durationDays: typeof parsed.durationDays === "number" ? parsed.durationDays : 1,
    };
  } catch {
    return { painScore: 0, durationDays: 1 };
  }
}

// ── classifyUrgency ───────────────────────────────────────────
export async function classifyUrgency(
  symptoms: string[],
  painScore: number | null,
  durationDays: number | null
): Promise<UrgencyLevel> {
  if (activeMock?.classifyUrgency) {
    return activeMock.classifyUrgency(symptoms, painScore, durationDays);
  }

  const system = `You are a medical triage AI. Classify urgency as one of: EMERGENCY, HIGH, MEDIUM, LOW.
EMERGENCY: chest pain, difficulty breathing, stroke signs, severe bleeding, unconsciousness.
HIGH: high fever, severe pain (8-10), acute injury, severe vomiting/diarrhea.
MEDIUM: moderate pain (4-7), infection signs, persistent symptoms 3+ days.
LOW: mild symptoms, chronic conditions stable, general wellness concerns.
Return ONLY one word: EMERGENCY, HIGH, MEDIUM, or LOW.`;

  const prompt = `Symptoms: ${symptoms.join("; ")}\nPain score: ${painScore ?? "unknown"}/10\nDuration: ${durationDays ?? "unknown"} days`;
  const raw = await askClaude(prompt, system);

  const upper = raw.toUpperCase().trim() as UrgencyLevel;
  const valid: UrgencyLevel[] = ["EMERGENCY", "HIGH", "MEDIUM", "LOW"];
  return valid.includes(upper) ? upper : "MEDIUM";
}

// ── summarizeSymptoms ─────────────────────────────────────────
export async function summarizeSymptoms(symptoms: string[]): Promise<string> {
  if (activeMock?.summarizeSymptoms) return activeMock.summarizeSymptoms(symptoms);

  const system = `Summarize these patient symptoms into a concise 1-2 sentence clinical note.
Write in third person (e.g. "Patient reports..."). Be factual, no diagnosis.`;

  return askClaude(symptoms.join("; "), system);
}
