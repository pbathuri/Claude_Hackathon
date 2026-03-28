// ============================================================
// src/components/OutcomeSubmissionForm.tsx
// Outcome Submission Form — Doctor Portal
//
// Renders a form for the doctor to submit their clinical guidance.
// Available fields are gated by the patient's country tier:
//
//   All tiers    : recommendedAction, followUpAdvice, generalNotes,
//                  languageOfCommunication, estimatedFollowUpDays
//   Tier 1–3     : referralSuggestion, referralUrgency
//   Tier 1–2     : treatmentNotes
//   Tier 1 only  : prescriptionDetails (only when action = PRESCRIBE)
//
// After submission the form switches to a read-only summary view.
// ============================================================

import { useState, FormEvent } from "react";
import { PatientCase, TierRule, OutcomeSubmission, RecommendedAction, CountryTier } from "../types";
import { useCases } from "../context/CasesContext";

// ── Human-readable labels for each action ────────────────────
const ACTION_LABELS: Record<RecommendedAction, string> = {
  [RecommendedAction.PRESCRIBE]: "Prescribe Medication",
  [RecommendedAction.LIMITED_TREATMENT]: "Limited Treatment Recommendation",
  [RecommendedAction.REFER_LOCAL]: "Refer to Local Facility",
  [RecommendedAction.REFER_SPECIALIST]: "Refer to Specialist",
  [RecommendedAction.GUIDANCE_ONLY]: "Guidance Only",
  [RecommendedAction.ADVICE_ONLY]: "Advice Only",
  [RecommendedAction.EMERGENCY_ESCALATION]: "Emergency Escalation",
};

const REFERRAL_ACTIONS = new Set<RecommendedAction>([
  RecommendedAction.REFER_LOCAL,
  RecommendedAction.REFER_SPECIALIST,
  RecommendedAction.EMERGENCY_ESCALATION,
]);

interface Props {
  patientCase: PatientCase;
  tierRule: TierRule;
  doctorId: string;
}

interface FormState {
  recommendedAction: RecommendedAction | "";
  prescriptionDetails: string;
  treatmentNotes: string;
  referralSuggestion: string;
  referralUrgency: "ROUTINE" | "URGENT" | "EMERGENCY" | "";
  followUpAdvice: string;
  generalNotes: string;
  estimatedFollowUpDays: string;
  languageOfCommunication: string;
}

const EMPTY_FORM: FormState = {
  recommendedAction: "",
  prescriptionDetails: "",
  treatmentNotes: "",
  referralSuggestion: "",
  referralUrgency: "",
  followUpAdvice: "",
  generalNotes: "",
  estimatedFollowUpDays: "",
  languageOfCommunication: "en",
};

