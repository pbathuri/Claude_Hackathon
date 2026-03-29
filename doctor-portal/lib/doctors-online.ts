import type { Doctor } from "@/types";

/** Mock colleagues when the API returns no doctors (demo / offline). */
export const MOCK_DOCTORS_ONLINE: Doctor[] = [
  {
    id: "mock-colleague-1",
    full_name: "Dr. Sarah Okonkwo",
    specialization: "Pediatrics",
    country_code: "NG",
    languages: ["en"],
    availability: "online",
    verified: true,
  },
  {
    id: "mock-colleague-2",
    full_name: "Dr. Chen Wei",
    specialization: "Cardiology",
    country_code: "PH",
    languages: ["en", "zh"],
    availability: "busy",
    verified: true,
  },
  {
    id: "mock-colleague-3",
    full_name: "Dr. Amara Okafor",
    specialization: "Emergency Medicine",
    country_code: "NG",
    languages: ["en"],
    availability: "offline",
    verified: true,
  },
  {
    id: "mock-colleague-4",
    full_name: "Dr. Elena Vasquez",
    specialization: "Dermatology",
    country_code: "KE",
    languages: ["en", "es"],
    availability: "online",
    verified: false,
  },
];

export type PresenceKind = "online" | "offline" | "away";

export function doctorPresence(availability: string): PresenceKind {
  const a = (availability || "").toLowerCase();
  if (a === "online") return "online";
  if (a === "busy" || a === "away") return "away";
  return "offline";
}

export function mergeDoctorsForOnlinePanel(apiDoctors: Doctor[]): Doctor[] {
  if (apiDoctors.length > 0) return apiDoctors;
  return MOCK_DOCTORS_ONLINE;
}
