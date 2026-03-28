import { Case, Doctor, BackpropResult, KGNavigationResult, KGStats, HottestPath, ConditionResult } from "@/types";
import {
  mockCases,
  mockKGNavigation,
  mockKGStats,
  mockHottestPaths,
  getMockConditions,
} from "./mock-data";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TIMEOUT_MS = 5000;

let _isUsingMockData = false;
export function isUsingMockData(): boolean { return _isUsingMockData; }

async function fetchWithFallback<T>(
  url: string,
  fallback: T,
  options?: RequestInit
): Promise<T> {
  try {
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
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    _isUsingMockData = true;
    return fallback;
  }
}

async function fetchStrict<T>(
  url: string,
  options?: RequestInit
): Promise<T> {
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
  return await res.json();
}

// --- Cases (graceful fallback to mock when backend is down) ---

export async function getCases(): Promise<Case[]> {
  return fetchWithFallback(`${API_BASE}/cases/patient-cases`, mockCases);
}

export async function getCase(id: string): Promise<Case | null> {
  const fallback = mockCases.find((c) => c.caseId === id) || null;
  return fetchWithFallback(`${API_BASE}/cases/patient-cases/${id}`, fallback);
}

export async function getCaseQueue(): Promise<Case[]> {
  return fetchWithFallback(`${API_BASE}/cases/queue`, mockCases.filter((c) => c.status === "pending_review"));
}

// --- Doctors (live, no mock fallback) ---

export async function getDoctors(): Promise<Doctor[]> {
  return fetchWithFallback<Doctor[]>(`${API_BASE}/doctors/`, []);
}

// --- Mutations (strict — throw on failure so UI can display errors) ---

export async function assignDoctor(caseId: string, doctorId: string = "portal-doctor"): Promise<{ success: boolean }> {
  return fetchStrict(`${API_BASE}/cases/${caseId}/assign`, {
    method: "POST",
    body: JSON.stringify({ doctor_id: doctorId }),
  });
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
  return fetchStrict(
    `${API_BASE}/cases/${caseId}/respond`,
    { method: "POST", body: JSON.stringify(payload) }
  );
}

export async function backpropagateCase(
  caseId: string,
  diagnosis: string,
  specialty: string
): Promise<BackpropResult> {
  return fetchStrict(
    `${API_BASE}/kg/backpropagate`,
    {
      method: "POST",
      body: JSON.stringify({
        case_id: caseId,
        doctor_diagnosis: diagnosis,
        doctor_specialty: specialty,
        outcome: "resolved",
      }),
    }
  );
}

// --- KG endpoints (graceful fallback to mock) ---

export async function navigateKG(symptoms: string[]): Promise<KGNavigationResult> {
  return fetchWithFallback(
    `${API_BASE}/kg/navigate`,
    mockKGNavigation,
    { method: "POST", body: JSON.stringify({ case_id: "portal-query", symptoms }) }
  );
}

export async function getKGStats(): Promise<KGStats> {
  return fetchWithFallback(`${API_BASE}/kg/stats`, mockKGStats);
}

export async function getHottestPaths(): Promise<HottestPath[]> {
  const result = await fetchWithFallback<{ paths: HottestPath[] } | HottestPath[]>(
    `${API_BASE}/kg/hottest-paths`,
    mockHottestPaths
  );
  return Array.isArray(result) ? result : result.paths || [];
}

export async function getConditions(symptomName: string): Promise<ConditionResult> {
  const fallback = getMockConditions(symptomName);
  return fetchWithFallback(`${API_BASE}/kg/conditions/${encodeURIComponent(symptomName)}`, fallback);
}

// --- Utilities ---

export function timeAgo(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
