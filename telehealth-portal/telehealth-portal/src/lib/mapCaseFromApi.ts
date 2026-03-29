/**
 * Maps GET /cases/patient-cases JSON → PatientCase for existing UI.
 */

import {
  CountryTier,
  DoctorDecisionStatus,
  type OutcomeSubmission,
  type PatientCase,
  RecommendedAction,
  UrgencyLevel,
} from "../types";
import type { ApiPatientCase } from "./api";
import { getApiBase } from "./api";

export type ExtendedPatientCase = PatientCase & {
  aiStructuredNotes?: { category: string; finding: string; icdCode?: string; confidence?: number }[];
  redFlagIndicators?: string[];
};

function tierFromApi(n: number): CountryTier {
  if (n === 1) return CountryTier.TIER_1;
  if (n === 2) return CountryTier.TIER_2;
  if (n === 3) return CountryTier.TIER_3;
  return CountryTier.TIER_4;
}

function urgencyFromApi(u: string): UrgencyLevel {
  if (u === "High") return UrgencyLevel.HIGH;
  if (u === "Medium") return UrgencyLevel.MEDIUM;
  return UrgencyLevel.LOW;
}

function parseDurationDays(raw: string): number {
  if (!raw || !raw.trim()) return 0;
  const m = raw.match(/(\d+(?:\.\d+)?)/);
  if (!m) return 0;
  const n = parseFloat(m[1]);
  const lower = raw.toLowerCase();
  if (lower.includes("week")) return Math.round(n * 7);
  if (lower.includes("month")) return Math.round(n * 30);
  if (lower.includes("hour")) return 0;
  return Math.round(n);
}

function bodyAreasFromApi(bodyArea: string): string[] {
  const t = bodyArea?.trim();
  if (!t) return ["—"];
  const parts = t.split(/[,;/]/).map((s) => s.trim()).filter(Boolean);
  return parts.length ? parts : [t];
}

function absoluteImageUrls(urls: string[]): string[] {
  const base = getApiBase();
  return urls.map((u) => {
    if (!u) return u;
    if (u.startsWith("http://") || u.startsWith("https://")) return u;
    return `${base}${u.startsWith("/") ? "" : "/"}${u}`;
  });
}

function portalStatusFromApi(status: string | undefined): DoctorDecisionStatus {
  const s = (status || "pending").toLowerCase();
  if (s === "pending" || s === "open" || s === "intake_complete") {
    return DoctorDecisionStatus.PENDING;
  }
  if (s === "assigned" || s === "in_review" || s === "in_progress") {
    return DoctorDecisionStatus.IN_REVIEW;
  }
  if (s === "escalated") return DoctorDecisionStatus.ESCALATED;
  if (s === "closed") return DoctorDecisionStatus.CLOSED;
  if (s === "resolved" || s === "responded") return DoctorDecisionStatus.COMPLETED;
  return DoctorDecisionStatus.PENDING;
}

function notesFromApi(ai: unknown): ExtendedPatientCase["aiStructuredNotes"] {
  if (Array.isArray(ai)) {
    return ai as ExtendedPatientCase["aiStructuredNotes"];
  }
  if (typeof ai === "string" && ai.trim()) {
    return [{ category: "Clinical summary", finding: ai.trim() }];
  }
  return undefined;
}

function stubOutcomeForCompleted(api: ApiPatientCase): OutcomeSubmission {
  const at = api.submittedAt || new Date().toISOString();
  return {
    submittedAt: at,
    submittedByDoctorId: api.assignedDoctor || "system",
    recommendedAction: RecommendedAction.GUIDANCE_ONLY,
    followUpAdvice: "—",
    generalNotes:
      "This case was already marked resolved in the hospital system. Local outcome form was not used for this record.",
    languageOfCommunication: api.detectedLanguage || "en",
  };
}

export function mapApiCaseToPatientCase(api: ApiPatientCase): ExtendedPatientCase {
  const decision = portalStatusFromApi(api.status);
  const submitted = api.submittedAt || new Date().toISOString();
  const hasServerCompletion = decision === DoctorDecisionStatus.COMPLETED;

  return {
    caseId: api.caseId,
    createdAt: submitted,
    updatedAt: submitted,
    countryTier: tierFromApi(Number(api.countryTier) || 3),

    patientAlias: api.patientAlias,
    phoneNumber: "—",
    countryCode: "—",
    country: api.country,
    consentGiven: api.consentGiven,
    consentTimestamp: submitted,

    symptomSummary: api.symptomSummary || "—",
    affectedBodyArea: bodyAreasFromApi(api.bodyArea || ""),
    painScore: typeof api.painScore === "number" ? api.painScore : 0,
    symptomDurationDays: parseDurationDays(api.symptomDuration || ""),
    urgencyLevel: urgencyFromApi(api.urgency),

    uploadedImageUrls: absoluteImageUrls(api.imageUrls || []),
    intakeChannel: "VOICE",
    intakeLanguage: api.detectedLanguage || "en",

    doctorReviewed:
      hasServerCompletion || decision === DoctorDecisionStatus.IN_REVIEW ? 1 : 0,
    doctorReviewedAt:
      hasServerCompletion || decision === DoctorDecisionStatus.IN_REVIEW ? submitted : null,
    doctorId: api.assignedDoctor ?? null,
    doctorDecisionStatus: decision,
    outcomeSubmission: hasServerCompletion ? stubOutcomeForCompleted(api) : null,

    redFlagIndicators: api.redFlagIndicators?.length ? api.redFlagIndicators : undefined,
    aiStructuredNotes: notesFromApi(api.aiStructuredNotes),
  };
}
