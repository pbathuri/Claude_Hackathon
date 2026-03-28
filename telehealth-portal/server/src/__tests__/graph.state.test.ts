// src/__tests__/graph.state.test.ts
// ──────────────────────────────────────────────────────────────
// Proves that the Annotation.Root channels accumulate arrays
// rather than replacing them.
//
// LangGraph internals:
//   BinaryOperatorAggregate channels expose:
//     .operator(existing, update) — the reduce function
//     .initialValueFactory()     — returns the default value
// ──────────────────────────────────────────────────────────────

import { describe, it, expect } from "vitest";
import { CallStateAnnotation } from "../graph/state.js";
import type { SymptomEntry, ConversationTurn } from "../types/callState.js";

// Helper — build a SymptomEntry
function makeSymptom(desc: string, node: "symptom_intake" | "follow_up" = "symptom_intake"): SymptomEntry {
  return { description: desc, collectedAt: node, timestamp: new Date().toISOString() };
}

// Helper — build a ConversationTurn
function makeTurn(role: "user" | "assistant", content: string): ConversationTurn {
  return { role, content, timestamp: new Date().toISOString() };
}

// Retrieve the channel's reduce operator and initial value factory
function getChannel(field: keyof typeof CallStateAnnotation.spec) {
  const channel = CallStateAnnotation.spec[field] as {
    operator: (existing: unknown, update: unknown) => unknown;
    initialValueFactory: () => unknown;
  };
  return {
    reduce: (a: unknown, b: unknown) => channel.operator(a, b),
    initial: () => channel.initialValueFactory(),
  };
}

describe("CallStateAnnotation — accumulation channels", () => {
  // ── symptoms: BinaryOperatorAggregate (accumulate) ────────
  it("accumulates symptoms across multiple updates", () => {
    const ch = getChannel("symptoms");

    const batch1: SymptomEntry[] = [makeSymptom("headache"), makeSymptom("fever")];
    const batch2: SymptomEntry[] = [makeSymptom("nausea", "follow_up")];
    const batch3: SymptomEntry[] = [makeSymptom("fatigue", "follow_up")];

    const after1 = ch.reduce([], batch1) as SymptomEntry[];
    const after2 = ch.reduce(after1, batch2) as SymptomEntry[];
    const after3 = ch.reduce(after2, batch3) as SymptomEntry[];

    expect(after3).toHaveLength(4);
    expect(after3.map((s) => s.description)).toEqual([
      "headache", "fever", "nausea", "fatigue",
    ]);
  });

  it("does NOT replace symptoms — each update appends", () => {
    const ch = getChannel("symptoms");

    const first = ch.reduce([], [makeSymptom("chest pain")]) as SymptomEntry[];
    const second = ch.reduce(first, [makeSymptom("shortness of breath", "follow_up")]) as SymptomEntry[];

    expect(second).toHaveLength(2);
    expect(second[0]!.description).toBe("chest pain");
    expect(second[1]!.description).toBe("shortness of breath");
  });

  it("starts with empty array (initialValueFactory)", () => {
    const ch = getChannel("symptoms");
    const initial = ch.initial() as SymptomEntry[];
    expect(Array.isArray(initial)).toBe(true);
    expect(initial).toHaveLength(0);
  });

  // ── conversationHistory: accumulate ──────────────────────
  it("accumulates conversationHistory across multiple updates", () => {
    const ch = getChannel("conversationHistory");

    const turn1 = [makeTurn("assistant", "Please consent"), makeTurn("user", "Yes")];
    const turn2 = [makeTurn("assistant", "Describe symptoms"), makeTurn("user", "I have a headache")];
    const turn3 = [makeTurn("assistant", "Any other symptoms?"), makeTurn("user", "And nausea")];

    const after1 = ch.reduce([], turn1) as ConversationTurn[];
    const after2 = ch.reduce(after1, turn2) as ConversationTurn[];
    const after3 = ch.reduce(after2, turn3) as ConversationTurn[];

    expect(after3).toHaveLength(6);
    expect(after3[0]!.content).toBe("Please consent");
    expect(after3[5]!.content).toBe("And nausea");
  });

  // ── scalar fields: replace (not accumulate) ──────────────
  it("replaces painScore on each update", () => {
    const ch = getChannel("painScore");

    const after = ch.reduce(null, 7);
    expect(after).toBe(7);

    const after2 = ch.reduce(after, 9);
    expect(after2).toBe(9);
  });

  it("replaces urgencyLevel on each update", () => {
    const ch = getChannel("urgencyLevel");

    const after = ch.reduce(null, "HIGH");
    expect(after).toBe("HIGH");

    const after2 = ch.reduce(after, "EMERGENCY");
    expect(after2).toBe("EMERGENCY");
  });

  // ── uploadedImages: accumulate ────────────────────────────
  it("accumulates uploadedImages", () => {
    const ch = getChannel("uploadedImages");

    const img1 = [{ url: "https://s3.example.com/img1.jpg", uploadedAt: new Date().toISOString() }];
    const img2 = [{ url: "https://s3.example.com/img2.jpg", uploadedAt: new Date().toISOString() }];

    const after = ch.reduce(ch.reduce([], img1), img2) as unknown[];
    expect(after).toHaveLength(2);
  });

  // ── Correctness proof ────────────────────────────────────
  it("concatenates rather than replaces on second reduce call", () => {
    const ch = getChannel("symptoms");
    const s1 = makeSymptom("symptom A");
    const s2 = makeSymptom("symptom B", "follow_up");

    const after1 = ch.reduce([], [s1]) as SymptomEntry[];
    const after2 = ch.reduce(after1, [s2]) as SymptomEntry[];

    // If channel were replace-only: after2 would have length 1
    expect(after2.length).toBe(2);
    expect(after2.find((s) => s.description === "symptom A")).toBeDefined();
    expect(after2.find((s) => s.description === "symptom B")).toBeDefined();
  });

  it("initialValueFactory returns a fresh array each call (no shared reference)", () => {
    const ch = getChannel("symptoms");
    const a = ch.initial() as SymptomEntry[];
    const b = ch.initial() as SymptomEntry[];
    a.push(makeSymptom("x"));
    expect(b).toHaveLength(0);
  });
});
