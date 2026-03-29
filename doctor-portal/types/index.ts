export type CaseStatusType = 
  | 'created' | 'active_intake' | 'intake_complete' 
  | 'pending_review' | 'assigned' | 'in_review'
  | 'responded' | 'followup_pending' | 'followup_replied'
  | 'escalated' | 'expired' | 'closed' | 'insufficient_information';

export interface Case {
  caseId: string;
  patientAlias: string;
  country: string;
  countryTier: number;
  urgency: "High" | "Medium" | "Low";
  symptomSummary: string;
  painScore: number;
  symptomDuration: string;
  bodyArea: string;
  imageUrls: string[];
  consentGiven: boolean;
  submittedAt: string;
  aiStructuredNotes: string;
  redFlagIndicators: string[];
  priorityScore: number;
  status?: CaseStatusType;
  assignedDoctor?: string;
  kgInsights?: KGNavigationResult;
  // Phase 01: Language metadata
  detectedLanguage?: string;
  translationUsed?: boolean;
  // Phase 01: Triage explainability
  triageBreakdown?: TriageBreakdown;
  // Phase 04: Clinician explainability
  explainability?: CaseExplainability;
}

// Phase 01: Explainable triage scoring
export interface TriageBreakdown {
  triage_level: string;
  base_score: number;
  severity_score: number;
  red_flag_score: number;
  symptom_count_score: number;
  duration_score: number;
  kg_confidence_score: number;
  country_tier_score: number;
  total_priority: number;
  explanation: string;
}

// Phase 04: Language/Communication banner
export interface LanguageBanner {
  patient_language: string;
  patient_language_name: string;
  detected_languages: string[];
  translation_used: boolean;
  code_switching_detected: boolean;
  translation_confidence: number;
  detection_method: string;
  risk_level: "none" | "low" | "medium" | "high";
  risk_label: string;
  interpreter_recommended: boolean;
}

// Phase 04: Extraction item with source attribution
export interface ExtractionItem {
  type: string;
  value: string;
  display?: string;
  source: "patient_reported" | "ai_extracted" | "kg_inferred" | "rule_derived";
  source_turn?: number;
  confidence?: number;
  label: string;
}

// Phase 04: Safety trigger
export interface SafetyTrigger {
  rule: string;
  severity: string;
  description: string;
  layer?: string;
}

// Phase 04: Full explainability package
export interface CaseExplainability {
  language_banner: LanguageBanner;
  patient_evidence: Array<{
    turn_number: number;
    original_text: string;
    language: string;
    timestamp?: string;
    channel: string;
    label: string;
    english_translation?: string;
    translation_label?: string;
    translation_confidence?: number;
  }>;
  extraction: {
    items: ExtractionItem[];
    total_facts: number;
    ai_extracted_count: number;
    patient_reported_count: number;
    label: string;
  };
  safety: {
    triage_level: string;
    triage_breakdown?: TriageBreakdown;
    triggers: SafetyTrigger[];
    trigger_count: number;
    emergency_detected: boolean;
    kg_confidence: number;
    label: string;
  };
  ambiguity: {
    unresolved_items: Array<{
      type: string;
      flag: string;
      context: string;
    }>;
    has_unresolved: boolean;
    count: number;
    label: string;
  };
}

export interface Doctor {
  id: string;
  full_name: string;
  specialization: string;
  country_code: string;
  languages: string[];
  availability: string;  // "online" | "offline" | "busy"
  verified: boolean;
}

export interface BackpropResult {
  success: boolean;
  updates_applied?: number;
  message?: string;
}

export interface KGNavigationResult {
  conditions: Array<{
    name: string;
    score: number;
    specialty: string;
  }>;
  recommendedSpecialty: string;
  followUpQuestions: string[];
  bodySystemMapping: Record<string, string[]>;
  graphPaths: Array<{
    from: string;
    to: string;
    weight: number;
    type: string;
  }>;
}

export interface KGStats {
  totalNodes: number;
  totalEdges: number;
  learnedEdges: number;
  specialties: string[];
  lastUpdated: string;
}

export interface HottestPath {
  source: string;
  target: string;
  conductivity: number;
  pathType: string;
}

export interface ConditionResult {
  symptom: string;
  conditions: Array<{
    name: string;
    probability: number;
    severity: string;
  }>;
}
