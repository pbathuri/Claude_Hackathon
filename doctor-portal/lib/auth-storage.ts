/** Client-side session for license-based doctor auth (demo; replace with real auth in production). */

export type DoctorProfile = {
  fullName: string;
  specialty: string;
  licenseNumber: string;
  hospitalAffiliation: string;
  email: string;
};

const ACCOUNTS_KEY = "whoPortalAccounts";
const SESSION_KEY = "whoPortalSession";
const LEGACY_DOCTOR_ID = "whoPortalDoctorId";

type StoredAccount = DoctorProfile & { password: string };

function readAccounts(): StoredAccount[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(ACCOUNTS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as StoredAccount[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
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
  const acc = readAccounts().find(
    (a) => a.licenseNumber.toLowerCase() === license.toLowerCase()
  );
  if (!acc) return null;
  const { password: _, ...profile } = acc;
  return profile;
}

export function signUp(profile: DoctorProfile, password: string): { ok: true } | { ok: false; error: string } {
  const license = profile.licenseNumber.trim();
  if (!license || !password) return { ok: false, error: "License and password are required." };
  const accounts = readAccounts();
  if (accounts.some((a) => a.licenseNumber.toLowerCase() === license.toLowerCase())) {
    return { ok: false, error: "An account with this license number already exists." };
  }
  accounts.push({ ...profile, licenseNumber: license, password });
  writeAccounts(accounts);
  localStorage.setItem(SESSION_KEY, JSON.stringify({ licenseNumber: license }));
  syncLegacyDoctorHeader(license);
  return { ok: true };
}

export function login(licenseNumber: string, password: string): { ok: true } | { ok: false; error: string } {
  const license = licenseNumber.trim();
  const acc = readAccounts().find(
    (a) => a.licenseNumber.toLowerCase() === license.toLowerCase()
  );
  if (!acc || acc.password !== password) {
    return { ok: false, error: "Invalid license number or password." };
  }
  localStorage.setItem(SESSION_KEY, JSON.stringify({ licenseNumber: acc.licenseNumber }));
  syncLegacyDoctorHeader(acc.licenseNumber);
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
