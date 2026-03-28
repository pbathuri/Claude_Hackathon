// src/components/layout/AppLayout.tsx
// ──────────────────────────────────────────────────────────────
// Shared shell for all authenticated pages.
// Structure:
//   ┌──────────┬────────────────────────┐
//   │          │  TopBar                │
//   │ Sidebar  ├────────────────────────┤
//   │          │  <Outlet /> (page)     │
//   └──────────┴────────────────────────┘
// ──────────────────────────────────────────────────────────────

import { type CSSProperties } from "react";
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useCases } from "../../context/CasesContext";
import { DoctorDecisionStatus } from "../../types";

export default function AppLayout() {
  const { doctor, logout } = useAuth();
  const { cases } = useCases();
  const navigate = useNavigate();

  // Badge count: pending cases only
  const pendingCount = cases.filter(
    (c) => c.doctorDecisionStatus === DoctorDecisionStatus.PENDING
  ).length;

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <div style={styles.shell}>
      {/* ── Sidebar ─────────────────────────────────────────── */}
      <aside style={styles.sidebar}>
        <div style={styles.sidebarLogo}>
          <span style={styles.logoMark}>✚</span>
          <span style={styles.logoText}>TeleHealth</span>
        </div>

        <nav style={styles.nav}>
          <NavLink
            to="/dashboard"
            style={({ isActive }) => ({
              ...styles.navLink,
              ...(isActive ? styles.navLinkActive : {}),
            })}
          >
            <span style={styles.navIcon}>⬡</span>
            Dashboard
            {pendingCount > 0 && (
              <span style={styles.badge}>{pendingCount}</span>
            )}
          </NavLink>
        </nav>

        {/* Doctor info at bottom of sidebar */}
        <div style={styles.sidebarFooter}>
          {doctor && (
            <>
              <div style={styles.doctorName}>{doctor.fullName}</div>
              <div style={styles.doctorSpecialty}>{doctor.specialty}</div>
              <div style={styles.doctorLicense}>{doctor.licenseNumber}</div>
            </>
          )}
          <button style={styles.logoutBtn} onClick={handleLogout}>
            Sign Out
          </button>
        </div>
      </aside>

      {/* ── Main content area ───────────────────────────────── */}
      <main style={styles.main}>
        {/* TopBar */}
        <header style={styles.topBar}>
          <span style={styles.topBarTitle}>Doctor Portal</span>
          <span style={styles.topBarSubtitle}>
            WHO-Verified Telehealth Platform
          </span>
        </header>

        {/* Page content rendered by React Router */}
        <div style={styles.pageContent}>
          <Outlet />
        </div>
      </main>
    </div>
  );
}

// ── Minimal inline styles (no CSS framework dependency) ───────
// Replace with Tailwind classes or CSS modules in Step 3+
const styles: Record<string, CSSProperties> = {
  shell: {
    display: "flex",
    height: "100vh",
    overflow: "hidden",
    fontFamily: "'Segoe UI', system-ui, sans-serif",
    backgroundColor: "#f4f6f9",
  },
  sidebar: {
    width: 220,
    minWidth: 220,
    backgroundColor: "#0f172a",
    color: "#e2e8f0",
    display: "flex",
    flexDirection: "column",
    padding: "0",
    boxShadow: "2px 0 8px rgba(0,0,0,0.2)",
  },
  sidebarLogo: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "24px 20px 20px",
    borderBottom: "1px solid #1e293b",
  },
  logoMark: { fontSize: 22, color: "#38bdf8" },
  logoText: { fontSize: 16, fontWeight: 700, color: "#f8fafc", letterSpacing: "0.03em" },
  nav: { flex: 1, padding: "16px 12px" },
  navLink: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "10px 12px",
    borderRadius: 8,
    color: "#94a3b8",
    textDecoration: "none",
    fontSize: 14,
    fontWeight: 500,
    transition: "background 0.15s, color 0.15s",
  },
  navLinkActive: {
    backgroundColor: "#1e293b",
    color: "#f8fafc",
  },
  navIcon: { fontSize: 16 },
  badge: {
    marginLeft: "auto",
    backgroundColor: "#ef4444",
    color: "#fff",
    borderRadius: 999,
    padding: "1px 7px",
    fontSize: 11,
    fontWeight: 700,
  },
  sidebarFooter: {
    padding: "16px 20px",
    borderTop: "1px solid #1e293b",
    fontSize: 12,
    color: "#64748b",
  },
  doctorName: { color: "#cbd5e1", fontWeight: 600, marginBottom: 2 },
  doctorSpecialty: { color: "#64748b", marginBottom: 2 },
  doctorLicense: { color: "#334155", fontFamily: "monospace", fontSize: 11, marginBottom: 12 },
  logoutBtn: {
    background: "none",
    border: "1px solid #334155",
    color: "#94a3b8",
    borderRadius: 6,
    padding: "6px 12px",
    cursor: "pointer",
    fontSize: 12,
    width: "100%",
  },
  main: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
  },
  topBar: {
    height: 56,
    backgroundColor: "#ffffff",
    borderBottom: "1px solid #e2e8f0",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 28px",
    flexShrink: 0,
  },
  topBarTitle: { fontSize: 15, fontWeight: 700, color: "#0f172a" },
  topBarSubtitle: { fontSize: 12, color: "#94a3b8" },
  pageContent: {
    flex: 1,
    overflow: "auto",
    padding: 28,
  },
};
