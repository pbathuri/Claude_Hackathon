// ============================================================
// types/index.ts
// Open Access Telehealth Platform — Doctor Portal
// Data Modeling: Interfaces, Const Objects, and Type Aliases
//
// NOTE: TypeScript enums replaced with `const` objects + type aliases
// to comply with `erasableSyntaxOnly` (TypeScript 5.9+).
// Usage is identical: CountryTier.TIER_1, UrgencyLevel.EMERGENCY, etc.
// ============================================================

// ------------------------------------------------------------
// CONST OBJECTS (replaces enums — compatible with TS 5.9 erasableSyntaxOnly)
// ------------------------------------------------------------

/**
 * Jurisdictional Permission Tiers (WHO-aligned mock framework)
 * Determines what actions a doctor is allowed to take for
 * a patient in a given country.
 */
export const CountryTier = {
  TIER_1: 1, // Prescription allowed
  TIER_2: 2, // Limited treatment authority
  TIER_3: 3, // Guidance / referral only
  TIER_4: 4, // Advice only
} as const;
export type CountryTier = typeof CountryTier[keyof typeof CountryTier];

/**
 * Clinical urgency levels — set during AI-assisted phone intake,
 * not modifiable by doctor portal (read-only after intake).
 */
export const UrgencyLevel = {
  EMERGENCY: "EMERGENCY",
  HIGH: "HIGH",
  MEDIUM: "MEDIUM",
  LOW: "LOW",
} as const;
export type UrgencyLevel = typeof UrgencyLevel[keyof typeof UrgencyLevel];

/**
 * Doctor's decision status for a case.
 * Tracks where the case is in the review lifecycle.
 */
export const DoctorDecisionStatus = {
  PENDING: "PENDING",       // Not yet reviewed
  IN_REVIEW: "IN_REVIEW",   // Doctor opened but not submitted
  COMPLETED: "COMPLETED",   // Outcome submitted
  ESCALATED: "ESCALATED",   // Referred to higher-level care
  CLOSED: "CLOSED",         // Case closed with no further action
} as const;
export type DoctorDecisionStatus = typeof DoctorDecisionStatus[keyof typeof DoctorDecisionStatus];

/**
 * Recommended actions a doctor can submit.
 * Available options depend on the country tier.
 */
export const RecommendedAction = {
  PRESCRIBE: "PRESCRIBE",                       // Tier 1 only
  LIMITED_TREATMENT: "LIMITED_TREATMENT",       // Tier 1–2
  REFER_LOCAL: "REFER_LOCAL",                   // Tier 1–3
  REFER_SPECIALIST: "REFER_SPECIALIST",         // Tier 1–3
  GUIDANCE_ONLY: "GUIDANCE_ONLY",               // All tiers
  ADVICE_ONLY: "ADVICE_ONLY",                   // All tiers
  EMERGENCY_ESCALATION: "EMERGENCY_ESCALATION", // All tiers (override)
} as const;
export type RecommendedAction = typeof RecommendedAction[keyof typeof RecommendedAction];

// ------------------------------------------------------------
// DOCTOR (Authentication & Profile)
// ------------------------------------------------------------

/**
 * Doctor profile returned from mock WHO verification API.
 * Populated after successful license validation.
 */
export interface Doctor {
  doctorId: string;
  licenseNumber: string;
  fullName: string;
  specialty: string;
  country: string;
  countryCode: string;
  verificationStatus: "VERIFIED" | "PENDING" | "REJECTED";
  allowedTiers: CountryTier[];
  email: string;
  avatarUrl?: string;
  lastLoginAt: string;
}

// ------------------------------------------------------------
// TIER RULES
// ------------------------------------------------------------

/**
 * Defines what is legally/operationally permitted per tier.
 * Used for Capability Disclosure Card and form validation.
 */
export interface TierRule {
  tier: CountryTier;
  label: string;
  description: string;
  allowedActions: RecommendedAction[];
  restrictions: string[];
  badgeColor: string;
  uiWarning?: string;
}

// ------------------------------------------------------------
// PATIENT CASE — split by data source
// ------------------------------------------------------------

export interface PhoneIntakeData {
  patientAlias: string;
  phoneNumber: string;
  countryCode: string;
  country: string;
  consentGiven: boolean;
  consentTimestamp: string;
  symptomSummary: string;
  affectedBodyArea: string[];
  painScore: number;
  symptomDurationDays: number;
  urgencyLevel: UrgencyLevel;
  uploadedImageUrls: string[];
  intakeChannel: "VOICE" | "SMS" | "COMBINED";
  intakeLanguage: string;
  rawTranscriptRef?: string;
}

export interface DoctorPortalData {
  doctorReviewed: 0 | 1;
  doctorReviewedAt: string | null;
  doctorId: string | null;
  doctorDecisionStatus: DoctorDecisionStatus;
  outcomeSubmission: OutcomeSubmission | null;
}

export interface PatientCase extends PhoneIntakeData, DoctorPortalData {
  caseId: string;
  countryTier: CountryTier;
  createdAt: string;
  updatedAt: string;
}

// ------------------------------------------------------------
// OUTCOME SUBMISSION (Doctor → System)
// ------------------------------------------------------------

export interface OutcomeSubmission {
  submittedAt: string;
  submittedByDoctorId: string;
  recommendedAction: RecommendedAction;
  prescriptionDetails?: string;
  treatmentNotes?: string;
  referralSuggestion?: string;
  referralUrgency?: "ROUTINE" | "URGENT" | "EMERGENCY";
  followUpAdvice: string;
  generalNotes: string;
  estimatedFollowUpDays?: number;
  languageOfCommunication: string;
}

// ------------------------------------------------------------
// PRIORITY QUEUE (Sorting)
// ------------------------------------------------------------

export interface CasePriorityScore {
  caseId: string;
  urgencyScore: number;
  tierScore: number;
  compositScore: number;
}

// ------------------------------------------------------------
// API RESPONSE WRAPPERS
// ------------------------------------------------------------

export interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  error?: string;
  timestamp: string;
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  total: number;
  page: number;
  pageSize: number;
}
