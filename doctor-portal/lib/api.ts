import { Case, Doctor, BackpropResult, KGNavigationResult, KGStats, HottestPath, ConditionResult } from "@/types";
import {
  mockKGNavigation,
  mockKGStats,
  mockHottestPaths,
  getMockConditions,
} from "./mock-data";
import { portalHeaders } from "./portal-headers";
import { mergeDoctorsForOnlinePanel } from "./doctors-online";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TIMEOUT_MS = 15000;
const isDev = process.env.NODE_ENV === "development";

let _isUsingMockData = false;
export function isUsingMockData(): boolean {
  return _isUsingMockData;
}

function mergeInit(options?: RequestInit): RequestInit {
  const extra = portalHeaders();
  return {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...extra,
      ...(options?.headers as Record<string, string>),
    },
  };
}

async function fetchWithFallback<T>(url: string, fallback: T, options?: RequestInit): Promise<T> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
    const res = await fetch(url, {
      ...mergeInit(options),
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    _isUsingMockData = false;
    return await res.json();
  } catch {
    _isUsingMockData = true;
    return fallback;
  }
}

async function fetchStrict<T>(url: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const res = await fetch(url, {
    ...mergeInit(options),
    signal: controller.signal,
  });
  clearTimeout(timeout);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(body || `HTTP ${res.status}`);
  }
  return await res.json();
}

// --- Cases (real data only) ---

/** Resolved API base (NEXT_PUBLIC_API_URL or localhost). */
export function getApiBase(): string {
  return API_BASE;
}

export type PatientCasesResult = { cases: Case[]; error: string | null };

/**
 * Load the doctor-portal case list from GET /cases/patient-cases.
 * Does not silently fall back to [] on failure — check `error` for CORS/network/auth issues.
 */
export async function loadPatientCases(): Promise<PatientCasesResult> {
  try {
    const data = await fetchStrict<Case[]>(`${API_BASE}/cases/patient-cases`);
    _isUsingMockData = false;
    const cases = Array.isArray(data) ? data : [];
    return { cases, error: null };
  } catch (e) {
    _isUsingMockData = true;
    const msg = e instanceof Error ? e.message : "Failed to load cases from the API.";
    return { cases: [], error: msg };
  }
}

/** Same data as loadPatientCases; returns [] on error (legacy callers). Prefer loadPatientCases for UI errors. */
export async function getCases(): Promise<Case[]> {
  const { cases } = await loadPatientCases();
  return cases;
}

export type PatientCaseResult = { case: Case | null; error: string | null };

export async function loadPatientCase(id: string): Promise<PatientCaseResult> {
  try {
    const data = await fetchStrict<Case>(`${API_BASE}/cases/patient-cases/${id}`);
    _isUsingMockData = false;
    return { case: data, error: null };
  } catch (e) {
    _isUsingMockData = true;
    const msg = e instanceof Error ? e.message : "Failed to load case.";
    return { case: null, error: msg };
  }
}

export async function getCase(id: string): Promise<Case | null> {
  const { case: c } = await loadPatientCase(id);
  return c;
}

/**
 * Internal queue snapshot (scores, not full portal Case rows). Use for diagnostics or future queue UI — not a drop-in for loadPatientCases.
 */
export async function getCaseQueue(): Promise<unknown[]> {
  return fetchWithFallback(`${API_BASE}/cases/queue`, []);
}

/**
 * SSE: backend emits counts every ~4s. Refetch lists when messages arrive or when the connection opens.
 * If the stream is blocked (CORS/proxy), onerror schedules an extra refetch — combine with polling in pages.
 */
export function subscribeCasesStream(onEvent: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  let debounce: ReturnType<typeof setTimeout> | null = null;
  const es = new EventSource(`${API_BASE}/cases/stream`);
  const nudge = () => {
    onEvent();
  };
  es.onopen = () => nudge();
  es.onmessage = () => nudge();
  es.onerror = () => {
    if (debounce) clearTimeout(debounce);
    debounce = setTimeout(() => nudge(), 1500);
  };
  return () => {
    if (debounce) clearTimeout(debounce);
    es.close();
  };
}

// --- Doctors ---

