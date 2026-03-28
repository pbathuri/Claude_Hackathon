// src/pages/DashboardPage.tsx
// ──────────────────────────────────────────────────────────────
// WHO Triage Dashboard — stats cards + filterable case queue.
// Combines Claude_Hackathon content with telehealth-portal UI.
// ──────────────────────────────────────────────────────────────

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCases } from "../context/CasesContext";
import { useAuth } from "../context/AuthContext";
import { DoctorDecisionStatus, UrgencyLevel, CountryTier, PatientCase } from "../types";

// ── Filter tabs ───────────────────────────────────────────────
type FilterTab = "ALL" | DoctorDecisionStatus;
const TABS: { label: string; value: FilterTab }[] = [
  { label: "All Cases", value: "ALL" },
  { label: "Pending", value: DoctorDecisionStatus.PENDING },
  { label: "In Review", value: DoctorDecisionStatus.IN_REVIEW },
  { label: "Completed", value: DoctorDecisionStatus.COMPLETED },
  { label: "Escalated", value: DoctorDecisionStatus.ESCALATED },
];

// ── Colour maps ───────────────────────────────────────────────
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

const WHO_BLUE = "#0077B6";

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

  // ── Derived stats ──────────────────────────────────────────
  const criticalCount = cases.filter(
    (c) => c.urgencyLevel === UrgencyLevel.EMERGENCY || c.urgencyLevel === UrgencyLevel.HIGH
  ).length;

  const pendingCount = cases.filter(
    (c) => c.doctorDecisionStatus === DoctorDecisionStatus.PENDING
  ).length;

  const withImagesCount = cases.filter((c) => c.uploadedImageUrls.length > 0).length;

  const today = new Date().toDateString();
  const todayCount = cases.filter(
    (c) => new Date(c.createdAt).toDateString() === today
  ).length;

  // ── Country distribution ───────────────────────────────────
  const countryCounts: Record<string, number> = {};
  cases.forEach((c) => {
    countryCounts[c.country] = (countryCounts[c.country] ?? 0) + 1;
  });
  const topCountries = Object.entries(countryCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4);

  return (
    <div>
      {/* ── Page header ──────────────────────────────────────── */}
      <div style={styles.pageHeader}>
        <div>
          <h2 style={styles.pageTitle}>Triage Dashboard</h2>
          <p style={styles.pageSubtitle}>
            Welcome, {doctor?.fullName}. Cases sorted by urgency × jurisdiction tier.
          </p>
        </div>
        <div style={styles.headerBadge}>
          <span style={styles.headerBadgeIcon}>✚</span>
          WHO Triage Intelligence
        </div>
      </div>

      {/* ── Stats cards row ───────────────────────────────────── */}
      <div style={styles.statsRow}>
        <StatCard
          icon="📂"
          value={cases.length}
          label="Total Cases"
          color={WHO_BLUE}
        />
        <StatCard
          icon="🔴"
          value={criticalCount}
          label="Critical / High"
          color="#ef4444"
          highlight
        />
        <StatCard
          icon="⏳"
          value={pendingCount}
          label="Awaiting Review"
          color="#f97316"
        />
        <StatCard
          icon="📷"
          value={withImagesCount}
          label="Cases with Images"
          color="#8b5cf6"
        />
      </div>

      {/* ── Case distribution + country panel ────────────────── */}
      <div style={styles.insightsRow}>
        {/* Urgency breakdown — donut chart */}
        <div style={styles.insightCard}>
          <h4 style={styles.insightTitle}>Urgency Distribution</h4>
          <UrgencyDonutChart cases={cases} />
        </div>

        {/* Top countries */}
        <div style={styles.insightCard}>
          <h4 style={styles.insightTitle}>Cases by Country</h4>
          {topCountries.map(([country, count]) => {
            const pct = cases.length ? Math.round((count / cases.length) * 100) : 0;
            const code = cases.find((c) => c.country === country)?.countryCode ?? "";
            return (
              <div key={country} style={styles.barRow}>
                <span style={styles.countryLabel}>
                  <span style={styles.flagChip}>{code}</span>
                  {country}
                </span>
                <div style={styles.barTrack}>
                  <div style={{ ...styles.barFill, width: `${pct}%`, backgroundColor: WHO_BLUE }} />
                </div>
                <span style={styles.barCount}>{count}</span>
              </div>
            );
          })}
        </div>

        {/* Doctor status */}
        <div style={styles.insightCard}>
          <h4 style={styles.insightTitle}>Doctor Status</h4>
          {doctor && (
            <div style={styles.doctorStatusCard}>
              <div style={styles.doctorStatusAvatar}>
                {doctor.fullName.split(" ").map(w => w[0]).join("").slice(0, 2)}
              </div>
              <div>
                <div style={styles.doctorStatusName}>{doctor.fullName}</div>
                <div style={styles.doctorStatusSpec}>{doctor.specialty}</div>
                <div style={styles.doctorStatusOnline}>
                  <span style={styles.onlineDot} /> Online
                </div>
              </div>
            </div>
          )}
          <div style={styles.tierList}>
            <div style={styles.tierListLabel}>Authorized Tiers</div>
            <div style={styles.tierChips}>
              {doctor?.allowedTiers.map((t) => (
                <span key={t} style={{ ...styles.tierChip, color: TIER_COLOR[t], backgroundColor: TIER_COLOR[t] + "18", borderColor: TIER_COLOR[t] + "44" }}>
                  Tier {t}
                </span>
              ))}
            </div>
          </div>
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
            <span style={{
              ...styles.tabCount,
              ...(activeTab === t.value ? styles.tabCountActive : {}),
            }}>
              {tabCount(t.value)}
            </span>
          </button>
        ))}
      </div>

      {/* ── Case table ───────────────────────────────────────── */}
      <div style={styles.tableWrapper}>
        <table style={styles.table}>
          <thead>
            <tr>
              {["#", "Case ID", "Patient", "Country", "Tier", "Urgency", "Pain", "Duration", "Images", "Status", "Created"].map((h) => (
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
                <td colSpan={11} style={styles.emptyCell}>
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

// SVG Donut chart — no external library, pure inline SVG
function UrgencyDonutChart({ cases }: { cases: PatientCase[] }) {
  const total = cases.length;
  const levels = Object.values(UrgencyLevel);
  const counts = levels.map((l) => cases.filter((c) => c.urgencyLevel === l).length);

  const R = 52;          // outer radius
  const r = 32;          // inner radius (hole)
  const CX = 70;         // centre x
  const CY = 70;         // centre y
  const circumference = 2 * Math.PI * R;

  // Build arc segments using stroke-dasharray on a circle
  let cumulativePct = 0;
  const segments = levels.map((level, i) => {
    const pct = total > 0 ? counts[i] / total : 0;
    const dash = pct * circumference;
    const gap = circumference - dash;
    // rotate so each segment starts after the previous
    const rotation = cumulativePct * 360 - 90; // -90 starts at top
    cumulativePct += pct;
    return { level, count: counts[i], pct, dash, gap, rotation };
  });

  // Dominant segment for centre label
  const maxIdx = counts.indexOf(Math.max(...counts));

  return (
    <div style={donutStyles.wrapper}>
      {/* SVG donut */}
      <div style={donutStyles.svgWrapper}>
        <svg width={140} height={140} viewBox="0 0 140 140">
          {/* Background ring */}
          <circle
            cx={CX} cy={CY} r={R}
            fill="none"
            stroke="#f1f5f9"
            strokeWidth={R - r}
          />
          {total === 0 ? null : segments.map((seg) => (
            seg.pct === 0 ? null : (
              <circle
                key={seg.level}
                cx={CX} cy={CY} r={R}
                fill="none"
                stroke={URGENCY_COLOR[seg.level]}
                strokeWidth={R - r}
                strokeDasharray={`${seg.dash} ${seg.gap}`}
                strokeLinecap="butt"
                style={{ transform: `rotate(${seg.rotation}deg)`, transformOrigin: `${CX}px ${CY}px` }}
              />
            )
          ))}
          {/* Centre label */}
          <text x={CX} y={CY - 6} textAnchor="middle" fontSize={22} fontWeight={800} fill="#0f172a">{total}</text>
          <text x={CX} y={CY + 12} textAnchor="middle" fontSize={9} fontWeight={600} fill="#94a3b8" letterSpacing={1}>CASES</text>
        </svg>
      </div>

      {/* Legend */}
      <div style={donutStyles.legend}>
        {segments.map((seg) => (
          <div key={seg.level} style={donutStyles.legendRow}>
            <span style={{ ...donutStyles.legendDot, backgroundColor: URGENCY_COLOR[seg.level] }} />
            <span style={{ ...donutStyles.legendLabel, color: URGENCY_COLOR[seg.level] }}>{seg.level}</span>
            <span style={donutStyles.legendCount}>{seg.count}</span>
            <span style={donutStyles.legendPct}>
              {total > 0 ? Math.round(seg.pct * 100) : 0}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

const donutStyles: Record<string, React.CSSProperties> = {
  wrapper: { display: "flex", alignItems: "center", gap: 12 },
  svgWrapper: { flexShrink: 0 },
  legend: { flex: 1, display: "flex", flexDirection: "column", gap: 7 },
  legendRow: { display: "flex", alignItems: "center", gap: 7 },
  legendDot: { width: 9, height: 9, borderRadius: "50%", flexShrink: 0 },
  legendLabel: { fontSize: 11, fontWeight: 700, flex: 1 },
  legendCount: { fontSize: 13, fontWeight: 800, color: "#0f172a", width: 18, textAlign: "right" },
  legendPct: { fontSize: 10, color: "#94a3b8", width: 32, textAlign: "right" },
};

function StatCard({ icon, value, label, color, highlight }: {
  icon: string; value: number; label: string; color: string; highlight?: boolean;
}) {
  return (
    <div style={{ ...styles.statCard, borderTop: `3px solid ${color}` }}>
      <span style={styles.statCardIcon}>{icon}</span>
      <span style={{ ...styles.statCardValue, color: highlight ? color : "#0f172a" }}>{value}</span>
      <span style={styles.statCardLabel}>{label}</span>
    </div>
  );
}

function CaseRow({ idx, c, onClick }: { idx: number; c: PatientCase; onClick: () => void }) {
  return (
    <tr
      style={styles.tr}
      onClick={onClick}
      onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "#f8fafc")}
      onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "")}
    >
      <td style={{ ...styles.td, color: "#94a3b8", width: 36 }}>{idx}</td>
      <td style={{ ...styles.td, fontFamily: "monospace", fontWeight: 600, color: "#0077B6" }}>
        {c.caseId}
      </td>
      <td style={{ ...styles.td, color: "#475569" }}>{c.patientAlias}</td>
      <td style={styles.td}>
        <span style={styles.flagChip}>{c.countryCode}</span>{" "}{c.country}
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
      <td style={{ ...styles.td, textAlign: "center" }}>
        {c.uploadedImageUrls.length > 0 ? (
          <span style={styles.imgBadge}>📷 {c.uploadedImageUrls.length}</span>
        ) : (
          <span style={{ color: "#cbd5e1" }}>—</span>
        )}
      </td>
      <td style={styles.td}>
        <Badge color={STATUS_COLOR[c.doctorDecisionStatus]} text={c.doctorDecisionStatus.replace("_", " ")} />
      </td>
      <td style={{ ...styles.td, color: "#94a3b8", fontSize: 11 }}>
        {new Date(c.createdAt).toLocaleString("en-GB", { dateStyle: "short", timeStyle: "short" })}
      </td>
    </tr>
  );
}

function Badge({ color, text }: { color: string; text: string }) {
  return (
    <span style={{
      backgroundColor: color + "1a",
      color,
      border: `1px solid ${color}44`,
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
  return <span style={{ color, fontWeight: 700, fontSize: 13 }}>{score}/10</span>;
}

// ── Styles ────────────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  pageHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 24,
  },
  pageTitle: { fontSize: 22, fontWeight: 800, color: "#0f172a", margin: "0 0 4px" },
  pageSubtitle: { fontSize: 13, color: "#64748b", margin: 0 },
  headerBadge: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    backgroundColor: "#E8F4FD",
    color: "#0077B6",
    borderRadius: 999,
    padding: "8px 18px",
    fontSize: 13,
    fontWeight: 600,
    border: "1px solid #0077B633",
  },
  headerBadgeIcon: { fontSize: 16 },

  // Stats cards
  statsRow: {
    display: "grid",
    gridTemplateColumns: "repeat(4, 1fr)",
    gap: 16,
    marginBottom: 20,
  },
  statCard: {
    backgroundColor: "#ffffff",
    borderRadius: 12,
    border: "1px solid #e2e8f0",
    padding: "18px 20px",
    display: "flex",
    flexDirection: "column" as const,
    gap: 4,
  },
  statCardIcon: { fontSize: 20, marginBottom: 4 },
  statCardValue: { fontSize: 28, fontWeight: 800, lineHeight: 1 },
  statCardLabel: { fontSize: 12, color: "#94a3b8", fontWeight: 500 },

  // Insights row
  insightsRow: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr 1fr",
    gap: 16,
    marginBottom: 24,
  },
  insightCard: {
    backgroundColor: "#ffffff",
    borderRadius: 12,
    border: "1px solid #e2e8f0",
    padding: "18px 20px",
  },
  insightTitle: { fontSize: 12, fontWeight: 700, color: "#94a3b8", letterSpacing: "0.06em", margin: "0 0 14px" },
  barRow: { display: "flex", alignItems: "center", gap: 10, marginBottom: 8 },
  barLabel: { fontSize: 11, fontWeight: 700, width: 72, flexShrink: 0 },
  countryLabel: { fontSize: 11, color: "#475569", width: 100, flexShrink: 0, display: "flex", alignItems: "center", gap: 5 },
  barTrack: { flex: 1, height: 6, backgroundColor: "#f1f5f9", borderRadius: 999 },
  barFill: { height: "100%", borderRadius: 999, transition: "width 0.3s" },
  barCount: { fontSize: 11, color: "#94a3b8", width: 20, textAlign: "right" as const },
  flagChip: {
    backgroundColor: "#f1f5f9",
    borderRadius: 4,
    padding: "1px 5px",
    fontSize: 10,
    fontWeight: 700,
    fontFamily: "monospace",
    color: "#475569",
  },

  // Doctor status
  doctorStatusCard: { display: "flex", alignItems: "center", gap: 10, marginBottom: 16 },
  doctorStatusAvatar: {
    width: 36,
    height: 36,
    borderRadius: "50%",
    backgroundColor: "#0077B6",
    color: "#fff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 13,
    fontWeight: 700,
    flexShrink: 0,
  },
  doctorStatusName: { fontSize: 13, fontWeight: 700, color: "#0f172a" },
  doctorStatusSpec: { fontSize: 11, color: "#64748b" },
  doctorStatusOnline: { display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: "#16a34a", fontWeight: 600, marginTop: 2 },
  onlineDot: { width: 6, height: 6, borderRadius: "50%", backgroundColor: "#16a34a", display: "inline-block" },
  tierList: {},
  tierListLabel: { fontSize: 10, color: "#94a3b8", fontWeight: 700, letterSpacing: "0.06em", marginBottom: 6 },
  tierChips: { display: "flex", gap: 6, flexWrap: "wrap" as const },
  tierChip: {
    borderRadius: 999,
    padding: "2px 10px",
    fontSize: 11,
    fontWeight: 700,
    border: "1px solid",
  },

  // Tabs
  tabRow: { display: "flex", gap: 8, marginBottom: 12 },
  tab: {
    backgroundColor: "#fff",
    border: "1px solid #e2e8f0",
    borderRadius: 8,
    padding: "7px 14px",
    fontSize: 13,
    color: "#64748b",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    gap: 6,
    fontWeight: 500,
  },
  tabActive: { backgroundColor: "#0f172a", color: "#f8fafc", borderColor: "#0f172a" },
  tabCount: {
    backgroundColor: "#e2e8f0",
    color: "#64748b",
    borderRadius: 999,
    padding: "1px 7px",
    fontSize: 10,
    fontWeight: 700,
  },
  tabCountActive: { backgroundColor: "#334155", color: "#f8fafc" },

  // Table
  tableWrapper: {
    backgroundColor: "#fff",
    borderRadius: 12,
    border: "1px solid #e2e8f0",
    overflow: "hidden",
  },
  table: { width: "100%", borderCollapse: "collapse" },
  th: {
    textAlign: "left",
    padding: "10px 14px",
    fontSize: 10,
    fontWeight: 700,
    color: "#94a3b8",
    letterSpacing: "0.07em",
    borderBottom: "1px solid #e2e8f0",
    backgroundColor: "#f8fafc",
  },
  tr: { cursor: "pointer", transition: "background 0.1s" },
  td: { padding: "11px 14px", fontSize: 13, color: "#334155", borderBottom: "1px solid #f1f5f9" },
  emptyCell: { padding: "32px", textAlign: "center", color: "#94a3b8", fontSize: 14 },
  imgBadge: {
    backgroundColor: "#f3e8ff",
    color: "#7c3aed",
    borderRadius: 999,
    padding: "2px 8px",
    fontSize: 11,
    fontWeight: 600,
  },
};
