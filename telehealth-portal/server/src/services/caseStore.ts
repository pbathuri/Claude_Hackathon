// src/services/caseStore.ts
// In-memory case store. Replace with a database in production.
// The doctor portal polls GET /api/cases to pick up new entries.

import type { FinalizedCase } from "../types/callState.js";

class CaseStore {
  private readonly cases = new Map<string, FinalizedCase>();

  save(c: FinalizedCase): void {
    this.cases.set(c.caseId, c);
  }

  getById(caseId: string): FinalizedCase | undefined {
    return this.cases.get(caseId);
  }

  getAll(): FinalizedCase[] {
    return Array.from(this.cases.values()).sort(
      (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    );
  }

  getBySessionId(sessionId: string): FinalizedCase | undefined {
    for (const c of this.cases.values()) {
      if (c.sessionId === sessionId) return c;
    }
    return undefined;
  }

  /** Remove all entries — used in tests only */
  clear(): void {
    this.cases.clear();
  }

  get size(): number {
    return this.cases.size;
  }
}

// Singleton exported so all modules share the same store
export const caseStore = new CaseStore();
