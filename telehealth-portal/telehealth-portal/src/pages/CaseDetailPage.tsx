// src/pages/CaseDetailPage.tsx
// ──────────────────────────────────────────────────────────────
// Case detail view. Layout:
//   [TierStatusBar — persistent top banner]
//   [CapabilityDisclosureCard]
//   [PatientDataPanel]
//   [OutcomeSubmissionForm  ← placeholder for Step 4]
// ──────────────────────────────────────────────────────────────

import { useEffect, type CSSProperties } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useCases } from "../context/CasesContext";
import { useAuth } from "../context/AuthContext";
import { getTierRule } from "../MockData/tierRules";
import { CountryTier, DoctorDecisionStatus, UrgencyLevel } from "../types";
import OutcomeSubmissionForm from "../components/OutcomeSubmissionForm";

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

  // Auto-mark as IN_REVIEW when doctor opens a PENDING case
  useEffect(() => {
    if (c && doctor && c.doctorDecisionStatus === DoctorDecisionStatus.PENDING) {
      markInReview(c.caseId, doctor.doctorId);
    }
  }, [c?.caseId]); // eslint-disable-line

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

  return (
    <div style={styles.page}>
      {/* ── Back button ────────────────────────────────────── */}
      <button style={styles.backBtn} onClick={() => navigate("/dashboard")}>
        ← Back to Inbox
      </button>

      {/* ── [1] Persistent Tier Status Bar ─────────────────── */}
      <TierStatusBar tier={c.countryTier} tierRule={tierRule} />

      <div style={styles.contentGrid}>
        {/* Left column */}
        <div style={styles.leftCol}>
          {/* ── [2] Capability Disclosure Card ───────────────── */}
          <CapabilityDisclosureCard tierRule={tierRule} />

          {/* ── [3] Patient Data Panel ───────────────────────── */}
          <section style={styles.card}>
            <h3 style={styles.cardTitle}>Patient Information</h3>
            <Row label="Case ID" value={c.caseId} mono />
            <Row label="Patient Alias" value={c.patientAlias} />
            <Row label="Country" value={`${c.country} (${c.countryCode})`} />
            <Row label="Intake Channel" value={c.intakeChannel} />
            <Row label="Language" value={c.intakeLanguage.toUpperCase()} />
            <Row label="Consent" value={c.consentGiven ? "✓ Verbal consent obtained" : "✗ No consent recorded"} />
          </section>

          <section style={styles.card}>
            <h3 style={styles.cardTitle}>Symptom Summary</h3>
            <div style={styles.urgencyRow}>
              <span style={{ ...styles.urgencyBadge, backgroundColor: URGENCY_COLOR[c.urgencyLevel] + "22", color: URGENCY_COLOR[c.urgencyLevel], borderColor: URGENCY_COLOR[c.urgencyLevel] + "55" }}>
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

          {/* Images */}
          {c.uploadedImageUrls.length > 0 && (
            <section style={styles.card}>
              <h3 style={styles.cardTitle}>Uploaded Images</h3>
              <div style={styles.imageGrid}>
                {c.uploadedImageUrls.map((url, i) => (
                  <div key={i} style={styles.imagePlaceholder}>
                    📷 Image {i + 1}
                    <span style={styles.imageUrl}>{url.split("/").pop()}</span>
                  </div>
                ))}
              </div>
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
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────

function TierStatusBar({ tier, tierRule }: { tier: CountryTier; tierRule: ReturnType<typeof getTierRule> }) {
  return (
    <div style={{ ...styles.tierBar, backgroundColor: tierRule.badgeColor + "18", borderColor: tierRule.badgeColor + "55" }}>
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
    <section style={{ ...styles.disclosureCard, borderColor: tierRule.badgeColor + "55" }}>
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
const styles: Record<string, CSSProperties> = {
  page: { maxWidth: 1100, margin: "0 auto" },
  backBtn: {
    background: "none", border: "none", color: "#64748b", fontSize: 13,
    cursor: "pointer", padding: "0 0 16px", display: "block",
  },
  tierBar: {
    display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
    padding: "12px 18px", borderRadius: 10, border: "1px solid",
    marginBottom: 20,
  },
  tierBadge: { borderRadius: 6, padding: "3px 10px", fontSize: 12, fontWeight: 700 },
  tierLabel: { fontWeight: 700, fontSize: 14 },
  tierWarning: { color: "#b45309", fontSize: 12, marginLeft: "auto" },
  contentGrid: { display: "grid", gridTemplateColumns: "1fr 380px", gap: 20, alignItems: "start" },
  leftCol: { display: "flex", flexDirection: "column", gap: 16 },
  rightCol: { display: "flex", flexDirection: "column", gap: 16 },
  card: {
    backgroundColor: "#fff", borderRadius: 12, border: "1px solid #e2e8f0",
    padding: "20px 22px",
  },
  cardTitle: { fontSize: 14, fontWeight: 700, color: "#0f172a", margin: "0 0 16px" },
  disclosureCard: {
    backgroundColor: "#fffbeb", borderRadius: 12, border: "2px solid",
    padding: "18px 22px",
  },
  disclosureTitle: { fontSize: 14, fontWeight: 700, margin: "0 0 10px" },
  disclosureDesc: { fontSize: 13, color: "#44403c", lineHeight: 1.6, margin: "0 0 12px" },
  restrictionList: { margin: 0, padding: 0, listStyle: "none" },
  restrictionItem: { fontSize: 12, color: "#dc2626", marginBottom: 4, paddingLeft: 2 },
  rowItem: { display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid #f1f5f9" },
  rowLabel: { fontSize: 12, color: "#94a3b8", fontWeight: 600 },
  rowValue: { fontSize: 13, color: "#334155", maxWidth: "60%", textAlign: "right" },
  urgencyRow: { display: "flex", gap: 10, alignItems: "center", marginBottom: 12 },
  urgencyBadge: { borderRadius: 999, padding: "2px 10px", fontSize: 11, fontWeight: 700, border: "1px solid" },
  painScore: { fontSize: 13, fontWeight: 700, color: "#0f172a" },
  duration: { fontSize: 12, color: "#64748b" },
  symptomText: { fontSize: 13, color: "#334155", lineHeight: 1.7, margin: "0 0 12px" },
  bodyAreaRow: { display: "flex", flexWrap: "wrap", gap: 6 },
  bodyTag: { backgroundColor: "#f1f5f9", color: "#475569", borderRadius: 6, padding: "3px 9px", fontSize: 11, fontWeight: 600 },
  imageGrid: { display: "flex", gap: 10 },
  imagePlaceholder: {
    backgroundColor: "#f8fafc", border: "1px dashed #cbd5e1", borderRadius: 8,
    padding: "16px", fontSize: 12, color: "#94a3b8", display: "flex",
    flexDirection: "column", alignItems: "center", gap: 4, minWidth: 120,
  },
  imageUrl: { fontSize: 10, color: "#cbd5e1", wordBreak: "break-all", textAlign: "center" },
  notFound: { textAlign: "center", padding: 60, color: "#64748b" },
};