export default function OutcomeSubmissionForm({ patientCase: c, tierRule, doctorId }: Props) {
  const { submitOutcome } = useCases();
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  // If the case already has an outcome, show the read-only view
  if (c.outcomeSubmission || submitted) {
    const o = c.outcomeSubmission;
    if (!o) return null;
    return <OutcomeReadOnly outcome={o} />;
  }

  // ── Derived visibility flags ─────────────────────────────
  const tier = c.countryTier;
  const action = form.recommendedAction as RecommendedAction | "";
  const canPrescribe = tier === CountryTier.TIER_1;
  const canTreat = tier <= CountryTier.TIER_2;
  const canRefer = tier <= CountryTier.TIER_3;
  const showPrescription = canPrescribe && action === RecommendedAction.PRESCRIBE;
  const showTreatment = canTreat && (
    action === RecommendedAction.LIMITED_TREATMENT || action === RecommendedAction.PRESCRIBE
  );
  const showReferral = canRefer && action !== "" && REFERRAL_ACTIONS.has(action as RecommendedAction);

  const set = (field: keyof FormState, value: string) => {
    setForm((f) => ({ ...f, [field]: value }));
    setErrors((e) => ({ ...e, [field]: undefined }));
  };

  // ── Validation ───────────────────────────────────────────
  const validate = (): boolean => {
    const errs: Partial<Record<keyof FormState, string>> = {};
    if (!form.recommendedAction) errs.recommendedAction = "Please select a recommended action.";
    if (!form.followUpAdvice.trim()) errs.followUpAdvice = "Follow-up advice is required.";
    if (!form.generalNotes.trim()) errs.generalNotes = "Clinical notes are required.";
    if (showPrescription && !form.prescriptionDetails.trim()) {
      errs.prescriptionDetails = "Prescription details are required when prescribing.";
    }
    if (showReferral && !form.referralSuggestion.trim()) {
      errs.referralSuggestion = "Referral destination is required.";
    }
    if (showReferral && !form.referralUrgency) {
      errs.referralUrgency = "Please select referral urgency.";
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  // ── Submit handler ────────────────────────────────────────
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setIsSubmitting(true);

    // Simulate network delay for demo realism
    await new Promise((r) => setTimeout(r, 600));

    const outcome: OutcomeSubmission = {
      submittedAt: new Date().toISOString(),
      submittedByDoctorId: doctorId,
      recommendedAction: form.recommendedAction as RecommendedAction,
      followUpAdvice: form.followUpAdvice.trim(),
      generalNotes: form.generalNotes.trim(),
      languageOfCommunication: form.languageOfCommunication || "en",
      ...(showPrescription && form.prescriptionDetails && {
        prescriptionDetails: form.prescriptionDetails.trim(),
      }),
      ...(showTreatment && form.treatmentNotes && {
        treatmentNotes: form.treatmentNotes.trim(),
      }),
      ...(showReferral && form.referralSuggestion && {
        referralSuggestion: form.referralSuggestion.trim(),
      }),
      ...(showReferral && form.referralUrgency && {
        referralUrgency: form.referralUrgency as OutcomeSubmission["referralUrgency"],
      }),
      ...(form.estimatedFollowUpDays && {
        estimatedFollowUpDays: parseInt(form.estimatedFollowUpDays, 10),
      }),
    };

    submitOutcome(c.caseId, doctorId, outcome);
    setIsSubmitting(false);
    setSubmitted(true);
  };

  // ── Render ────────────────────────────────────────────────
  return (
    <form onSubmit={handleSubmit} style={styles.form} noValidate>

      {/* Disclaimer banner — always visible */}
      <div style={styles.disclaimer}>
        <strong>Clinical Reminder:</strong> This platform assists triage only.
        You are the licensed clinician responsible for all guidance provided.
        AI has not made any diagnosis. All fields are your professional judgement.
      </div>

      {/* Recommended Action */}
      <Field label="Recommended Action *" error={errors.recommendedAction}>
        <select
          style={{ ...styles.input, ...(errors.recommendedAction ? styles.inputError : {}) }}
          value={form.recommendedAction}
          onChange={(e) => set("recommendedAction", e.target.value)}
        >
          <option value="">— Select an action —</option>
          {tierRule.allowedActions.map((a) => (
            <option key={a} value={a}>{ACTION_LABELS[a]}</option>
          ))}
        </select>
      </Field>

      {/* Prescription Details — Tier 1, action = PRESCRIBE only */}
      {showPrescription && (
        <Field
          label="Prescription Details *"
          hint="Drug name, dosage, frequency, duration. Tier 1 jurisdiction only."
          error={errors.prescriptionDetails}
        >
          <textarea
            style={{ ...styles.textarea, ...(errors.prescriptionDetails ? styles.inputError : {}) }}
            rows={3}
            placeholder="e.g. Amoxicillin 500mg, 3× daily for 7 days"
            value={form.prescriptionDetails}
            onChange={(e) => set("prescriptionDetails", e.target.value)}
          />
        </Field>
      )}

      {/* Treatment Notes — Tier 1–2 */}
      {showTreatment && (
        <Field
          label="Treatment Notes"
          hint="OTC-equivalent or limited treatment recommendations."
          error={errors.treatmentNotes}
        >
          <textarea
            style={styles.textarea}
            rows={3}
            placeholder="e.g. Apply warm compress 3× daily, use OTC antiseptic…"
            value={form.treatmentNotes}
            onChange={(e) => set("treatmentNotes", e.target.value)}
          />
        </Field>
      )}

      {/* Referral fields — Tier 1–3 when a referral action is selected */}
      {showReferral && (
        <>
          <Field
            label="Referral Destination *"
            hint="Name or type of facility / specialist to refer to."
            error={errors.referralSuggestion}
          >
            <input
              type="text"
              style={{ ...styles.input, ...(errors.referralSuggestion ? styles.inputError : {}) }}
              placeholder="e.g. Nearest district hospital, ophthalmologist"
              value={form.referralSuggestion}
              onChange={(e) => set("referralSuggestion", e.target.value)}
            />
          </Field>

          <Field label="Referral Urgency *" error={errors.referralUrgency}>
            <div style={styles.radioGroup}>
              {(["ROUTINE", "URGENT", "EMERGENCY"] as const).map((u) => (
                <label key={u} style={styles.radioLabel}>
                  <input
                    type="radio"
                    name="referralUrgency"
                    value={u}
                    checked={form.referralUrgency === u}
                    onChange={() => set("referralUrgency", u)}
                    style={{ marginRight: 6 }}
                  />
                  <span style={{
                    color: u === "EMERGENCY" ? "#dc2626" : u === "URGENT" ? "#d97706" : "#16a34a",
                    fontWeight: 600,
                  }}>
                    {u}
                  </span>
                </label>
              ))}
            </div>
          </Field>
        </>
      )}

      {/* Follow-up Advice — required for all tiers */}
      <Field
        label="Follow-up Advice *"
        hint="What the patient should do next. Plain language, actionable."
        error={errors.followUpAdvice}
      >
        <textarea
          style={{ ...styles.textarea, ...(errors.followUpAdvice ? styles.inputError : {}) }}
          rows={3}
          placeholder="e.g. Seek in-person care within 48 hours if symptoms worsen…"
          value={form.followUpAdvice}
          onChange={(e) => set("followUpAdvice", e.target.value)}
        />
      </Field>

      {/* General Notes — required for all tiers */}
      <Field
        label="Clinical Notes *"
        hint="Your professional assessment. Not sent to the patient directly."
        error={errors.generalNotes}
      >
        <textarea
          style={{ ...styles.textarea, ...(errors.generalNotes ? styles.inputError : {}) }}
          rows={4}
          placeholder="Summarise your clinical reasoning, concerns, and observations…"
          value={form.generalNotes}
          onChange={(e) => set("generalNotes", e.target.value)}
        />
      </Field>

      {/* Optional fields row */}
      <div style={styles.optionalRow}>
        <Field label="Est. Follow-up (days)" style={{ flex: 1 }}>
          <input
            type="number"
            min={0}
            max={365}
            style={styles.input}
            placeholder="e.g. 3"
            value={form.estimatedFollowUpDays}
            onChange={(e) => set("estimatedFollowUpDays", e.target.value)}
          />
        </Field>
        <Field label="Language of Communication" style={{ flex: 1 }}>
          <input
            type="text"
            style={styles.input}
            placeholder="BCP 47 tag, e.g. en, sw, fr"
            value={form.languageOfCommunication}
            onChange={(e) => set("languageOfCommunication", e.target.value)}
          />
        </Field>
      </div>

      {/* Jurisdiction restriction reminder */}
      {tierRule.restrictions.length > 0 && (
        <div style={styles.restrictionBox}>
          <p style={styles.restrictionTitle}>Active Restrictions for Tier {c.countryTier}</p>
          {tierRule.restrictions.map((r, i) => (
            <p key={i} style={styles.restrictionItem}>✗ {r}</p>
          ))}
        </div>
      )}

      {/* Submit button */}
      <button
        type="submit"
        style={{ ...styles.submitBtn, ...(isSubmitting ? styles.submitBtnDisabled : {}) }}
        disabled={isSubmitting}
      >
        {isSubmitting ? "Submitting…" : "Submit Outcome"}
      </button>
    </form>
  );
}

// ── Read-only outcome summary ─────────────────────────────────
function OutcomeReadOnly({ outcome }: { outcome: OutcomeSubmission }) {
  return (
    <div>
      <div style={styles.completedBanner}>
        ✓ Outcome submitted on {new Date(outcome.submittedAt).toLocaleString("en-GB")}
      </div>
      <ReadRow label="Action" value={ACTION_LABELS[outcome.recommendedAction] ?? outcome.recommendedAction} />
      {outcome.prescriptionDetails && (
        <ReadRow label="Prescription" value={outcome.prescriptionDetails} />
      )}
      {outcome.treatmentNotes && (
        <ReadRow label="Treatment Notes" value={outcome.treatmentNotes} />
      )}
      {outcome.referralSuggestion && (
        <ReadRow label="Referral" value={`${outcome.referralSuggestion} (${outcome.referralUrgency})`} />
      )}
      <ReadRow label="Follow-up Advice" value={outcome.followUpAdvice} />
      <ReadRow label="Clinical Notes" value={outcome.generalNotes} />
      {outcome.estimatedFollowUpDays !== undefined && (
        <ReadRow label="Follow-up in" value={`${outcome.estimatedFollowUpDays} days`} />
      )}
      <ReadRow label="Language" value={outcome.languageOfCommunication.toUpperCase()} />
    </div>
  );
}

function ReadRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={styles.readRow}>
      <span style={styles.readLabel}>{label}</span>
      <span style={styles.readValue}>{value}</span>
    </div>
  );
}

