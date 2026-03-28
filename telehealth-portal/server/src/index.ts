// src/index.ts
// Express server entry point for the telehealth call service.
// Part 1: AI-assisted phone intake with LangGraph symptom collection.

import express from "express";
import cors from "cors";
import { callRouter } from "./routes/call.js";
import { casesRouter } from "./routes/cases.js";

const app = express();
const PORT = process.env["PORT"] ?? 3001;

// ── Middleware ────────────────────────────────────────────────
app.use(cors());
app.use(express.json());

// ── Routes ────────────────────────────────────────────────────
app.use("/api/call", callRouter);
app.use("/api/cases", casesRouter);

// ── Health check ──────────────────────────────────────────────
app.get("/health", (_req, res) => {
  res.json({ status: "ok", service: "telehealth-call-service", timestamp: new Date().toISOString() });
});

// ── Start ─────────────────────────────────────────────────────
app.listen(PORT, () => {
  console.log(`[telehealth-call-service] Listening on port ${PORT}`);
  console.log(`  POST /api/call/start  — start an intake session`);
  console.log(`  POST /api/call/turn   — advance conversation`);
  console.log(`  GET  /api/cases       — list finalized cases`);
});

export { app };
