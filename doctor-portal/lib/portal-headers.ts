/** Optional doctor identity for production auth (X-Doctor-ID). */
export function portalHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const id = localStorage.getItem("whoPortalDoctorId");
  return id ? { "X-Doctor-ID": id } : {};
}
