// src/context/AuthContext.tsx
// ──────────────────────────────────────────────────────────────
// Global authentication state via React Context.
// Wraps the entire app so any component can read/write the
// logged-in doctor without prop drilling.
// ──────────────────────────────────────────────────────────────

import { createContext, useContext, useState, ReactNode } from "react";
import { Doctor } from "../types";
import { verifyLicense } from "../MockData/doctors";

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

// ── Create context with a safe default ───────────────────────
const AuthContext = createContext<AuthContextValue | null>(null);

// ── Provider ─────────────────────────────────────────────────
export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    doctor: null,
    isAuthenticated: false,
    isLoading: false,
    error: null,
  });

  /**
   * Simulates a WHO license verification API call.
   * In production, replace verifyLicense() with a real fetch().
   * Returns true on success, false on failure.
   */
  const login = async (licenseNumber: string): Promise<boolean> => {
    setState((s) => ({ ...s, isLoading: true, error: null }));

    // Simulate network latency
    await new Promise((r) => setTimeout(r, 800));

    const doctor = verifyLicense(licenseNumber);

    if (doctor) {
      setState({ doctor, isAuthenticated: true, isLoading: false, error: null });
      return true;
    } else {
      setState((s) => ({
        ...s,
        isLoading: false,
        error: "License not found or not verified. Please check your WHO license number.",
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

// ── Hook ─────────────────────────────────────────────────────
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
