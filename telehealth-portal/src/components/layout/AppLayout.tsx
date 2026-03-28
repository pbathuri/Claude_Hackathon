// src/components/layout/AppLayout.tsx
// ──────────────────────────────────────────────────────────────
// Shared shell for all authenticated pages.
// Updated with WHO Triage Intelligence branding and nav links.
// Structure:
//   ┌──────────┬────────────────────────┐
//   │          │  TopBar                │
//   │ Sidebar  ├────────────────────────┤
//   │          │  <Outlet /> (page)     │
//   └──────────┴────────────────────────┘
// ──────────────────────────────────────────────────────────────

import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useCases } from "../../context/CasesContext";
import { DoctorDecisionStatus } from "../../types";

const WHO_BLUE = "#0077B6";

const NAV_ITEMS = [
  { to: "/dashboard", icon: "⬡", label: "Dashboard" },
  { to: "/dashboard?tab=cases", icon: "📋", label: "Case Queue", isCaseQueue: true },
  { to: "/dashboard?tab=knowledge", icon: "🔬", label: "ICD-11 Knowledge", isKnowledge: true },
];

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
          <div style={styles.logoIconWrapper}>
            <span style={styles.logoMark}>✚</span>
          </div>
          <div>
            <div style={styles.logoText}>WHO Triage</div>
            <div style={styles.logoSub}>Intelligence Platform</div>
          </div>
        </div>

        <nav style={styles.nav}>
          <NavLink
            to="/dashboard"
            end
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

          <div style={styles.navSectionLabel}>CASE MANAGEMENT</div>

          <NavLink
            to="/dashboard"
            style={({ isActive }) => ({
              ...styles.navLink,
              ...(isActive ? styles.navLinkActive : {}),
            })}
          >
            <span style={styles.navIcon}>📋</span>
            Case Queue
            {pendingCount > 0 && (
              <span style={styles.badge}>{pendingCount}</span>
            )}
          </NavLink>

          <div style={styles.navSectionLabel}>TOOLS</div>

          <button
            style={styles.navLinkBtn}
            title="ICD-11 Knowledge Graph (coming soon)"
          >
            <span style={styles.navIcon}>🔬</span>
            ICD-11 Knowledge
            <span style={styles.comingSoonChip}>soon</span>
          </button>
        </nav>

        {/* Doctor info at bottom of sidebar */}
        <div style={styles.sidebarFooter}>
          {doctor && (
            <>
              <div style={styles.doctorAvatar}>
                {doctor.fullName.split(" ").map(w => w[0]).join("").slice(0, 2)}
              </div>
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
          <div style={styles.topBarLeft}>
            <span style={styles.topBarTitle}>WHO Triage Intelligence Platform</span>
            <span style={styles.topBarDivider}>·</span>
            <span style={styles.topBarSubtitle}>
              Doctor Portal
            </span>
          </div>
          <div style={styles.topBarRight}>
            <span style={styles.topBarVerified}>
              <span style={styles.verifiedDot} />
              WHO-Verified
            </span>
          </div>
        </header>

        {/* Page content rendered by React Router */}
        <div style={styles.pageContent}>
          <Outlet />
        </div>
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  shell: {
    display: "flex",
    height: "100vh",
    overflow: "hidden",
    fontFamily: "'Segoe UI', system-ui, sans-serif",
    backgroundColor: "#f4f6f9",
  },
  sidebar: {
    width: 232,
    minWidth: 232,
    backgroundColor: "#0f172a",
    color: "#e2e8f0",
    display: "flex",
    flexDirection: "column",
    boxShadow: "2px 0 8px rgba(0,0,0,0.2)",
  },
  sidebarLogo: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "20px 18px 16px",
    borderBottom: "1px solid #1e293b",
  },
  logoIconWrapper: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: WHO_BLUE,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  logoMark: { fontSize: 20, color: "#ffffff" },
  logoText: { fontSize: 14, fontWeight: 700, color: "#f8fafc", letterSpacing: "0.02em" },
  logoSub: { fontSize: 10, color: "#475569", letterSpacing: "0.04em", marginTop: 1 },
  nav: { flex: 1, padding: "12px 10px" },
  navSectionLabel: {
    fontSize: 9,
    fontWeight: 700,
    color: "#334155",
    letterSpacing: "0.1em",
    padding: "14px 12px 6px",
  },
  navLink: {
    display: "flex",
    alignItems: "center",
    gap: 9,
    padding: "9px 12px",
    borderRadius: 8,
    color: "#64748b",
    textDecoration: "none",
    fontSize: 13,
    fontWeight: 500,
    transition: "background 0.15s, color 0.15s",
  },
  navLinkActive: {
    backgroundColor: "#1e293b",
    color: "#f8fafc",
  },
  navLinkBtn: {
    display: "flex",
    alignItems: "center",
    gap: 9,
    padding: "9px 12px",
    borderRadius: 8,
    color: "#334155",
    fontSize: 13,
    fontWeight: 500,
    background: "none",
    border: "none",
    cursor: "default",
    width: "100%",
    textAlign: "left",
  },
  navIcon: { fontSize: 14, width: 18, textAlign: "center" as const },
  badge: {
    marginLeft: "auto",
    backgroundColor: "#ef4444",
    color: "#fff",
    borderRadius: 999,
    padding: "1px 7px",
    fontSize: 10,
    fontWeight: 700,
  },
  comingSoonChip: {
    marginLeft: "auto",
    backgroundColor: "#1e293b",
    color: "#475569",
    borderRadius: 999,
    padding: "1px 7px",
    fontSize: 9,
    fontWeight: 600,
    letterSpacing: "0.04em",
  },
  sidebarFooter: {
    padding: "14px 16px",
    borderTop: "1px solid #1e293b",
    fontSize: 12,
    color: "#64748b",
  },
  doctorAvatar: {
    width: 32,
    height: 32,
    borderRadius: "50%",
    backgroundColor: WHO_BLUE,
    color: "#ffffff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 12,
    fontWeight: 700,
    marginBottom: 8,
  },
  doctorName: { color: "#cbd5e1", fontWeight: 600, marginBottom: 2, fontSize: 13 },
  doctorSpecialty: { color: "#64748b", marginBottom: 2, fontSize: 11 },
  doctorLicense: { color: "#334155", fontFamily: "monospace", fontSize: 10, marginBottom: 12 },
  logoutBtn: {
    background: "none",
    border: "1px solid #1e293b",
    color: "#64748b",
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
    height: 52,
    backgroundColor: "#ffffff",
    borderBottom: "1px solid #e2e8f0",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 28px",
    flexShrink: 0,
  },
  topBarLeft: { display: "flex", alignItems: "center", gap: 8 },
  topBarTitle: { fontSize: 14, fontWeight: 700, color: "#0f172a" },
  topBarDivider: { color: "#cbd5e1" },
  topBarSubtitle: { fontSize: 13, color: "#94a3b8" },
  topBarRight: {},
  topBarVerified: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    fontSize: 12,
    color: "#16a34a",
    fontWeight: 600,
  },
  verifiedDot: {
    width: 7,
    height: 7,
    borderRadius: "50%",
    backgroundColor: "#16a34a",
    display: "inline-block",
  },
  pageContent: {
    flex: 1,
    overflow: "auto",
    padding: 28,
  },
};
