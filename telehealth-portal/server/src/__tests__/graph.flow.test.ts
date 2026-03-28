// src/__tests__/graph.flow.test.ts
// ──────────────────────────────────────────────────────────────
// End-to-end graph flow test.
// Simulates a full intake call without real LLM calls by injecting
// mock responses via setLlmMock().
//
// The CRITICAL assertion: after symptom_intake + two follow_up rounds,
// state.symptoms contains ALL collected symptoms — not just the last batch.
// ──────────────────────────────────────────────────────────────

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { setLlmMock } from "../services/llm.js";
import { policyNotice } from "../graph/nodes/policyNotice.js";
import { collectConsent } from "../graph/nodes/collectConsent.js";
import { symptomIntake } from "../graph/nodes/symptomIntake.js";
import { followUpQuestions } from "../graph/nodes/followUpQuestions.js";
import { painAssessment } from "../graph/nodes/painAssessment.js";
import { imageRequest } from "../graph/nodes/imageRequest.js";
import { urgencyAssessment } from "../graph/nodes/urgencyAssessment.js";
import { finalizeCase } from "../graph/nodes/finalizeCase.js";
import { caseStore } from "../services/caseStore.js";
import { CallStateAnnotation, type GraphState } from "../graph/state.js";
import type { IntakeChannel } from "../types/callState.js";

// ── Test-only state helpers ───────────────────────────────────
function makeInitialState(overrides: Partial<GraphState> = {}): GraphState {
  return {
    sessionId: "test-session-001",
    callerId: "+1-555-0100",
    intakeChannel: "PHONE" as IntakeChannel,
    intakeLanguage: "en",
    startedAt: new Date().toISOString(),
    consentGiven: null,
    consentTimestamp: null,
    symptoms: [],
    conversationHistory: [],
    painScore: null,
    symptomDurationDays: null,
    affectedBodyAreas: [],
    uploadedImages: [],
    imageRequestSent: false,
    urgencyLevel: null,
    symptomSummary: null,
    currentNode: "policy_notice",
    followUpRound: 0,
    maxFollowUpRounds: 2,
    isComplete: false,
    error: null,
    ...overrides,
  };
}

// Merge partial update onto state (mirrors route handler logic)
function applyUpdate(state: GraphState, update: Partial<GraphState>): GraphState {
  const merged = { ...state };
  for (const [key, value] of Object.entries(update)) {
    const k = key as keyof GraphState;
    const existing = merged[k];
    if (Array.isArray(existing) && Array.isArray(value)) {
      // @ts-expect-error dynamic
      merged[k] = [...existing, ...value];
    } else {
      // @ts-expect-error dynamic
      merged[k] = value;
    }
  }
  return merged;
}

// ── Mock LLM responses ────────────────────────────────────────
const MOCK_LLM = {
  extractSymptoms: async (input: string) => {
    // Return different symptoms per call to test accumulation
    if (input.includes("headache")) return ["headache", "fever"];
    if (input.includes("nausea")) return ["nausea", "vomiting"];
    if (input.includes("fatigue")) return ["fatigue", "muscle aches"];
    return ["general discomfort"];
  },
  extractPainData: async () => ({ painScore: 6, durationDays: 3 }),
  classifyUrgency: async () => "HIGH" as const,
  summarizeSymptoms: async (symptoms: string[]) =>
    `Patient reports: ${symptoms.join(", ")}.`,
};

