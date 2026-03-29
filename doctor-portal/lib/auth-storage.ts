/** Client-side session for license-based doctor auth (demo; replace with real auth in production). */

export type DoctorProfile = {
  fullName: string;
  specialty: string;
  licenseNumber: string;
  hospitalAffiliation: string;
  email: string;
};

/** Seeded demo account for immediate login (testing / demos). */
export const DEMO_DOCTOR_LICENSE = "MD-2024-00142";
export const DEMO_DOCTOR_EMAIL = "james.mitchell@ghmc.org";
export const DEMO_DOCTOR_PASSWORD = "Doctor@1234";

const ACCOUNTS_KEY = "whoPortalAccounts";
const SESSION_KEY = "whoPortalSession";
const LEGACY_DOCTOR_ID = "whoPortalDoctorId";

type StoredAccount = DoctorProfile & { password: string };

const DEMO_SEED_ACCOUNT: StoredAccount = {
  fullName: "Dr. James Mitchell",
  specialty: "Internal Medicine",
  licenseNumber: DEMO_DOCTOR_LICENSE,
  hospitalAffiliation: "Global Health Medical Center",
  email: DEMO_DOCTOR_EMAIL,
  password: DEMO_DOCTOR_PASSWORD,
};

function licenseMatch(a: StoredAccount | undefined, license: string): boolean {
  const n = a?.licenseNumber;
  return typeof n === "string" && n.trim().toLowerCase() === license.trim().toLowerCase();
}

function emailMatch(a: StoredAccount | undefined, email: string): boolean {
  const e = a?.email;
  return typeof e === "string" && e.trim().toLowerCase() === email.trim().toLowerCase();
}

function accountMatchesIdentifier(a: StoredAccount, identifier: string): boolean {
  const t = identifier.trim();
  return licenseMatch(a, t) || emailMatch(a, t);
}

/**
 * Ensures the sample doctor exists with the canonical password (upserts by license).
 * Fixes duplicates, wrong passwords, or corrupted entries for MD-2024-00142.
 */
export function ensureDemoDoctorSeeded(): void {
  if (typeof window === "undefined") return;
  let list: StoredAccount[] = [];
  try {
    const raw = localStorage.getItem(ACCOUNTS_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as StoredAccount[];
      if (Array.isArray(parsed)) list = parsed;
    }
  } catch {
    list = [];
  }
  const withoutDemo = list.filter((a) => !licenseMatch(a, DEMO_DOCTOR_LICENSE));
  const demoRows = list.filter((a) => licenseMatch(a, DEMO_DOCTOR_LICENSE));
  const demoEntry = demoRows[0];
  const demoOk =
    demoRows.length === 1 &&
    demoEntry &&
    String(demoEntry.password ?? "") === DEMO_DOCTOR_PASSWORD &&
    demoEntry.fullName === DEMO_SEED_ACCOUNT.fullName;
  if (demoOk) return;

  const next = [...withoutDemo, { ...DEMO_SEED_ACCOUNT }];
  try {
    localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(next));
  } catch {
    /* quota / private mode — demo login still works via login() fast path */
  }
}

function readAccounts(): StoredAccount[] {
  if (typeof window === "undefined") return [];
  ensureDemoDoctorSeeded();
  try {
    const raw = localStorage.getItem(ACCOUNTS_KEY);
    if (!raw) return [{ ...DEMO_SEED_ACCOUNT }];
    const parsed = JSON.parse(raw) as StoredAccount[];
    if (!Array.isArray(parsed)) return [{ ...DEMO_SEED_ACCOUNT }];
    return parsed;
  } catch {
    return [{ ...DEMO_SEED_ACCOUNT }];
  }
}

function writeAccounts(accounts: StoredAccount[]) {
  localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(accounts));
}

export function getSessionLicense(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const j = JSON.parse(raw) as { licenseNumber?: string };
    return j.licenseNumber?.trim() || null;
  } catch {
    return null;
  }
}

export function isLoggedIn(): boolean {
  return Boolean(getSessionLicense());
}

export function getCurrentProfile(): DoctorProfile | null {
  const license = getSessionLicense();
  if (!license) return null;
  const acc = readAccounts().find((a) => licenseMatch(a, license));
  if (!acc) return null;
  const { password: _, ...profile } = acc;
  return profile;
}

export function signUp(profile: DoctorProfile, password: string): { ok: true } | { ok: false; error: string } {
  const license = profile.licenseNumber.trim();
  if (!license || !password) return { ok: false, error: "License and password are required." };
  const accounts = readAccounts();
  const em = profile.email.trim();
  if (accounts.some((a) => licenseMatch(a, license) || emailMatch(a, em))) {
    return { ok: false, error: "An account with this license number or email already exists." };
  }
  accounts.push({ ...profile, licenseNumber: license, password });
  writeAccounts(accounts);
  localStorage.setItem(SESSION_KEY, JSON.stringify({ licenseNumber: license }));
  syncLegacyDoctorHeader(license);
  return { ok: true };
}

export function login(licenseOrEmail: string, password: string): { ok: true } | { ok: false; error: string } {
  if (typeof window === "undefined") {
    return { ok: false, error: "Invalid email, license number, or password." };
  }
  const id = licenseOrEmail.trim();
  const pwd = password.trim();

  /* Demo account: license or email + password vs constants (localStorage cannot block) */
  const isDemoId =
    id.toLowerCase() === DEMO_DOCTOR_LICENSE.toLowerCase() ||
    id.toLowerCase() === DEMO_DOCTOR_EMAIL.toLowerCase();
  if (isDemoId) {
    if (pwd !== DEMO_DOCTOR_PASSWORD) {
      return { ok: false, error: "Invalid email, license number, or password." };
    }
    ensureDemoDoctorSeeded();
    localStorage.setItem(SESSION_KEY, JSON.stringify({ licenseNumber: DEMO_DOCTOR_LICENSE }));
    syncLegacyDoctorHeader(DEMO_DOCTOR_LICENSE);
    return { ok: true };
  }

  ensureDemoDoctorSeeded();
  const acc = readAccounts().find((a) => accountMatchesIdentifier(a, id));
  if (!acc || String(acc.password ?? "").trim() !== pwd) {
    return { ok: false, error: "Invalid email, license number, or password." };
  }
  localStorage.setItem(SESSION_KEY, JSON.stringify({ licenseNumber: acc.licenseNumber.trim() }));
  syncLegacyDoctorHeader(acc.licenseNumber.trim());
  return { ok: true };
}

export function logout() {
  localStorage.removeItem(SESSION_KEY);
  localStorage.removeItem(LEGACY_DOCTOR_ID);
}

/** Backend may expect a UUID in X-Doctor-ID; use license string as opaque id for demo. */
function syncLegacyDoctorHeader(license: string) {
  localStorage.setItem(LEGACY_DOCTOR_ID, license);
}
