// src/pages/LoginPage.tsx
// ──────────────────────────────────────────────────────────────
// WHO License verification login form. White background design.
// On success → navigates to /dashboard.
// On failure → shows error message from AuthContext.
// ──────────────────────────────────────────────────────────────

import { useState, FormEvent } from "react";
import { useNavigate, Navigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

// Match backend seed_and_demo.py (requires API running + seeded DB)
const DEMO_LICENSES = [
  { label: "Dr. James Mwangi (KE)", value: "KMPDC-22222" },
  { label: "Dr. Priya Sharma (IN)", value: "MCI-67890" },
  { label: "Dr. Adebayo Okafor (NG)", value: "MDCN-12345" },
];

const WHO_BLUE = "#0077B6";
const WHO_BLUE_DARK = "#005F8A";

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
      {/* Back to landing */}
      <Link to="/" style={styles.backLink}>← Back to Home</Link>

      <div style={styles.card}>
        {/* Header */}
        <div style={styles.cardHeader}>
          <div style={styles.logoCircle}>
            <span style={styles.logoMark}>✚</span>
          </div>
          <h1 style={styles.title}>WHO Triage Portal</h1>
          <p style={styles.subtitle}>Sign in with your WHO License Number</p>
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
          <p style={styles.demoTitle}>DEMO ACCOUNTS</p>
          {DEMO_LICENSES.map((d) => (
            <button
              key={d.value}
              style={styles.demoChip}
              onClick={() => fillDemo(d.value)}
              type="button"
            >
              <span style={styles.demoChipName}>{d.label}</span>
              <span style={styles.demoChipCode}>{d.value}</span>
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

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100vh",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#f8fafc",
    padding: 20,
    fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif",
  },
  backLink: {
    position: "absolute" as const,
    top: 24,
    left: 32,
    color: "#64748b",
    fontSize: 13,
    textDecoration: "none",
    fontWeight: 500,
  },
  card: {
    backgroundColor: "#ffffff",
    borderRadius: 16,
    padding: "40px 36px",
    width: "100%",
    maxWidth: 420,
    boxShadow: "0 4px 24px rgba(0,0,0,0.08)",
    border: "1px solid #e2e8f0",
  },
  cardHeader: { textAlign: "center", marginBottom: 32 },
  logoCircle: {
    width: 56,
    height: 56,
    borderRadius: "50%",
    backgroundColor: "#E8F4FD",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    margin: "0 auto 14px",
  },
  logoMark: { fontSize: 26, color: WHO_BLUE },
  title: { color: "#0f172a", fontSize: 22, fontWeight: 700, margin: "0 0 4px" },
  subtitle: { color: "#64748b", fontSize: 13, margin: 0 },
  form: { display: "flex", flexDirection: "column", gap: 12 },
  label: { color: "#475569", fontSize: 12, fontWeight: 600, letterSpacing: "0.05em" },
  input: {
    backgroundColor: "#f8fafc",
    border: "1.5px solid #e2e8f0",
    borderRadius: 8,
    padding: "11px 14px",
    color: "#0f172a",
    fontSize: 14,
    fontFamily: "monospace",
    outline: "none",
  },
  errorMsg: {
    color: "#dc2626",
    fontSize: 12,
    backgroundColor: "#fef2f2",
    border: "1px solid #fecaca",
    borderRadius: 6,
    padding: "8px 12px",
    margin: 0,
  },
  submitBtn: {
    backgroundColor: WHO_BLUE,
    color: "#ffffff",
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
    backgroundColor: "#f8fafc",
    borderRadius: 10,
    border: "1px solid #e2e8f0",
  },
  demoTitle: {
    color: "#94a3b8",
    fontSize: 10,
    fontWeight: 700,
    margin: "0 0 10px",
    letterSpacing: "0.08em",
  },
  demoChip: {
    display: "flex",
    flexDirection: "column" as const,
    width: "100%",
    textAlign: "left" as const,
    background: "#ffffff",
    border: "1px solid #e2e8f0",
    borderRadius: 8,
    color: "#334155",
    padding: "9px 12px",
    fontSize: 12,
    cursor: "pointer",
    marginBottom: 8,
    gap: 2,
  },
  demoChipName: { fontWeight: 600, color: "#0f172a", fontSize: 12 },
  demoChipCode: { fontFamily: "monospace", color: WHO_BLUE, fontSize: 11 },
  disclaimer: {
    color: "#94a3b8",
    fontSize: 11,
    textAlign: "center",
    marginTop: 20,
    lineHeight: 1.5,
  },
};
