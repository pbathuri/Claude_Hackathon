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
  status?: "pending" | "assigned" | "resolved";
  assignedDoctor?: string;
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
