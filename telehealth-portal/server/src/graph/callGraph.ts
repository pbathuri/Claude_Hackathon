// src/graph/callGraph.ts
// Assembles the StateGraph for the symptom-collection workflow.
//
// Node flow:
//
//   policy_notice
//       │
//   collect_consent ─── (no consent) ──► END
//       │
//   symptom_intake
//       │
//   follow_up_questions ◄──────────┐
//       │  (more rounds?)          │
//       │  (no) ───────────────────┘
//       ▼
//   pain_assessment
//       │
//   image_request
//       │
//   urgency_assessment
//       │
//   finalize_case
//       │
//      END
//
// Note: collect_consent, symptom_intake, follow_up_questions, pain_assessment,
// and image_request all require userInput injected at runtime (call webhook).
// These are invoked directly by the route handler rather than wired as pure
// graph edges, because LangGraph doesn't natively support interactive I/O
// across HTTP requests. The graph state is persisted in sessionStore between
// webhook calls.

import { StateGraph, END } from "@langchain/langgraph";
import { CallStateAnnotation } from "./state.js";
import { policyNotice } from "./nodes/policyNotice.js";
import { urgencyAssessment } from "./nodes/urgencyAssessment.js";
import { finalizeCase } from "./nodes/finalizeCase.js";

// ── Build the "auto-advance" subgraph for nodes that don't ────
// need live user input (policy notice → urgency → finalize).
// Interactive nodes are handled directly in the route handler.
export function buildAutoGraph() {
  const graph = new StateGraph(CallStateAnnotation)
    .addNode("policy_notice", policyNotice)
    .addNode("urgency_assessment", urgencyAssessment)
    .addNode("finalize_case", finalizeCase)
    .addEdge("__start__", "policy_notice")
    .addEdge("policy_notice", END)
    .addEdge("urgency_assessment", "finalize_case")
    .addEdge("finalize_case", END);

  return graph.compile();
}

// ── Exported compiled graphs ──────────────────────────────────
export const autoGraph = buildAutoGraph();

// ── Helper: run urgency + finalize against a complete state ──
// Called by the route handler once all interactive nodes are done.
export async function runFinalStage(
  state: typeof CallStateAnnotation.State
): Promise<typeof CallStateAnnotation.State> {
  const result = await autoGraph.invoke(
    { ...state, currentNode: "urgency_assessment" },
    { recursionLimit: 10 }
  );
  return result;
}
