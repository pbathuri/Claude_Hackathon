// src/pages/LoginPage.tsx
// ──────────────────────────────────────────────────────────────
// WHO License verification login form.
// On success → navigates to /dashboard.
// On failure → shows error message from AuthContext.
// ──────────────────────────────────────────────────────────────

import { useState, type FormEvent, type CSSProperties } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

// Match backend seed_and_demo.py (API must be reachable via VITE_API_URL)
const DEMO_LICENSES = [
  { label: "Dr. James Mwangi (KE)", value: "KMPDC-22222" },
  { label: "Dr. Priya Sharma (IN)", value: "MCI-67890" },
  { label: "Dr. Adebayo Okafor (NG)", value: "MDCN-12345" },
];

export default function LoginPage() {
  const { login, isLoading, error, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [licenseInput, setLicenseInput] = useState("");

  // If already logged in, skip to dashboard
  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const success = await login(licenseInput.trim());
    if (success) navigate("/dashboard", { replace: true });
  };

  const fillDemo = (value: string) => setLicenseInput(value);

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        {/* Header */}
        <div style={styles.cardHeader}>
          <span style={styles.logoMark}>✚</span>
          <h1 style={styles.title}>TeleHealth Portal</h1>
          <p style={styles.subtitle}>WHO License Verification</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} style={styles.form}>
          <label style={styles.label} htmlFor="license">
            WHO License Number
          </label>
          <input
            id="license"
            type="text"
            placeholder="e.g. WHO-KE-2019-04821"
            value={licenseInput}
            onChange={(e) => setLicenseInput(e.target.value)}
            style={styles.input}
            required
            autoFocus
          />

          {error && <p style={styles.errorMsg}>{error}</p>}

          <button type="submit" style={styles.submitBtn} disabled={isLoading}>
            {isLoading ? "Verifying…" : "Verify & Sign In"}
          </button>
        </form>

        {/* Demo helpers */}
        <div style={styles.demoBox}>
          <p style={styles.demoTitle}>Demo Accounts</p>
          {DEMO_LICENSES.map((d) => (
            <button
              key={d.value}
              style={styles.demoChip}
              onClick={() => fillDemo(d.value)}
              type="button"
            >
              {d.label}
            </button>
          ))}
        </div>

        {/* Disclaimer */}
        <p style={styles.disclaimer}>
          This platform is for licensed medical professionals only.
          All patient data is anonymised for demo purposes.
        </p>
      </div>
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  page: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#0f172a",
    padding: 20,
  },
  card: {
    backgroundColor: "#1e293b",
    borderRadius: 16,
    padding: "40px 36px",
    width: "100%",
    maxWidth: 420,
    boxShadow: "0 24px 64px rgba(0,0,0,0.5)",
  },
  cardHeader: { textAlign: "center", marginBottom: 32 },
  logoMark: { fontSize: 36, display: "block", marginBottom: 8 },
  title: { color: "#f8fafc", fontSize: 22, fontWeight: 700, margin: "0 0 4px" },
  subtitle: { color: "#64748b", fontSize: 13, margin: 0 },
  form: { display: "flex", flexDirection: "column", gap: 12 },
  label: { color: "#94a3b8", fontSize: 12, fontWeight: 600, letterSpacing: "0.05em" },
  input: {
    backgroundColor: "#0f172a",
    border: "1px solid #334155",
    borderRadius: 8,
    padding: "11px 14px",
    color: "#f8fafc",
    fontSize: 14,
    fontFamily: "monospace",
    outline: "none",
  },
  errorMsg: {
    color: "#f87171",
    fontSize: 12,
    backgroundColor: "#450a0a",
    border: "1px solid #7f1d1d",
    borderRadius: 6,
    padding: "8px 12px",
    margin: 0,
  },
  submitBtn: {
    backgroundColor: "#38bdf8",
    color: "#0c1a2e",
    border: "none",
    borderRadius: 8,
    padding: "12px",
    fontWeight: 700,
    fontSize: 14,
    cursor: "pointer",
    marginTop: 4,
  },
  demoBox: {
    marginTop: 28,
    padding: "16px",
    backgroundColor: "#0f172a",
    borderRadius: 10,
    border: "1px solid #1e3a5f",
  },
  demoTitle: { color: "#475569", fontSize: 11, fontWeight: 600, margin: "0 0 10px", letterSpacing: "0.06em" },
  demoChip: {
    display: "block",
    width: "100%",
    textAlign: "left",
    background: "none",
    border: "1px solid #1e293b",
    borderRadius: 6,
    color: "#7dd3fc",
    padding: "7px 10px",
    fontSize: 12,
    cursor: "pointer",
    marginBottom: 6,
    fontFamily: "monospace",
  },
  disclaimer: { color: "#334155", fontSize: 11, textAlign: "center", marginTop: 20, lineHeight: 1.5 },
};