export async function getDoctors(): Promise<Doctor[]> {
  const list = await fetchWithFallback<Doctor[]>(`${API_BASE}/doctors/`, []);
  return mergeDoctorsForOnlinePanel(list);
}

// --- Mutations ---

export async function assignDoctor(caseId: string, doctorId: string = "portal-doctor"): Promise<{ success: boolean }> {
  try {
    const data = await fetchStrict<{
      success?: boolean;
      status?: string;
      case_id?: string;
      doctor_id?: string;
    }>(`${API_BASE}/cases/${caseId}/assign`, {
      method: "POST",
      body: JSON.stringify({ doctor_id: doctorId }),
    });
    const ok = data.success === true || data.status === "assigned";
    return { success: ok };
  } catch (err) {
    console.error("[assignDoctor] failed:", err);
    return { success: false };
  }
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
  return fetchStrict(`${API_BASE}/cases/${caseId}/respond`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function backpropagateCase(caseId: string, diagnosis: string, specialty: string): Promise<BackpropResult> {
  return fetchStrict(`${API_BASE}/kg/backpropagate`, {
    method: "POST",
    body: JSON.stringify({
      case_id: caseId,
      doctor_diagnosis: diagnosis,
      doctor_specialty: specialty,
      outcome: "resolved",
    }),
  });
}

// --- KG: normalize snake_case API → portal types ---

export function normalizeKgStats(raw: Record<string, unknown> | null | undefined): KGStats {
  if (!raw || typeof raw !== "object") {
    return {
      totalNodes: 0,
      totalEdges: 0,
      learnedEdges: 0,
      specialties: [],
      lastUpdated: new Date().toISOString(),
    };
  }
  return {
    totalNodes: Number(raw.totalNodes ?? raw.total_nodes ?? 0),
    totalEdges: Number(raw.totalEdges ?? raw.total_edges ?? 0),
    learnedEdges: Number(raw.learnedEdges ?? raw.learned_edges ?? 0),
    specialties: Array.isArray(raw.specialties) ? (raw.specialties as string[]) : [],
    lastUpdated: String(raw.lastUpdated ?? raw.last_updated ?? new Date().toISOString()),
  };
}

export function normalizeHottestPaths(raw: unknown): HottestPath[] {
  const arr = Array.isArray(raw) ? raw : [];
  return arr.map((p: Record<string, unknown>) => ({
    source: String(p.source ?? ""),
    target: String(p.target ?? ""),
    conductivity: Number(p.conductivity ?? 0),
    pathType: String(p.pathType ?? p.edge_type ?? "edge"),
  }));
}

const emptyKgStats = normalizeKgStats({});
const emptyHottest: HottestPath[] = [];

const emptyNavigation: KGNavigationResult = {
  conditions: [],
  recommendedSpecialty: "General Medicine",
  followUpQuestions: [],
  bodySystemMapping: {},
  graphPaths: [],
};

export async function navigateKG(symptoms: string[]): Promise<KGNavigationResult> {
  return fetchWithFallback(
    `${API_BASE}/kg/navigate`,
    isDev ? mockKGNavigation : emptyNavigation,
    { method: "POST", body: JSON.stringify({ case_id: "portal-query", symptoms }) }
  );
}

export async function getKGStats(): Promise<KGStats> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
    const res = await fetch(`${API_BASE}/kg/stats`, {
      ...mergeInit(),
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!res.ok) throw new Error(String(res.status));
    _isUsingMockData = false;
    const j = await res.json();
    return normalizeKgStats(j);
  } catch {
    _isUsingMockData = true;
    return isDev ? mockKGStats : emptyKgStats;
  }
}

export async function getHottestPaths(): Promise<HottestPath[]> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
    const res = await fetch(`${API_BASE}/kg/hottest-paths`, {
      ...mergeInit(),
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!res.ok) throw new Error(String(res.status));
    _isUsingMockData = false;
    const j = await res.json();
    const paths = Array.isArray(j) ? j : j.paths || [];
    return normalizeHottestPaths(paths);
  } catch {
    _isUsingMockData = true;
    return isDev ? mockHottestPaths : emptyHottest;
  }
}

export async function getConditions(symptomName: string): Promise<ConditionResult> {
  const fallback = isDev ? getMockConditions(symptomName) : ({ symptom: symptomName, conditions: [] } as ConditionResult);
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
