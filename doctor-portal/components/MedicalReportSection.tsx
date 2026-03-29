"use client";

import { useState } from "react";
import {
  setCaseOverlay,
  type MedicalReportPayload,
  type ReportStatus,
} from "@/lib/case-overlays";
import { submitResponse } from "@/lib/api";
import { getSessionLicense } from "@/lib/auth-storage";
import { AlertTriangle, CheckCircle, Send } from "lucide-react";

interface Props {
  caseId: string;
  reportStatus: ReportStatus;
  report?: MedicalReportPayload;
  onAfterSubmit: () => void;
}

function buildGuidanceText(payload: MedicalReportPayload): string {
  return [
    "--- Medical report (portal) ---",
    `Chief complaint & clinical assessment: ${payload.chiefComplaint}`,
    `Doctor's diagnosis: ${payload.diagnosis}`,
    `Doctor's notes & recommendations: ${payload.doctorNotes}`,
    `Emergency referral requested: ${payload.isEmergencyReferral ? "Yes" : "No"}`,
  ].join("\n");
}

export default function MedicalReportSection({ caseId, reportStatus, report, onAfterSubmit }: Props) {
  const [chiefComplaint, setChiefComplaint] = useState(report?.chiefComplaint ?? "");
  const [diagnosis, setDiagnosis] = useState(report?.diagnosis ?? "");
  const [doctorNotes, setDoctorNotes] = useState(report?.doctorNotes ?? "");
  const [isEmergencyReferral, setIsEmergencyReferral] = useState(report?.isEmergencyReferral ?? false);
  const [submitting, setSubmitting] = useState(false);

  const formValid =
    chiefComplaint.trim().length > 0 && diagnosis.trim().length > 0 && doctorNotes.trim().length > 0;

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formValid) return;
    setSubmitting(true);
    const payload: MedicalReportPayload = {
      chiefComplaint: chiefComplaint.trim(),
      diagnosis: diagnosis.trim(),
      doctorNotes: doctorNotes.trim(),
      isEmergencyReferral,
      submittedAt: new Date().toISOString(),
    };
    const doctorId =
      getSessionLicense() ||
      (typeof window !== "undefined" ? localStorage.getItem("whoPortalDoctorId") : null) ||
      "portal-doctor";
    try {
      await submitResponse(caseId, {
        doctor_id: doctorId,
        guidance_text: buildGuidanceText(payload),
        is_emergency_referral: isEmergencyReferral,
        compliance_acknowledged: true,
      });
    } catch {
      /* API unavailable — still persist locally for demo */
    }
    setCaseOverlay(caseId, { reportStatus: "Submitted", report: payload });
    onAfterSubmit();
    setSubmitting(false);
  };

  if (reportStatus === "Submitted" && report) {
    const diagnosis = report.diagnosis ?? "—";
    const notes = report.doctorNotes ?? "—";
    const emergency = report.isEmergencyReferral === true;
    return (
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
        <h2 className="font-heading font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <CheckCircle className="w-5 h-5 text-triage-green" />
          Medical report submitted
        </h2>
        <div className="text-sm text-gray-700 space-y-3 bg-gray-50 rounded-lg p-4 border border-gray-100">
          <p>
            <span className="font-semibold text-gray-500">Chief complaint &amp; assessment:</span>{" "}
            {report.chiefComplaint || "—"}
          </p>
          <p>
            <span className="font-semibold text-gray-500">Diagnosis:</span> {diagnosis}
          </p>
          <p>
            <span className="font-semibold text-gray-500">Notes &amp; recommendations:</span> {notes}
          </p>
          <p>
            <span className="font-semibold text-gray-500">Emergency referral:</span> {emergency ? "Yes" : "No"}
          </p>
          <p className="text-xs text-gray-400">Submitted {new Date(report.submittedAt).toLocaleString()}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
      <h2 className="font-heading font-semibold text-gray-900 mb-4">Medical report submission</h2>
      <form onSubmit={onSubmit} className="space-y-5">
        <div>
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
            Chief complaint &amp; clinical assessment
          </label>
          <textarea
            value={chiefComplaint}
            onChange={(e) => setChiefComplaint(e.target.value)}
            rows={4}
            required
            className="w-full bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/20 focus:border-who-blue resize-none"
            placeholder="Patient presentation, history relevant to this encounter, and your clinical assessment..."
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
            Doctor&apos;s diagnosis
          </label>
          <textarea
            value={diagnosis}
            onChange={(e) => setDiagnosis(e.target.value)}
            rows={2}
            required
            className="w-full bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/20 focus:border-who-blue resize-none"
            placeholder="Working or provisional diagnosis..."
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
            Doctor&apos;s notes &amp; recommendations
          </label>
          <textarea
            value={doctorNotes}
            onChange={(e) => setDoctorNotes(e.target.value)}
            rows={4}
            required
            className="w-full bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/20 focus:border-who-blue resize-none"
            placeholder="Assessment, plan, follow-up, patient instructions..."
          />
        </div>

        <label className="flex items-start gap-3 cursor-pointer rounded-lg border border-gray-200 bg-amber-50/40 px-4 py-3">
          <input
            type="checkbox"
            checked={isEmergencyReferral}
            onChange={(e) => setIsEmergencyReferral(e.target.checked)}
            className="mt-1 rounded border-gray-300 text-triage-red focus:ring-triage-red"
          />
          <span>
            <span className="flex items-center gap-2 text-sm font-semibold text-gray-900">
              <AlertTriangle className="w-4 h-4 text-triage-red shrink-0" />
              Emergency referral
            </span>
            <span className="text-xs text-gray-600 block mt-0.5">
              Check if the patient should seek immediate in-person or emergency care.
            </span>
          </span>
        </label>

        <button
          type="submit"
          disabled={submitting || !formValid}
          className="flex items-center gap-2 px-4 py-2.5 bg-who-blue text-white rounded-lg text-sm font-semibold hover:bg-who-blue-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Send className="w-4 h-4" />
          {submitting ? "Submitting..." : "Submit report"}
        </button>
      </form>
    </div>
  );
}
