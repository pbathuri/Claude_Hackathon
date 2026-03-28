// src/services/sessionStore.ts
// In-memory session store mapping sessionId → current GraphState.
// The call route reads/writes here between webhook turns.

import type { GraphState } from "../graph/state.js";

class SessionStore {
  private readonly sessions = new Map<string, GraphState>();

  save(sessionId: string, state: GraphState): void {
    this.sessions.set(sessionId, state);
  }

  get(sessionId: string): GraphState | undefined {
    return this.sessions.get(sessionId);
  }

  delete(sessionId: string): void {
    this.sessions.delete(sessionId);
  }

  clear(): void {
    this.sessions.clear();
  }

  get size(): number {
    return this.sessions.size;
  }
}

export const sessionStore = new SessionStore();
