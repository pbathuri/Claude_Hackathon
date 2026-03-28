// src/routes/cases.ts
// REST API consumed by the doctor portal frontend.
//
// GET  /api/cases         — list all finalized cases
// GET  /api/cases/:caseId — get one case by ID

import { Router, type Request, type Response } from "express";
import { caseStore } from "../services/caseStore.js";

export const casesRouter = Router();

// ── GET /api/cases ────────────────────────────────────────────
casesRouter.get("/", (_req: Request, res: Response) => {
  const cases = caseStore.getAll();
  res.json({ cases, total: cases.length });
});

// ── GET /api/cases/:caseId ────────────────────────────────────
casesRouter.get("/:caseId", (req: Request, res: Response) => {
  const c = caseStore.getById(req.params["caseId"] ?? "");
  if (!c) {
    res.status(404).json({ error: "Case not found" });
    return;
  }
  res.json(c);
});
