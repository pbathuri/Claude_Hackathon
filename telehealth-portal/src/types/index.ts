// ============================================================
// types/index.ts
// Open Access Telehealth Platform — Doctor Portal
// Data Modeling: Interfaces, Enums, and Type Guards
// ============================================================

// ------------------------------------------------------------
// ENUMS
// ------------------------------------------------------------

/**
 * Jurisdictional Permission Tiers (WHO-aligned mock framework)
 * Determines what actions a doctor is allowed to take for
 * a patient in a given country.
 */
export enum CountryTier {
  TIER_1 = 1, // Prescription allowed
  TIER_2 = 2, // Limited treatment authority
  TIER_3 = 3, // Guidance / referral only
  TIER_4 = 4, // Advice only
}

/**
 * Clinical urgency levels — set during AI-assisted phone intake,
 * not modifiable by doctor portal (read-only after intake).
 */
export enum UrgencyLevel {
  EMERGENCY = "EMERGENCY",
  HIGH = "HIGH",
  MEDIUM = "MEDIUM",
  LOW = "LOW",
}

/**
 * Doctor's decision status for a case.
 * Tracks where the case is in the review lifecycle.
 */
export enum DoctorDecisionStatus {
  PENDING = "PENDING",         // Not yet reviewed
  IN_REVIEW = "IN_REVIEW",     // Doctor opened but not submitted
  COMPLETED = "COMPLETED",     // Outcome submitted
  ESCALATED = "ESCALATED",     // Referred to higher-level care
  CLOSED = "CLOSED",           // Case closed with no further action
}

/**
 * Recommended actions a doctor can submit.
 * Available options depend on the country tier.
 */
export enum RecommendedAction {
  PRESCRIBE = "PRESCRIBE",             // Tier 1 only
  LIMITED_TREATMENT = "LIMITED_TREATMENT", // Tier 1–2
  REFER_LOCAL = "REFER_LOCAL",         // Tier 1–3
  REFER_SPECIALIST = "REFER_SPECIALIST", // Tier 1–3
  GUIDANCE_ONLY = "GUIDANCE_ONLY",     // All tiers
  ADVICE_ONLY = "ADVICE_ONLY",         // All tiers
  EMERGENCY_ESCALATION = "EMERGENCY_ESCALATION", // All tiers (override)
}

// ------------------------------------------------------------
// DOCTOR (Authentication & Profile)
// ------------------------------------------------------------

/**
 * Doctor profile returned from mock WHO verification API.
 * Populated after successful license validation.
 */
export interface Doctor {
  doctorId: string;           // Internal system ID
  licenseNumber: string;      // WHO-style license input by doctor at login
  fullName: string;
  specialty: string;          // e.g. "General Practice", "Pediatrics"
  country: string;            // Country the license is registered in
  countryCode: string;        // ISO 3166-1 alpha-2, e.g. "KE", "BD"
  verificationStatus: "VERIFIED" | "PENDING" | "REJECTED";
  allowedTiers: CountryTier[];// Which tiers this doctor is cleared to handle
  email: string;
  avatarUrl?: string;
  lastLoginAt: string;        // ISO 8601
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
  label: string;              // Human-readable tier name
  description: string;        // Short explanation for the disclosure card
  allowedActions: RecommendedAction[];
  restrictions: string[];     // Bullet-point restrictions shown to doctor
  badgeColor: string;         // CSS color for UI badge
  uiWarning?: string;         // Optional warning message shown in status bar
}

// ------------------------------------------------------------
// PATIENT CASE — split by data source
// ------------------------------------------------------------

/**
 * Fields collected exclusively during AI-assisted phone/SMS intake.
 * These are READ-ONLY in the doctor portal — never edited post-intake.
 */
export interface PhoneIntakeData {
  // Identity & Consent
  patientAlias: string;           // Anonymized ID, e.g. "Patient #A3F2"
  phoneNumber: string;            // Hashed/masked for privacy, e.g. "+254***5678"
  countryCode: string;            // ISO 3166-1 alpha-2
  country: string;                // Full country name
  consentGiven: boolean;          // Whether verbal consent was collected
  consentTimestamp: string;       // ISO 8601 — when consent was recorded

  // Symptom Data (structured by LLM from voice input)
  symptomSummary: string;         // Free-text LLM-generated summary
  affectedBodyArea: string[];     // e.g. ["chest", "left arm"]
  painScore: number;              // 0–10 scale (patient self-report)
  symptomDurationDays: number;    // How many days symptoms have been present
  urgencyLevel: UrgencyLevel;     // AI-assessed urgency (not doctor-modifiable)

  // Media
  uploadedImageUrls: string[];    // URLs of patient-submitted photos (via SMS link)

  // Intake Metadata
  intakeChannel: "VOICE" | "SMS" | "COMBINED";
  intakeLanguage: string;         // BCP 47 language tag, e.g. "sw", "bn", "en"
  rawTranscriptRef?: string;      // Optional reference to stored transcript
}

/**
 * Fields added or modified exclusively by the Doctor Portal.
 * All doctor-side actions are tracked here.
 */
export interface DoctorPortalData {
  doctorReviewed: 0 | 1;          // 0 = not reviewed, 1 = reviewed (binary flag)
  doctorReviewedAt: string | null; // ISO 8601 or null if not yet reviewed
  doctorId: string | null;         // Which doctor reviewed it
  doctorDecisionStatus: DoctorDecisionStatus;
  outcomeSubmission: OutcomeSubmission | null; // null until doctor submits
}

/**
 * Full Patient Case — union of intake data + portal metadata + system fields.
 */
export interface PatientCase extends PhoneIntakeData, DoctorPortalData {
  caseId: string;             // UUID
  countryTier: CountryTier;   // Looked up from country → tier mapping
  createdAt: string;          // ISO 8601 — when the case was first created
  updatedAt: string;          // ISO 8601 — last modification timestamp
}

// ------------------------------------------------------------
// OUTCOME SUBMISSION (Doctor → System)
// ------------------------------------------------------------

/**
 * The form the doctor fills out after reviewing a case.
 * Available fields depend on country tier.
 */
export interface OutcomeSubmission {
  submittedAt: string;            // ISO 8601
  submittedByDoctorId: string;

  recommendedAction: RecommendedAction;

  // Tier 1–2 only: prescription/treatment details
  prescriptionDetails?: string;   // Free text; only shown/required in Tier 1
  treatmentNotes?: string;        // Tier 1–2

  // Tier 1–3: referral
  referralSuggestion?: string;    // Name/type of facility or specialist
  referralUrgency?: "ROUTINE" | "URGENT" | "EMERGENCY";

  // All tiers
  followUpAdvice: string;         // Required for all tiers
  generalNotes: string;           // Required — doctor's free-form notes

  // Metadata
  estimatedFollowUpDays?: number; // How many days until follow-up recommended
  languageOfCommunication: string; // Language doctor used in notes (BCP 47)
}

// ------------------------------------------------------------
// PRIORITY QUEUE (Sorting)
// ------------------------------------------------------------

/**
 * Used by priority queue sorting utility.
 * Lower number = higher priority.
 */
export interface CasePriorityScore {
  caseId: string;
  urgencyScore: number;     // EMERGENCY=1, HIGH=2, MEDIUM=3, LOW=4
  tierScore: number;        // Tier 1=1 (highest permission), Tier 4=4 (lowest)
  compositScore: number;    // urgencyScore * 10 + tierScore (lower = higher priority)
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