describe("Graph flow — end-to-end symptom accumulation", () => {
  beforeEach(() => {
    setLlmMock(MOCK_LLM);
    caseStore.clear();
  });

  afterEach(() => {
    setLlmMock(null);
    caseStore.clear();
  });

  it("collects symptoms across all nodes and does not lose any", async () => {
    let state = makeInitialState();

    // [1] policy_notice — reads script, no LLM
    const notice = await policyNotice(state);
    state = applyUpdate(state, notice);
    expect(state.currentNode).toBe("collect_consent");
    expect(state.conversationHistory).toHaveLength(1);

    // [2] collect_consent — user says yes
    const consent = await collectConsent(state, "yes I consent");
    state = applyUpdate(state, consent);
    expect(state.consentGiven).toBe(true);
    expect(state.currentNode).toBe("symptom_intake");

    // [3] symptom_intake — first symptom batch: headache, fever
    const intake = await symptomIntake(state, "I have a headache and a fever");
    state = applyUpdate(state, intake);
    expect(state.symptoms).toHaveLength(2);
    expect(state.symptoms.map((s) => s.description)).toContain("headache");
    expect(state.symptoms.map((s) => s.description)).toContain("fever");
    expect(state.currentNode).toBe("follow_up_questions");
    expect(state.followUpRound).toBe(1);

    // [4] follow_up round 1 — adds nausea, vomiting
    const fu1 = await followUpQuestions(state, "Also feeling nausea and vomiting");
    state = applyUpdate(state, fu1);
    // ── CRITICAL: symptoms must now have 4 entries (not 2) ──
    expect(state.symptoms).toHaveLength(4);
    expect(state.symptoms.map((s) => s.description)).toContain("nausea");
    expect(state.symptoms.map((s) => s.description)).toContain("vomiting");
    expect(state.currentNode).toBe("follow_up_questions");

    // [5] follow_up round 2 — adds fatigue, muscle aches
    const fu2 = await followUpQuestions(state, "Also fatigue and muscle aches");
    state = applyUpdate(state, fu2);
    // ── CRITICAL: symptoms must now have 6 entries ───────────
    expect(state.symptoms).toHaveLength(6);
    expect(state.symptoms.map((s) => s.description)).toContain("fatigue");
    expect(state.symptoms.map((s) => s.description)).toContain("muscle aches");
    expect(state.currentNode).toBe("pain_assessment");

    // [6] pain_assessment
    const pain = await painAssessment(state, "Pain is 6 out of 10, started 3 days ago, in my chest");
    state = applyUpdate(state, pain);
    expect(state.painScore).toBe(6);
    expect(state.affectedBodyAreas).toContain("chest");
    expect(state.currentNode).toBe("image_request");

    // [7] image_request — patient declines
    const img = await imageRequest(state, "no thanks");
    state = applyUpdate(state, img);
    expect(state.imageRequestSent).toBe(false);
    expect(state.currentNode).toBe("urgency_assessment");

    // [8] urgency_assessment — reads ALL 6 symptoms
    const urgency = await urgencyAssessment(state);
    state = applyUpdate(state, urgency);
    expect(state.urgencyLevel).toBe("HIGH");
    expect(state.symptomSummary).toMatch(/headache|fever|nausea/i);
    expect(state.currentNode).toBe("finalize_case");

    // [9] finalize_case — builds FinalizedCase from complete state
    const final = await finalizeCase(state);
    state = applyUpdate(state, final);
    expect(state.isComplete).toBe(true);

    // ── Verify the stored case has ALL 6 symptoms ────────────
    const stored = caseStore.getAll()[0];
    expect(stored).toBeDefined();
    expect(stored!.symptoms).toHaveLength(6);
    expect(stored!.urgencyLevel).toBe("HIGH");
    expect(stored!.consentGiven).toBe(true);
  });

  it("terminates early when consent is refused", async () => {
    let state = makeInitialState();

    const notice = await policyNotice(state);
    state = applyUpdate(state, notice);

    const consent = await collectConsent(state, "no I refuse");
    state = applyUpdate(state, consent);

    expect(state.consentGiven).toBe(false);
    expect(state.isComplete).toBe(true);
    expect(state.currentNode).toBe("end");
    expect(state.symptoms).toHaveLength(0);
    expect(caseStore.size).toBe(0);
  });

  it("symptom collectedAt field correctly distinguishes source nodes", async () => {
    let state = makeInitialState({ consentGiven: true, currentNode: "symptom_intake" });

    const intake = await symptomIntake(state, "headache and fever");
    state = applyUpdate(state, intake);
    state = { ...state, followUpRound: 1 };

    const fu = await followUpQuestions(state, "nausea too");
    state = applyUpdate(state, fu);

    const intakeSymptoms = state.symptoms.filter((s) => s.collectedAt === "symptom_intake");
    const followUpSymptoms = state.symptoms.filter((s) => s.collectedAt === "follow_up");

    expect(intakeSymptoms.length).toBeGreaterThan(0);
    expect(followUpSymptoms.length).toBeGreaterThan(0);
  });

  it("conversationHistory accumulates the full transcript", async () => {
    let state = makeInitialState();

    const notice = await policyNotice(state);
    state = applyUpdate(state, notice);

    const consent = await collectConsent(state, "yes");
    state = applyUpdate(state, consent);

    const intake = await symptomIntake(state, "headache");
    state = applyUpdate(state, intake);

    // policy_notice(1) + collect_consent user+ack(2) + symptom_intake user+prompt(2) = 5 turns
    expect(state.conversationHistory.length).toBeGreaterThanOrEqual(5);
  });
});

// Keep TS happy — Annotation.spec is used in graph.state.test only
void CallStateAnnotation;
