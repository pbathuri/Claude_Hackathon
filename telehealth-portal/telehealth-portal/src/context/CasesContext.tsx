// Global case list + mutations via FastAPI (same contract as doctor-portal).

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { OutcomeSubmission, PatientCase } from "../types";
import { DoctorDecisionStatus, RecommendedAction } from "../types";
import { sortCasesByPriority } from "../utils/priorityQueue";
import {
  getCases,
  assignDoctor as apiAssign,
  submitResponse as apiSubmit,
} from "../lib/api";
import { mapApiCaseToPatientCase } from "../lib/mapCaseFromApi";

interface CasesContextValue {
  cases: PatientCase[];
  casesLoading: boolean;
  casesError: string | null;
  refreshCases: () => Promise<void>;
  getCaseById: (id: string) => PatientCase | undefined;
  markInReview: (caseId: string, doctorId: string) => Promise<void>;
  submitOutcome: (
    caseId: string,
    doctorId: string,
    outcome: OutcomeSubmission
  ) => Promise<void>;
}

const CasesContext = createContext<CasesContextValue | null>(null);

function guidancePayload(outcome: OutcomeSubmission): string {
  const lines = [
    `recommended_action: ${outcome.recommendedAction}`,
    `follow_up_advice: ${outcome.followUpAdvice}`,
    `general_notes: ${outcome.generalNotes}`,
    `language: ${outcome.languageOfCommunication}`,
  ];
  if (outcome.prescriptionDetails) {
    lines.push(`prescription: ${outcome.prescriptionDetails}`);
  }
  if (outcome.treatmentNotes) {
    lines.push(`treatment_notes: ${outcome.treatmentNotes}`);
  }
  if (outcome.referralSuggestion) {
    lines.push(
      `referral: ${outcome.referralSuggestion} (${outcome.referralUrgency || "ROUTINE"})`
    );
  }
  if (outcome.estimatedFollowUpDays != null) {
    lines.push(`follow_up_days: ${outcome.estimatedFollowUpDays}`);
  }
  return lines.join("\n");
}

export function CasesProvider({ children }: { children: ReactNode }) {
  const [cases, setCases] = useState<PatientCase[]>([]);
  const [casesLoading, setCasesLoading] = useState(true);
  const [casesError, setCasesError] = useState<string | null>(null);

  const refreshCases = useCallback(async () => {
    setCasesError(null);
    setCasesLoading(true);
    try {
      const rows = await getCases();
      const mapped = rows.map((r) => mapApiCaseToPatientCase(r) as PatientCase);
      setCases(sortCasesByPriority(mapped));
    } catch (e) {
      setCasesError(e instanceof Error ? e.message : "Failed to load cases");
      setCases([]);
    } finally {
      setCasesLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshCases();
  }, [refreshCases]);

  const getCaseById = (id: string) => cases.find((c) => c.caseId === id);

  const markInReview = useCallback(async (caseId: string, doctorId: string) => {
    try {
      await apiAssign(caseId, doctorId);
    } catch {
      /* assignment may already exist */
    }
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
  }, []);

  const submitOutcome = useCallback(
    async (caseId: string, doctorId: string, outcome: OutcomeSubmission) => {
      const isEmergency =
        outcome.recommendedAction === RecommendedAction.EMERGENCY_ESCALATION ||
        outcome.referralUrgency === "EMERGENCY";

      await apiSubmit(caseId, {
        doctor_id: doctorId,
        guidance_text: guidancePayload(outcome),
        is_emergency_referral: isEmergency,
        compliance_acknowledged: true,
      });

      setCases((prev) =>
        prev.map((c) =>
          c.caseId === caseId
            ? {
                ...c,
                doctorReviewed: 1,
                doctorReviewedAt: c.doctorReviewedAt ?? new Date().toISOString(),
                doctorId,
                doctorDecisionStatus:
                  outcome.recommendedAction === RecommendedAction.EMERGENCY_ESCALATION ||
                  outcome.referralUrgency === "EMERGENCY"
                    ? DoctorDecisionStatus.ESCALATED
                    : DoctorDecisionStatus.COMPLETED,
                outcomeSubmission: outcome,
                updatedAt: new Date().toISOString(),
              }
            : c
        )
      );
    },
    []
  );

  return (
    <CasesContext.Provider
      value={{
        cases,
        casesLoading,
        casesError,
        refreshCases,
        getCaseById,
        markInReview,
        submitOutcome,
      }}
    >
      {children}
    </CasesContext.Provider>
  );
}

export function useCases(): CasesContextValue {
  const ctx = useContext(CasesContext);
  if (!ctx) throw new Error("useCases must be used within <CasesProvider>");
  return ctx;
}
