// ============================================================
// src/utils/priorityQueue.ts
// Priority Queue Sorting Logic
//
// Cases are sorted by a composite score:
//   score = urgencyScore * 10 + tierScore
//
// Lower score = higher priority (appears first in inbox).
//
// Urgency scores:  EMERGENCY=1 | HIGH=2 | MEDIUM=3 | LOW=4
// Tier scores:     Tier 1=1    | Tier 2=2 | Tier 3=3 | Tier 4=4
//
// Example rankings:
//   EMERGENCY + Tier 1 → 11 (highest priority)
//   EMERGENCY + Tier 4 → 14
//   HIGH      + Tier 1 → 21
//   LOW       + Tier 4 → 44 (lowest priority)
//
// Rationale: emergency cases are always surfaced first regardless of
// jurisdiction; within the same urgency band, cases from higher-authority
// jurisdictions appear first because the doctor can take more decisive action.
// ============================================================

import { UrgencyLevel, type PatientCase, type CasePriorityScore } from "../types";

const URGENCY_SCORE: Record<UrgencyLevel, number> = {
  [UrgencyLevel.EMERGENCY]: 1,
  [UrgencyLevel.HIGH]: 2,
  [UrgencyLevel.MEDIUM]: 3,
  [UrgencyLevel.LOW]: 4,
};

/**
 * Computes the numeric priority score for a single case.
 * Lower number = higher priority.
 */
export function computePriorityScore(c: PatientCase): CasePriorityScore {
  const urgencyScore = URGENCY_SCORE[c.urgencyLevel];
  const tierScore = c.countryTier as number; // Tier 1–4 maps directly
  return {
    caseId: c.caseId,
    urgencyScore,
    tierScore,
    compositScore: urgencyScore * 10 + tierScore,
  };
}

/**
 * Sorts an array of patient cases by descending priority.
 * Does NOT mutate the original array.
 *
 * @param cases - Unsorted list of patient cases
 * @returns New array sorted highest → lowest priority
 */
export function sortCasesByPriority(cases: PatientCase[]): PatientCase[] {
  return [...cases].sort((a, b) => {
    const scoreA = computePriorityScore(a).compositScore;
    const scoreB = computePriorityScore(b).compositScore;

    if (scoreA !== scoreB) return scoreA - scoreB;

    // Tie-breaker: older cases (earlier createdAt) appear first
    return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
  });
}