// ── Field wrapper ─────────────────────────────────────────────
function Field({
  label,
  hint,
  error,
  children,
  style,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <div style={{ ...styles.fieldGroup, ...style }}>
      <label style={styles.fieldLabel}>{label}</label>
      {hint && <p style={styles.fieldHint}>{hint}</p>}
      {children}
      {error && <p style={styles.fieldError}>{error}</p>}
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  form: { display: "flex", flexDirection: "column", gap: 16 },
  disclaimer: {
    backgroundColor: "#fefce8",
    border: "1px solid #fde047",
    borderRadius: 8,
    padding: "10px 14px",
    fontSize: 11,
    color: "#713f12",
    lineHeight: 1.5,
  },
  fieldGroup: { display: "flex", flexDirection: "column", gap: 4 },
  fieldLabel: { fontSize: 11, fontWeight: 700, color: "#475569", letterSpacing: "0.04em" },
  fieldHint: { fontSize: 11, color: "#94a3b8", margin: 0 },
  fieldError: { fontSize: 11, color: "#dc2626", margin: 0, marginTop: 2 },
  input: {
    backgroundColor: "#f8fafc",
    border: "1px solid #e2e8f0",
    borderRadius: 7,
    padding: "9px 12px",
    fontSize: 13,
    color: "#0f172a",
    outline: "none",
    width: "100%",
  },
  inputError: { borderColor: "#fca5a5", backgroundColor: "#fff5f5" },
  textarea: {
    backgroundColor: "#f8fafc",
    border: "1px solid #e2e8f0",
    borderRadius: 7,
    padding: "9px 12px",
    fontSize: 13,
    color: "#0f172a",
    outline: "none",
    width: "100%",
    resize: "vertical" as const,
    lineHeight: 1.6,
  },
  radioGroup: { display: "flex", gap: 20, padding: "6px 0" },
  radioLabel: { display: "flex", alignItems: "center", fontSize: 13, cursor: "pointer" },
  optionalRow: { display: "flex", gap: 12 },
  restrictionBox: {
    backgroundColor: "#fef2f2",
    border: "1px solid #fecaca",
    borderRadius: 8,
    padding: "10px 14px",
  },
  restrictionTitle: { fontSize: 11, fontWeight: 700, color: "#991b1b", marginBottom: 6 },
  restrictionItem: { fontSize: 11, color: "#dc2626", marginBottom: 3 },
  submitBtn: {
    backgroundColor: "#0f172a",
    color: "#f8fafc",
    border: "none",
    borderRadius: 8,
    padding: "12px",
    fontSize: 14,
    fontWeight: 700,
    cursor: "pointer",
    marginTop: 4,
  },
  submitBtnDisabled: {
    backgroundColor: "#64748b",
    cursor: "not-allowed",
  },
  completedBanner: {
    backgroundColor: "#f0fdf4",
    border: "1px solid #86efac",
    borderRadius: 8,
    padding: "10px 14px",
    color: "#166534",
    fontWeight: 700,
    fontSize: 13,
    marginBottom: 16,
  },
  readRow: {
    display: "flex",
    flexDirection: "column",
    padding: "8px 0",
    borderBottom: "1px solid #f1f5f9",
    gap: 3,
  },
  readLabel: { fontSize: 11, color: "#94a3b8", fontWeight: 700 },
  readValue: { fontSize: 13, color: "#334155", lineHeight: 1.6 },
};
