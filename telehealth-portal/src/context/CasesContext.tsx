// src/context/CasesContext.tsx
// ──────────────────────────────────────────────────────────────
// Manages the patient cases list globally.
// Provides sorted case data and an update mechanism so the
// dashboard and detail view stay in sync without a backend.
// ──────────────────────────────────────────────────────────────

import { createContext, useContext, useState, ReactNode } from "react";
import { PatientCase, OutcomeSubmission, DoctorDecisionStatus } from "../types";
import { MOCK_PATIENT_CASES } from "../MockData/patientCases";
import { sortCasesByPriority } from "../utils/priorityQueue";

interface CasesContextValue {
  cases: PatientCase[];                               // All cases, priority-sorted
  getCaseById: (id: string) => PatientCase | undefined;
  markInReview: (caseId: string, doctorId: string) => void;
  submitOutcome: (caseId: string, doctorId: string, outcome: OutcomeSubmission) => void;
}

const CasesContext = createContext<CasesContextValue | null>(null);

export function CasesProvider({ children }: { children: ReactNode }) {
  // Initialise with mock data, sorted by priority
  const [cases, setCases] = useState<PatientCase[]>(
    sortCasesByPriority(MOCK_PATIENT_CASES)
  );

  const getCaseById = (id: string) => cases.find((c) => c.caseId === id);

  /** Called when a doctor opens a PENDING case → sets it to IN_REVIEW */
  const markInReview = (caseId: string, doctorId: string) => {
    setCases((prev) =>
      prev.map((c) =>
        c.caseId === caseId && c.doctorDecisionStatus === DoctorDecisionStatus.PENDING
          ? {
              ...c,
              doctorReviewed: 1,
              doctorReviewedAt: new Date().toISOString(),
              doctorId,
              doctorDecisionStatus: DoctorDecisionStatus.IN_REVIEW,
              updatedAt: new Date().toISOString(),
            }
          : c
      )
    );
  };

  /** Called when the doctor submits the outcome form */
  const submitOutcome = (
    caseId: string,
    doctorId: string,
    outcome: OutcomeSubmission
  ) => {
    setCases((prev) =>
      prev.map((c) =>
        c.caseId === caseId
          ? {
              ...c,
              doctorReviewed: 1,
              doctorReviewedAt: c.doctorReviewedAt ?? new Date().toISOString(),
              doctorId,
              doctorDecisionStatus:
                outcome.recommendedAction === "EMERGENCY_ESCALATION" ||
                outcome.referralUrgency === "EMERGENCY"
                  ? DoctorDecisionStatus.ESCALATED
                  : DoctorDecisionStatus.COMPLETED,
              outcomeSubmission: outcome,
              updatedAt: new Date().toISOString(),
            }
          : c
      )
    );
  };

  return (
    <CasesContext.Provider value={{ cases, getCaseById, markInReview, submitOutcome }}>
      {children}
    </CasesContext.Provider>
  );
}

export function useCases(): CasesContextValue {
  const ctx = useContext(CasesContext);
  if (!ctx) throw new Error("useCases must be used within <CasesProvider>");
  return ctx;
}
