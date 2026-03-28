// src/__tests__/api.routes.test.ts
// ──────────────────────────────────────────────────────────────
// HTTP-level tests for the call and cases API routes.
// Uses supertest-style fetch against the live Express app.
// LLM calls are mocked so no API key is required.
// ──────────────────────────────────────────────────────────────

import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll } from "vitest";
import { setLlmMock } from "../services/llm.js";
import { caseStore } from "../services/caseStore.js";
import { sessionStore } from "../services/sessionStore.js";
import { app } from "../index.js";
import type { AddressInfo } from "net";
import http from "http";

// ── Server lifecycle ──────────────────────────────────────────
let server: http.Server;
let baseUrl: string;

beforeAll(
  () =>
    new Promise<void>((resolve) => {
      server = app.listen(0, () => {
        const port = (server.address() as AddressInfo).port;
        baseUrl = `http://localhost:${port}`;
        resolve();
      });
    })
);

afterAll(
  () =>
    new Promise<void>((resolve) => {
      server.close(() => resolve());
    })
);

// ── Mock LLM ─────────────────────────────────────────────────
const MOCK_LLM = {
  extractSymptoms: async () => ["headache", "fever"],
  extractPainData: async () => ({ painScore: 5, durationDays: 2 }),
  classifyUrgency: async () => "MEDIUM" as const,
  summarizeSymptoms: async () => "Patient reports headache and fever for 2 days.",
};

beforeEach(() => {
  setLlmMock(MOCK_LLM);
});

afterEach(() => {
  setLlmMock(null);
  caseStore.clear();
  sessionStore.clear();
});

// ── Helpers ───────────────────────────────────────────────────
async function post(path: string, body: unknown) {
  const res = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return { status: res.status, body: (await res.json()) as Record<string, unknown> };
}

async function get(path: string) {
  const res = await fetch(`${baseUrl}${path}`);
  return { status: res.status, body: (await res.json()) as Record<string, unknown> };
}

// ── Tests ─────────────────────────────────────────────────────
describe("GET /health", () => {
  it("returns 200 ok", async () => {
    const { status, body } = await get("/health");
    expect(status).toBe(200);
    expect(body["status"]).toBe("ok");
  });
});

describe("POST /api/call/start", () => {
  it("returns a sessionId and opens with the policy script", async () => {
    const { status, body } = await post("/api/call/start", {
      callerId: "+1-555-0001",
      channel: "PHONE",
      language: "en",
    });
    expect(status).toBe(200);
    expect(typeof body["sessionId"]).toBe("string");
    expect(body["currentNode"]).toBe("collect_consent");
    expect(typeof body["message"]).toBe("string");
    expect((body["message"] as string).length).toBeGreaterThan(0);
  });

  it("uses default values when body fields are omitted", async () => {
    const { status, body } = await post("/api/call/start", {});
    expect(status).toBe(200);
    expect(body["sessionId"]).toBeDefined();
  });
});

describe("POST /api/call/turn", () => {
  it("advances state on consent YES", async () => {
    const start = await post("/api/call/start", { callerId: "+1-555-0002" });
    const sessionId = start.body["sessionId"] as string;

    const turn = await post("/api/call/turn", { sessionId, userInput: "yes I consent" });
    expect(turn.status).toBe(200);
    expect(turn.body["currentNode"]).toBe("symptom_intake");
  });

  it("terminates session on consent NO", async () => {
    const start = await post("/api/call/start", { callerId: "+1-555-0003" });
    const sessionId = start.body["sessionId"] as string;

    const turn = await post("/api/call/turn", { sessionId, userInput: "no" });
    expect(turn.status).toBe(200);
    expect(turn.body["isComplete"]).toBe(true);
    expect(turn.body["currentNode"]).toBe("end");
  });

  it("returns 400 when sessionId is missing", async () => {
    const { status } = await post("/api/call/turn", { userInput: "hello" });
    expect(status).toBe(400);
  });

  it("returns 404 for unknown sessionId", async () => {
    const { status } = await post("/api/call/turn", {
      sessionId: "does-not-exist",
      userInput: "hello",
    });
    expect(status).toBe(404);
  });

  it("collects symptoms through full flow and produces a case", async () => {
    const start = await post("/api/call/start", { callerId: "+1-555-0004" });
    const sid = start.body["sessionId"] as string;

    // consent
    await post("/api/call/turn", { sessionId: sid, userInput: "yes" });
    // symptom intake
    await post("/api/call/turn", { sessionId: sid, userInput: "I have a headache and fever" });
    // follow-up 1
    await post("/api/call/turn", { sessionId: sid, userInput: "Also nausea" });
    // follow-up 2
    await post("/api/call/turn", { sessionId: sid, userInput: "fatigue as well" });
    // pain assessment
    await post("/api/call/turn", { sessionId: sid, userInput: "Pain is 5, started 2 days ago, in my head" });
    // image request
    const finalTurn = await post("/api/call/turn", { sessionId: sid, userInput: "no image" });

    expect(finalTurn.body["isComplete"]).toBe(true);
    expect((finalTurn.body["symptomCount"] as number)).toBeGreaterThan(0);

    // Case should be findable via the cases API
    const cases = await get("/api/cases");
    expect(cases.status).toBe(200);
    expect((cases.body["total"] as number)).toBeGreaterThan(0);
  });
});

describe("GET /api/cases", () => {
  it("returns empty list when no cases exist", async () => {
    const { status, body } = await get("/api/cases");
    expect(status).toBe(200);
    expect(body["total"]).toBe(0);
    expect(Array.isArray(body["cases"])).toBe(true);
  });
});

describe("GET /api/cases/:caseId", () => {
  it("returns 404 for non-existent case", async () => {
    const { status } = await get("/api/cases/does-not-exist");
    expect(status).toBe(404);
  });
});

describe("GET /api/call/:sessionId", () => {
  it("returns session state", async () => {
    const start = await post("/api/call/start", { callerId: "+1-555-0005" });
    const sid = start.body["sessionId"] as string;

    const { status, body } = await get(`/api/call/${sid}`);
    expect(status).toBe(200);
    expect(body["sessionId"]).toBe(sid);
    expect(body["currentNode"]).toBe("collect_consent");
  });

  it("returns 404 for unknown session", async () => {
    const { status } = await get("/api/call/unknown-session");
    expect(status).toBe(404);
  });
});
