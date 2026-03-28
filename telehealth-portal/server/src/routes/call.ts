// src/routes/call.ts
// Webhook endpoint for intake calls.
// Each HTTP POST represents one "turn" in the conversation.
//
// POST /api/call/start   — initialise session (no user input yet)
// POST /api/call/turn    — advance state machine with user input
// GET  /api/call/:id     — get current state for a session

import { Router, type Request, type Response } from "express";
import { v4 as uuidv4 } from "uuid";
import { CallStateAnnotation, type GraphState } from "../graph/state.js";
import { policyNotice } from "../graph/nodes/policyNotice.js";
import { collectConsent } from "../graph/nodes/collectConsent.js";
import { symptomIntake } from "../graph/nodes/symptomIntake.js";
import { followUpQuestions } from "../graph/nodes/followUpQuestions.js";
import { painAssessment } from "../graph/nodes/painAssessment.js";
import { imageRequest } from "../graph/nodes/imageRequest.js";
import { urgencyAssessment } from "../graph/nodes/urgencyAssessment.js";
import { finalizeCase } from "../graph/nodes/finalizeCase.js";
import { sessionStore } from "../services/sessionStore.js";
import type { IntakeChannel } from "../types/callState.js";

export const callRouter = Router();

// ── POST /api/call/start ──────────────────────────────────────
callRouter.post("/start", async (req: Request, res: Response) => {
  const sessionId = uuidv4();
  const { callerId = "unknown", channel = "PHONE", language = "en" } = req.body as {
    callerId?: string;
    channel?: string;
    language?: string;
  };

  // Build initial state using annotation defaults
  const initialState: GraphState = {
    ...CallStateAnnotation.spec,
    sessionId,
    callerId,
    intakeChannel: channel as IntakeChannel,
    intakeLanguage: language,
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
  };

  // Run policy notice (deterministic, no user input needed)
  const update = await policyNotice(initialState);
  const newState = mergeState(initialState, update);
  sessionStore.save(sessionId, newState);

  res.json({
    sessionId,
    currentNode: newState.currentNode,
    message: newState.conversationHistory.at(-1)?.content ?? "",
  });
});

// ── POST /api/call/turn ───────────────────────────────────────
callRouter.post("/turn", async (req: Request, res: Response) => {
  const { sessionId, userInput } = req.body as { sessionId?: string; userInput?: string };

  if (!sessionId || !userInput) {
    res.status(400).json({ error: "sessionId and userInput are required" });
    return;
  }

  const state = sessionStore.get(sessionId);
  if (!state) {
    res.status(404).json({ error: "Session not found" });
    return;
  }

  if (state.isComplete) {
    res.status(400).json({ error: "Session already complete", caseId: state.sessionId });
    return;
  }

  let update;
  try {
    update = await dispatchNode(state, userInput);
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Unknown error";
    res.status(500).json({ error: msg });
    return;
  }

  let newState = mergeState(state, update);

  // If we've moved to urgency_assessment or finalize, run those automatically
  if (newState.currentNode === "urgency_assessment" && !newState.isComplete) {
    const urgUpdate = await urgencyAssessment(newState);
    newState = mergeState(newState, urgUpdate);
  }
  if (newState.currentNode === "finalize_case" && !newState.isComplete) {
    const finalUpdate = await finalizeCase(newState);
    newState = mergeState(newState, finalUpdate);
  }

  sessionStore.save(sessionId, newState);

  res.json({
    sessionId,
    currentNode: newState.currentNode,
    isComplete: newState.isComplete,
    message: newState.conversationHistory.at(-1)?.content ?? "",
    symptomCount: newState.symptoms.length,
  });
});

// ── GET /api/call/:sessionId ──────────────────────────────────
callRouter.get("/:sessionId", (req: Request, res: Response) => {
  const state = sessionStore.get(req.params["sessionId"] ?? "");
  if (!state) {
    res.status(404).json({ error: "Session not found" });
    return;
  }
  res.json({
    sessionId: state.sessionId,
    currentNode: state.currentNode,
    isComplete: state.isComplete,
    symptomCount: state.symptoms.length,
    followUpRound: state.followUpRound,
  });
});

// ── Node dispatcher ───────────────────────────────────────────
async function dispatchNode(state: GraphState, userInput: string) {
  switch (state.currentNode) {
    case "collect_consent":
      return collectConsent(state, userInput);
    case "symptom_intake":
      return symptomIntake(state, userInput);
    case "follow_up_questions":
      return followUpQuestions(state, userInput);
    case "pain_assessment":
      return painAssessment(state, userInput);
    case "image_request":
      return imageRequest(state, userInput);
    default:
      throw new Error(`No handler for node: ${state.currentNode}`);
  }
}

// ── State merge helper (applies partial updates) ──────────────
function mergeState(state: GraphState, update: Partial<GraphState>): GraphState {
  const merged = { ...state };

  for (const [key, value] of Object.entries(update)) {
    const k = key as keyof GraphState;
    const existing = merged[k];

    // Accumulate arrays (mirrors the Annotation reducers in state.ts)
    if (Array.isArray(existing) && Array.isArray(value)) {
      // @ts-expect-error dynamic key assignment
      merged[k] = [...existing, ...value];
    } else {
      // @ts-expect-error dynamic key assignment
      merged[k] = value;
    }
  }

  return merged;
}
