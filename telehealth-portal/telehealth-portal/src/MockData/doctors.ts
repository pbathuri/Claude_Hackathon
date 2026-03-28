// ============================================================
// mockData/doctors.ts
// Mock WHO-verified Doctor Profiles
// ============================================================

import { type Doctor, CountryTier } from "../types";

export const MOCK_DOCTORS: Doctor[] = [
  {
    doctorId: "doc-001",
    licenseNumber: "WHO-KE-2019-04821",
    fullName: "Dr. Amara Osei",
    specialty: "General Practice",
    country: "Kenya",
    countryCode: "KE",
    verificationStatus: "VERIFIED",
    allowedTiers: [
      CountryTier.TIER_1,
      CountryTier.TIER_2,
      CountryTier.TIER_3,
      CountryTier.TIER_4,
    ],
    email: "a.osei@telehealth.mock",
    lastLoginAt: "2025-07-14T08:23:00Z",
  },
  {
    doctorId: "doc-002",
    licenseNumber: "WHO-BD-2021-11203",
    fullName: "Dr. Priya Chakraborty",
    specialty: "Internal Medicine",
    country: "Bangladesh",
    countryCode: "BD",
    verificationStatus: "VERIFIED",
    allowedTiers: [CountryTier.TIER_3, CountryTier.TIER_4],
    email: "p.chakraborty@telehealth.mock",
    lastLoginAt: "2025-07-13T14:55:00Z",
  },
];

/**
 * Mock WHO license verification.
 * In production this would hit a real WHO API endpoint.
 * Returns the matching doctor or null if not found.
 */
export function verifyLicense(licenseNumber: string): Doctor | null {
  return (
    MOCK_DOCTORS.find(
      (d) =>
        d.licenseNumber === licenseNumber &&
        d.verificationStatus === "VERIFIED"
    ) ?? null
  );
}
