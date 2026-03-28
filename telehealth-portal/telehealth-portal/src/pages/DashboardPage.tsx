// src/pages/DashboardPage.tsx
// ──────────────────────────────────────────────────────────────
// Case inbox with priority-sorted table.
// Filters: All / Pending / In Review / Completed
// Each row is clickable → navigates to /cases/:caseId
// ──────────────────────────────────────────────────────────────

import { useState, type CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import { useCases } from "../context/CasesContext";
import { useAuth } from "../context/AuthContext";
import { DoctorDecisionStatus, UrgencyLevel, CountryTier, type PatientCase } from "../types";

// ── Filter tabs ───────────────────────────────────────────────
type FilterTab = "ALL" | DoctorDecisionStatus;
const TABS: { label: string; value: FilterTab }[] = [
  { label: "All Cases", value: "ALL" },
  { label: "Pending", value: DoctorDecisionStatus.PENDING },
  { label: "In Review", value: DoctorDecisionStatus.IN_REVIEW },
  { label: "Completed", value: DoctorDecisionStatus.COMPLETED },
  { label: "Escalated", value: DoctorDecisionStatus.ESCALATED },
];

// ── Urgency badge colours ─────────────────────────────────────
const URGENCY_COLOR: Record<UrgencyLevel, string> = {
  [UrgencyLevel.EMERGENCY]: "#ef4444",
  [UrgencyLevel.HIGH]: "#f97316",
  [UrgencyLevel.MEDIUM]: "#eab308",
  [UrgencyLevel.LOW]: "#22c55e",
};

const TIER_COLOR: Record<CountryTier, string> = {
  [CountryTier.TIER_1]: "#16a34a",
  [CountryTier.TIER_2]: "#2563eb",
  [CountryTier.TIER_3]: "#d97706",
  [CountryTier.TIER_4]: "#dc2626",
};

const STATUS_COLOR: Record<DoctorDecisionStatus, string> = {
  [DoctorDecisionStatus.PENDING]: "#64748b",
  [DoctorDecisionStatus.IN_REVIEW]: "#2563eb",
  [DoctorDecisionStatus.COMPLETED]: "#16a34a",
  [DoctorDecisionStatus.ESCALATED]: "#f97316",
  [DoctorDecisionStatus.CLOSED]: "#334155",
};

export default function DashboardPage() {
  const { cases } = useCases();
  const { doctor } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<FilterTab>("ALL");

  const filtered = activeTab === "ALL"
    ? cases
    : cases.filter((c) => c.doctorDecisionStatus === activeTab);

  const tabCount = (tab: FilterTab) =>
    tab === "ALL" ? cases.length : cases.filter((c) => c.doctorDecisionStatus === tab).length;

  return (
    <div>
      {/* ── Page header ──────────────────────────────────────── */}
      <div style={styles.pageHeader}>
        <div>
          <h2 style={styles.pageTitle}>Case Inbox</h2>
          <p style={styles.pageSubtitle}>
            Welcome back, {doctor?.fullName}. Cases sorted by urgency × jurisdiction tier.
          </p>
        </div>
        <div style={styles.statsRow}>
          <Stat label="Total" value={cases.length} />
          <Stat label="Pending" value={tabCount(DoctorDecisionStatus.PENDING)} highlight />
        </div>
      </div>

      {/* ── Filter tabs ──────────────────────────────────────── */}
      <div style={styles.tabRow}>
        {TABS.map((t) => (
          <button
            key={t.value}
            style={{
              ...styles.tab,
              ...(activeTab === t.value ? styles.tabActive : {}),
            }}
            onClick={() => setActiveTab(t.value)}
          >
            {t.label}
            <span style={styles.tabCount}>{tabCount(t.value)}</span>
          </button>
        ))}
      </div>

      {/* ── Case table ───────────────────────────────────────── */}
      <div style={styles.tableWrapper}>
        <table style={styles.table}>
          <thead>
            <tr>
              {["#", "Case ID", "Country", "Tier", "Urgency", "Pain", "Duration", "Status", "Created"].map((h) => (
                <th key={h} style={styles.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((c, idx) => (
              <CaseRow
                key={c.caseId}
                idx={idx + 1}
                c={c}
                onClick={() => navigate(`/cases/${c.caseId}`)}
              />
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={9} style={styles.emptyCell}>
                  No cases match this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────

function CaseRow({ idx, c, onClick }: { idx: number; c: PatientCase; onClick: () => void }) {
  return (
    <tr style={styles.tr} onClick={onClick}>
      <td style={{ ...styles.td, color: "#64748b", width: 36 }}>{idx}</td>
      <td style={{ ...styles.td, fontFamily: "monospace", fontWeight: 600, color: "#38bdf8" }}>
        {c.caseId}
      </td>
      <td style={styles.td}>
        <span style={styles.flag}>{c.countryCode}</span> {c.country}
      </td>
      <td style={styles.td}>
        <Badge color={TIER_COLOR[c.countryTier]} text={`Tier ${c.countryTier}`} />
      </td>
      <td style={styles.td}>
        <Badge color={URGENCY_COLOR[c.urgencyLevel]} text={c.urgencyLevel} />
      </td>
      <td style={{ ...styles.td, textAlign: "center" }}>
        <PainDot score={c.painScore} />
      </td>
      <td style={{ ...styles.td, color: "#94a3b8" }}>{c.symptomDurationDays}d</td>
      <td style={styles.td}>
        <Badge color={STATUS_COLOR[c.doctorDecisionStatus]} text={c.doctorDecisionStatus.replace("_", " ")} />
      </td>
      <td style={{ ...styles.td, color: "#64748b", fontSize: 11 }}>
        {new Date(c.createdAt).toLocaleString("en-GB", { dateStyle: "short", timeStyle: "short" })}
      </td>
    </tr>
  );
}

function Badge({ color, text }: { color: string; text: string }) {
  return (
    <span style={{
      backgroundColor: color + "22",
      color,
      border: `1px solid ${color}55`,
      borderRadius: 999,
      padding: "2px 8px",
      fontSize: 11,
      fontWeight: 600,
      whiteSpace: "nowrap",
    }}>
      {text}
    </span>
  );
}

function PainDot({ score }: { score: number }) {
  const color = score >= 8 ? "#ef4444" : score >= 5 ? "#f97316" : "#22c55e";
  return (
    <span style={{ color, fontWeight: 700, fontSize: 13 }}>{score}/10</span>
  );
}

function Stat({ label, value, highlight }: { label: string; value: number; highlight?: boolean }) {
  return (
    <div style={styles.stat}>
      <span style={{ ...styles.statValue, color: highlight ? "#ef4444" : "#f8fafc" }}>{value}</span>
      <span style={styles.statLabel}>{label}</span>
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────
const styles: Record<string, CSSProperties> = {
  pageHeader: {
    display: "flex", justifyContent: "space-between", alignItems: "flex-start",
    marginBottom: 24,
  },
  pageTitle: { fontSize: 22, fontWeight: 700, color: "#0f172a", margin: "0 0 4px" },
  pageSubtitle: { fontSize: 13, color: "#64748b", margin: 0 },
  statsRow: { display: "flex", gap: 16 },
  stat: {
    backgroundColor: "#fff", border: "1px solid #e2e8f0", borderRadius: 10,
    padding: "10px 18px", textAlign: "center", minWidth: 72,
  },
  statValue: { display: "block", fontSize: 22, fontWeight: 700 },
  statLabel: { fontSize: 11, color: "#94a3b8", letterSpacing: "0.05em" },
  tabRow: { display: "flex", gap: 8, marginBottom: 16 },
  tab: {
    backgroundColor: "#fff", border: "1px solid #e2e8f0", borderRadius: 8,
    padding: "7px 14px", fontSize: 13, color: "#64748b", cursor: "pointer",
    display: "flex", alignItems: "center", gap: 6,
  },
  tabActive: { backgroundColor: "#0f172a", color: "#f8fafc", borderColor: "#0f172a" },
  tabCount: {
    backgroundColor: "#e2e8f0", borderRadius: 999, padding: "1px 7px",
    fontSize: 11, fontWeight: 700,
  },
  tableWrapper: {
    backgroundColor: "#fff", borderRadius: 12, border: "1px solid #e2e8f0",
    overflow: "hidden",
  },
  table: { width: "100%", borderCollapse: "collapse" },
  th: {
    textAlign: "left", padding: "10px 14px", fontSize: 11, fontWeight: 700,
    color: "#94a3b8", letterSpacing: "0.07em", borderBottom: "1px solid #e2e8f0",
    backgroundColor: "#f8fafc",
  },
  tr: {
    cursor: "pointer",
    transition: "background 0.1s",
  },
  td: { padding: "12px 14px", fontSize: 13, color: "#334155", borderBottom: "1px solid #f1f5f9" },
  emptyCell: { padding: "32px", textAlign: "center", color: "#94a3b8", fontSize: 14 },
  flag: {
    backgroundColor: "#f1f5f9", borderRadius: 4, padding: "1px 5px",
    fontSize: 10, fontWeight: 700, fontFamily: "monospace", color: "#475569",
  },
};
