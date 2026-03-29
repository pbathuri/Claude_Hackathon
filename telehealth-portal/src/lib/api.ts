/**
 * Backend API client — same FastAPI contract as doctor-portal (NEXT_PUBLIC_API_URL → Vite VITE_API_URL).
 */

const API_BASE =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL) ||
  "http://localhost:8000";

const TIMEOUT_MS = 15000;

export function getApiBase(): string {
  return API_BASE.replace(/\/$/, "");
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const res = await fetch(url, {
    ...options,
    signal: controller.signal,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  clearTimeout(timeout);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(body || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export type ApiDoctorListItem = {
  id: string;
  full_name: string;
  specialization: string;
  country_code: string;
  languages: string[];
  availability: string;
  verified: boolean;
  license_verified: boolean;
  license_number: string | null;
};

export type ApiDoctorDetail = ApiDoctorListItem & {
  email: string;
  license_number: string | null;
};

export async function getDoctors(): Promise<ApiDoctorListItem[]> {
  return fetchJson<ApiDoctorListItem[]>(`${getApiBase()}/doctors/`);
}

export async function getDoctor(id: string): Promise<ApiDoctorDetail> {
  return fetchJson<ApiDoctorDetail>(`${getApiBase()}/doctors/${encodeURIComponent(id)}`);
}

/** Raw case shape from GET /cases/patient-cases and GET /cases/patient-cases/:id */
export type ApiPatientCase = {
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
  submittedAt: string | null;
  aiStructuredNotes: string | unknown;
  redFlagIndicators: string[];
  priorityScore: number;
  status?: string;
  assignedDoctor?: string;
  detectedLanguage?: string;
  translationUsed?: boolean;
};

export async function getCases(): Promise<ApiPatientCase[]> {
  return fetchJson<ApiPatientCase[]>(`${getApiBase()}/cases/patient-cases`);
}

export async function getCase(id: string): Promise<ApiPatientCase | null> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const res = await fetch(
    `${getApiBase()}/cases/patient-cases/${encodeURIComponent(id)}`,
    {
      signal: controller.signal,
      headers: { "Content-Type": "application/json" },
    }
  );
  clearTimeout(timeout);
  if (res.status === 404) return null;
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(body || `HTTP ${res.status}`);
  }
  return res.json() as Promise<ApiPatientCase>;
}

export async function assignDoctor(
  caseId: string,
  doctorId: string
): Promise<{ success: boolean }> {
  await fetchJson(`${getApiBase()}/cases/${encodeURIComponent(caseId)}/assign`, {
    method: "POST",
    body: JSON.stringify({ doctor_id: doctorId }),
  });
  return { success: true };
}

export async function submitResponse(
  caseId: string,
  payload: {
    doctor_id: string;
    guidance_text: string;
    is_emergency_referral: boolean;
    compliance_acknowledged: boolean;
  }
): Promise<{ success: boolean }> {
  await fetchJson(`${getApiBase()}/cases/${encodeURIComponent(caseId)}/respond`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return { success: true };
}
