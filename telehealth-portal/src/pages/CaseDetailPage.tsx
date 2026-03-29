// src/pages/CaseDetailPage.tsx
// ──────────────────────────────────────────────────────────────
// Case detail view with WHO content from Claude_Hackathon.
// Includes: AI Triage Notes, Red Flag Indicators, SMS Image Viewer,
// Jurisdiction Disclosure, and Outcome Submission Form.
// ──────────────────────────────────────────────────────────────

import { useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useCases } from "../context/CasesContext";
import { useAuth } from "../context/AuthContext";
import { getTierRule } from "../MockData/tierRules";
import { CountryTier, DoctorDecisionStatus, UrgencyLevel } from "../types";
import OutcomeSubmissionForm from "../components/OutcomeSubmissionForm";
import ImageViewer from "../components/ImageViewer";

const URGENCY_COLOR: Record<UrgencyLevel, string> = {
  [UrgencyLevel.EMERGENCY]: "#ef4444",
  [UrgencyLevel.HIGH]: "#f97316",
  [UrgencyLevel.MEDIUM]: "#eab308",
  [UrgencyLevel.LOW]: "#22c55e",
};

export default function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const { getCaseById, markInReview } = useCases();
  const { doctor } = useAuth();
  const navigate = useNavigate();

  const c = caseId ? getCaseById(caseId) : undefined;

  // Auto-mark as IN_REVIEW when doctor opens a PENDING case (assigns via API)
  useEffect(() => {
    if (!c || !doctor || c.doctorDecisionStatus !== DoctorDecisionStatus.PENDING) return;
    void markInReview(c.caseId, doctor.doctorId);
  }, [c?.caseId, c?.doctorDecisionStatus, doctor?.doctorId, markInReview]);

  if (!c) {
    return (
      <div style={styles.notFound}>
        <p>Case not found.</p>
        <button style={styles.backBtn} onClick={() => navigate("/dashboard")}>
          ← Back to Dashboard
        </button>
      </div>
    );
  }

  const tierRule = getTierRule(c.countryTier);

  // Derive AI-structured notes from symptom data (enhanced display)
  const aiNotes = (c as any).aiStructuredNotes as AiNote[] | undefined;
  const redFlags = (c as any).redFlagIndicators as string[] | undefined;

  return (
    <div style={styles.page}>
      {/* ── Back button ────────────────────────────────────── */}
      <button style={styles.backBtn} onClick={() => navigate("/dashboard")}>
        ← Back to Case Queue
      </button>

      {/* ── [1] Persistent Tier Status Bar ─────────────────── */}
      <TierStatusBar tier={c.countryTier} tierRule={tierRule} />

      <div style={styles.contentGrid}>
        {/* Left column */}
        <div style={styles.leftCol}>

          {/* ── [2] Capability Disclosure Card ───────────────── */}
          <CapabilityDisclosureCard tierRule={tierRule} />

          {/* ── [3] Patient Information ───────────────────────── */}
          <section style={styles.card}>
            <h3 style={styles.cardTitle}>Patient Information</h3>
            <Row label="Case ID" value={c.caseId} mono />
            <Row label="Patient Alias" value={c.patientAlias} />
            <Row label="Country" value={`${c.country} (${c.countryCode})`} />
            <Row label="Intake Channel" value={c.intakeChannel} />
            <Row label="Language" value={c.intakeLanguage.toUpperCase()} />
            <Row label="Consent" value={c.consentGiven ? "✓ Verbal consent obtained" : "✗ No consent recorded"} />
            <Row label="Priority Score" value={`${calcPriority(c.urgencyLevel, c.countryTier)} / 44`} />
          </section>

          {/* ── [4] Symptom Summary ──────────────────────────── */}
          <section style={styles.card}>
            <h3 style={styles.cardTitle}>Symptom Summary</h3>
            <div style={styles.urgencyRow}>
              <span style={{
                ...styles.urgencyBadge,
                backgroundColor: URGENCY_COLOR[c.urgencyLevel] + "1a",
                color: URGENCY_COLOR[c.urgencyLevel],
                borderColor: URGENCY_COLOR[c.urgencyLevel] + "44",
              }}>
                {c.urgencyLevel}
              </span>
              <span style={styles.painScore}>Pain: {c.painScore}/10</span>
              <span style={styles.duration}>Duration: {c.symptomDurationDays} day{c.symptomDurationDays !== 1 ? "s" : ""}</span>
            </div>
            <p style={styles.symptomText}>{c.symptomSummary}</p>
            <div style={styles.bodyAreaRow}>
              {c.affectedBodyArea.map((area) => (
                <span key={area} style={styles.bodyTag}>{area}</span>
              ))}
            </div>
          </section>

          {/* ── [5] Red Flag Indicators ──────────────────────── */}
          {redFlags && redFlags.length > 0 && (
            <section style={styles.redFlagCard}>
              <h3 style={styles.redFlagTitle}>⚠ Red Flag Indicators</h3>
              <p style={styles.redFlagSubtitle}>
                AI-identified clinical warning signs requiring immediate attention.
              </p>
              <div style={styles.redFlagList}>
                {redFlags.map((flag, i) => (
                  <div key={i} style={styles.redFlagItem}>
                    <span style={styles.redFlagDot}>●</span>
                    {flag}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* ── [6] AI Triage Notes ──────────────────────────── */}
          {aiNotes && aiNotes.length > 0 && (
            <section style={styles.card}>
              <h3 style={styles.cardTitle}>
                🤖 AI Triage Notes
                <span style={styles.aiNoteBadge}>WHO ICD-11</span>
              </h3>
              {aiNotes.map((note, i) => (
                <div key={i} style={styles.aiNoteItem}>
                  <div style={styles.aiNoteHeader}>
                    <span style={styles.aiNoteCategory}>{note.category}</span>
                    {note.icdCode && (
                      <span style={styles.icdChip}>{note.icdCode}</span>
                    )}
                  </div>
                  <p style={styles.aiNoteText}>{note.finding}</p>
                  {note.confidence && (
                    <div style={styles.confidenceBar}>
                      <span style={styles.confidenceLabel}>Confidence</span>
                      <div style={styles.confBarTrack}>
                        <div style={{
                          ...styles.confBarFill,
                          width: `${note.confidence}%`,
                          backgroundColor: note.confidence > 75 ? "#16a34a" : note.confidence > 50 ? "#eab308" : "#f97316",
                        }} />
                      </div>
                      <span style={styles.confidencePct}>{note.confidence}%</span>
                    </div>
                  )}
                </div>
              ))}
            </section>
          )}

          {/* ── [7] SMS Image Viewer ─────────────────────────── */}
          {c.uploadedImageUrls.length > 0 && (
            <section style={styles.card}>
              <h3 style={styles.cardTitle}>
                📷 Patient Images
                <span style={styles.smsImageBadge}>
                  📱 Received via {c.intakeChannel === "COMBINED" ? "SMS / Voice" : c.intakeChannel}
                </span>
              </h3>
              <p style={styles.imageNote}>
                {c.uploadedImageUrls.length} image{c.uploadedImageUrls.length !== 1 ? "s" : ""} submitted by the patient during intake.
                Click any thumbnail to view full size.
              </p>
              <ImageViewer
                imageUrls={c.uploadedImageUrls}
                intakeChannel={c.intakeChannel}
              />
            </section>
          )}
        </div>

        {/* Right column — outcome submission form */}
        <div style={styles.rightCol}>
          <section style={styles.card}>
            <h3 style={styles.cardTitle}>Outcome Submission</h3>
            {doctor && (
              <OutcomeSubmissionForm
                patientCase={c}
                tierRule={tierRule}
                doctorId={doctor.doctorId}
              />
            )}
          </section>

          {/* ICD-11 Quick Reference */}
          <section style={styles.kgCard}>
            <h4 style={styles.kgTitle}>
              🔬 ICD-11 Triage Reference
            </h4>
            <p style={styles.kgDesc}>
              WHO Knowledge Graph insights for symptoms matching this case:
            </p>
            <div style={styles.kgChips}>
              {c.affectedBodyArea.map((area) => (
                <span key={area} style={styles.kgChip}>{area}</span>
              ))}
            </div>
            <div style={styles.kgLink}>
              <span style={styles.kgLinkIcon}>📖</span>
              <span style={styles.kgLinkText}>
                ICD-11 classification guided by WHO Telehealth Guidelines 2022
              </span>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

// ── Types ──────────────────────────────────────────────────────
interface AiNote {
  category: string;
  finding: string;
  icdCode?: string;
  confidence?: number;
}

// ── Helper ────────────────────────────────────────────────────
function calcPriority(urgency: UrgencyLevel, tier: CountryTier): number {
  const uScore = { EMERGENCY: 1, HIGH: 2, MEDIUM: 3, LOW: 4 }[urgency] ?? 4;
  const tScore = tier;
  return uScore * 10 + tScore;
}

// ── Sub-components ────────────────────────────────────────────

function TierStatusBar({ tier, tierRule }: { tier: CountryTier; tierRule: ReturnType<typeof getTierRule> }) {
  return (
    <div style={{ ...styles.tierBar, backgroundColor: tierRule.badgeColor + "12", borderColor: tierRule.badgeColor + "44" }}>
      <span style={{ ...styles.tierBadge, backgroundColor: tierRule.badgeColor, color: "#fff" }}>
        Tier {tier}
      </span>
      <span style={{ ...styles.tierLabel, color: tierRule.badgeColor }}>
        {tierRule.label}
      </span>
      {tierRule.uiWarning && (
        <span style={styles.tierWarning}>⚠ {tierRule.uiWarning}</span>
      )}
    </div>
  );
}

function CapabilityDisclosureCard({ tierRule }: { tierRule: ReturnType<typeof getTierRule> }) {
  return (
    <section style={{ ...styles.disclosureCard, borderColor: tierRule.badgeColor + "44" }}>
      <h3 style={{ ...styles.disclosureTitle, color: tierRule.badgeColor }}>
        ⚖ Jurisdiction Capability Disclosure
      </h3>
      <p style={styles.disclosureDesc}>{tierRule.description}</p>
      {tierRule.restrictions.length > 0 && (
        <ul style={styles.restrictionList}>
          {tierRule.restrictions.map((r, i) => (
            <li key={i} style={styles.restrictionItem}>✗ {r}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={styles.rowItem}>
      <span style={styles.rowLabel}>{label}</span>
      <span style={{ ...styles.rowValue, fontFamily: mono ? "monospace" : "inherit" }}>{value}</span>
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  page: { maxWidth: 1140, margin: "0 auto" },
  backBtn: {
    background: "none", border: "none", color: "#64748b", fontSize: 13,
    cursor: "pointer", padding: "0 0 16px", display: "block",
  },

  // Tier bar
  tierBar: {
    display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
    padding: "12px 18px", borderRadius: 10, border: "1px solid",
    marginBottom: 20,
  },
  tierBadge: { borderRadius: 6, padding: "3px 10px", fontSize: 12, fontWeight: 700 },
  tierLabel: { fontWeight: 700, fontSize: 14 },
  tierWarning: { color: "#b45309", fontSize: 12, marginLeft: "auto" },

  // Grid
  contentGrid: { display: "grid", gridTemplateColumns: "1fr 380px", gap: 20, alignItems: "start" },
  leftCol: { display: "flex", flexDirection: "column", gap: 16 },
  rightCol: { display: "flex", flexDirection: "column", gap: 16 },

  // Cards
  card: {
    backgroundColor: "#fff", borderRadius: 12, border: "1px solid #e2e8f0",
    padding: "20px 22px",
  },
  cardTitle: {
    fontSize: 14, fontWeight: 700, color: "#0f172a", margin: "0 0 16px",
    display: "flex", alignItems: "center", gap: 10,
  },

  // Disclosure
  disclosureCard: {
    backgroundColor: "#fffbeb", borderRadius: 12, border: "2px solid",
    padding: "18px 22px",
  },
  disclosureTitle: { fontSize: 14, fontWeight: 700, margin: "0 0 10px" },
  disclosureDesc: { fontSize: 13, color: "#44403c", lineHeight: 1.6, margin: "0 0 12px" },
  restrictionList: { margin: 0, padding: 0, listStyle: "none" },
  restrictionItem: { fontSize: 12, color: "#dc2626", marginBottom: 4, paddingLeft: 2 },

  // Patient info rows
  rowItem: { display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid #f1f5f9" },
  rowLabel: { fontSize: 12, color: "#94a3b8", fontWeight: 600 },
  rowValue: { fontSize: 13, color: "#334155", maxWidth: "60%", textAlign: "right" },

  // Symptom
  urgencyRow: { display: "flex", gap: 10, alignItems: "center", marginBottom: 12 },
  urgencyBadge: { borderRadius: 999, padding: "2px 10px", fontSize: 11, fontWeight: 700, border: "1px solid" },
  painScore: { fontSize: 13, fontWeight: 700, color: "#0f172a" },
  duration: { fontSize: 12, color: "#64748b" },
  symptomText: { fontSize: 13, color: "#334155", lineHeight: 1.7, margin: "0 0 12px" },
  bodyAreaRow: { display: "flex", flexWrap: "wrap", gap: 6 },
  bodyTag: { backgroundColor: "#f1f5f9", color: "#475569", borderRadius: 6, padding: "3px 9px", fontSize: 11, fontWeight: 600 },

  // Red flags
  redFlagCard: {
    backgroundColor: "#fff5f5",
    borderRadius: 12,
    border: "1.5px solid #fecaca",
    padding: "18px 22px",
  },
  redFlagTitle: { fontSize: 14, fontWeight: 700, color: "#dc2626", margin: "0 0 6px" },
  redFlagSubtitle: { fontSize: 12, color: "#ef4444", margin: "0 0 14px", opacity: 0.8 },
  redFlagList: { display: "flex", flexDirection: "column", gap: 6 },
  redFlagItem: { display: "flex", alignItems: "flex-start", gap: 8, fontSize: 13, color: "#991b1b", lineHeight: 1.5 },
  redFlagDot: { color: "#ef4444", fontSize: 8, marginTop: 4, flexShrink: 0 },

  // AI notes
  aiNoteBadge: {
    backgroundColor: "#E8F4FD",
    color: "#0077B6",
    borderRadius: 999,
    padding: "2px 8px",
    fontSize: 10,
    fontWeight: 700,
    border: "1px solid #0077B633",
    marginLeft: 4,
  },
  aiNoteItem: {
    borderBottom: "1px solid #f1f5f9",
    paddingBottom: 14,
    marginBottom: 14,
  },
  aiNoteHeader: { display: "flex", alignItems: "center", gap: 8, marginBottom: 6 },
  aiNoteCategory: { fontSize: 11, fontWeight: 700, color: "#0077B6", textTransform: "uppercase", letterSpacing: "0.06em" },
  icdChip: {
    backgroundColor: "#f0fdf4",
    color: "#16a34a",
    borderRadius: 4,
    padding: "1px 7px",
    fontSize: 10,
    fontWeight: 700,
    fontFamily: "monospace",
    border: "1px solid #bbf7d0",
  },
  aiNoteText: { fontSize: 13, color: "#334155", lineHeight: 1.6, margin: "0 0 8px" },
  confidenceBar: { display: "flex", alignItems: "center", gap: 8 },
  confidenceLabel: { fontSize: 10, color: "#94a3b8", width: 62, flexShrink: 0 },
  confBarTrack: { flex: 1, height: 5, backgroundColor: "#f1f5f9", borderRadius: 999 },
  confBarFill: { height: "100%", borderRadius: 999 },
  confidencePct: { fontSize: 10, color: "#64748b", width: 32, textAlign: "right" },

  // Image section
  smsImageBadge: {
    backgroundColor: "#f3e8ff",
    color: "#7c3aed",
    borderRadius: 999,
    padding: "2px 8px",
    fontSize: 10,
    fontWeight: 700,
    border: "1px solid #e9d5ff",
    marginLeft: 4,
  },
  imageNote: { fontSize: 12, color: "#64748b", margin: "0 0 12px" },

  // KG card
  kgCard: {
    backgroundColor: "#fff",
    borderRadius: 12,
    border: "1px solid #e2e8f0",
    padding: "18px 20px",
  },
  kgTitle: { fontSize: 13, fontWeight: 700, color: "#0f172a", margin: "0 0 6px" },
  kgDesc: { fontSize: 12, color: "#64748b", margin: "0 0 12px", lineHeight: 1.5 },
  kgChips: { display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 14 },
  kgChip: {
    backgroundColor: "#E8F4FD",
    color: "#0077B6",
    borderRadius: 999,
    padding: "3px 10px",
    fontSize: 11,
    fontWeight: 600,
    border: "1px solid #0077B633",
  },
  kgLink: { display: "flex", alignItems: "flex-start", gap: 8, backgroundColor: "#f8fafc", borderRadius: 8, padding: "10px 12px" },
  kgLinkIcon: { fontSize: 14, flexShrink: 0 },
  kgLinkText: { fontSize: 11, color: "#64748b", lineHeight: 1.5 },

  // Not found
  notFound: { textAlign: "center", padding: 60, color: "#64748b" },
};
