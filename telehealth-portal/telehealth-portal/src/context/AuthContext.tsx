// Sign-in via GET /doctors (license_number on list + email from detail).

import { createContext, useContext, useState, type ReactNode } from "react";
import type { Doctor } from "../types";
import { CountryTier } from "../types";
import { getDoctors, getDoctor } from "../lib/api";

interface AuthState {
  doctor: Doctor | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

interface AuthContextValue extends AuthState {
  login: (licenseNumber: string) => Promise<boolean>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function mapApiToDoctor(
  row: Awaited<ReturnType<typeof getDoctor>>,
  email: string
): Doctor {
  const verified =
    row.verified && row.license_verified ? ("VERIFIED" as const) : ("PENDING" as const);
  const tiers =
    verified === "VERIFIED"
      ? [CountryTier.TIER_1, CountryTier.TIER_2, CountryTier.TIER_3, CountryTier.TIER_4]
      : [CountryTier.TIER_3, CountryTier.TIER_4];

  return {
    doctorId: row.id,
    licenseNumber: row.license_number || "",
    fullName: row.full_name,
    specialty: row.specialization,
    country: row.country_code,
    countryCode: row.country_code,
    verificationStatus: verified,
    allowedTiers: tiers,
    email,
    lastLoginAt: new Date().toISOString(),
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    doctor: null,
    isAuthenticated: false,
    isLoading: false,
    error: null,
  });

  const login = async (licenseNumber: string): Promise<boolean> => {
    const trimmed = licenseNumber.trim();
    setState((s) => ({ ...s, isLoading: true, error: null }));

    try {
      const list = await getDoctors();
      const match = list.find(
        (d) =>
          d.license_number &&
          d.license_number.trim().toLowerCase() === trimmed.toLowerCase()
      );

      if (!match) {
        setState((s) => ({
          ...s,
          isLoading: false,
          error:
            "License not found. Use a license from the seeded API (e.g. KMPDC-22222) and set VITE_API_URL on Vercel.",
        }));
        return false;
      }

      const detail = await getDoctor(match.id);
      const doctor = mapApiToDoctor(detail, detail.email);

      setState({
        doctor,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
      return true;
    } catch (e) {
      setState((s) => ({
        ...s,
        isLoading: false,
        error:
          e instanceof Error
            ? e.message
            : "Could not reach the API. Set VITE_API_URL to your backend (HTTPS) and check CORS.",
      }));
      return false;
    }
  };

  const logout = () => {
    setState({ doctor: null, isAuthenticated: false, isLoading: false, error: null });
  };

  return (
    <AuthContext.Provider value={{ ...state, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
