import type { Case } from "@/types";

export type ClinicalUrgency = "Low" | "Medium" | "High" | "Critical";

export type ReportStatus = "Pending" | "Submitted";

export type CommunicationPreference = "voice" | "sms" | "phone";

export type MedicalReportPayload = {
  chiefComplaint: string;
  bloodPressure: string;
  heartRate: string;
  temperature: string;
  oxygenSaturation: string;
  painScale: number;
  medications: string;
  allergies: string;
  allergyFlags: string[];
  doctorNotes: string;
  communicationPreference: CommunicationPreference;
  submittedAt: string;
};

export type CaseOverlay = {
  clinicalUrgency?: ClinicalUrgency;
  reportStatus: ReportStatus;
  report?: MedicalReportPayload;
};

const STORAGE_KEY = "whoPortalCaseOverlays";

function readAll(): Record<string, CaseOverlay> {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const j = JSON.parse(raw) as Record<string, CaseOverlay>;
    return j && typeof j === "object" ? j : {};
  } catch {
    return {};
  }
}

function writeAll(data: Record<string, CaseOverlay>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("who-portal-overlays"));
  }
}

export function getCaseOverlay(caseId: string): CaseOverlay {
  const all = readAll();
  return all[caseId] ?? { reportStatus: "Pending" };
}

export function setCaseOverlay(caseId: string, partial: Partial<CaseOverlay>) {
  const all = readAll();
  const prev = all[caseId] ?? { reportStatus: "Pending" as ReportStatus };
  all[caseId] = { ...prev, ...partial };
  writeAll(all);
}

export function subscribeOverlays(callback: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const onStorage = (e: StorageEvent) => {
    if (e.key === STORAGE_KEY) callback();
  };
  const onLocal = () => callback();
  window.addEventListener("storage", onStorage);
  window.addEventListener("who-portal-overlays", onLocal);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener("who-portal-overlays", onLocal);
  };
}

/** Map triage urgency to clinical display when doctor has not set one */
export function defaultClinicalUrgency(c: Case): ClinicalUrgency {
  if (c.urgency === "High") return "High";
  if (c.urgency === "Medium") return "Medium";
  return "Low";
}

export function displayUrgency(c: Case, overlay: CaseOverlay): ClinicalUrgency {
  return overlay.clinicalUrgency ?? defaultClinicalUrgency(c);
}

export type CaseWithOverlay = Case & {
  displayUrgency: ClinicalUrgency;
  reportStatus: ReportStatus;
};

export function mergeCaseWithOverlay(c: Case): CaseWithOverlay {
  const o = getCaseOverlay(c.caseId);
  return {
    ...c,
    displayUrgency: displayUrgency(c, o),
    reportStatus: o.reportStatus,
  };
}

export function mergeCasesWithOverlays(cases: Case[]): CaseWithOverlay[] {
  return cases.map(mergeCaseWithOverlay);
}
