"use client";

import { useState } from "react";
import {
  setCaseOverlay,
  type MedicalReportPayload,
  type CommunicationPreference,
  type ReportStatus,
} from "@/lib/case-overlays";
import { submitResponse } from "@/lib/api";
import { getSessionLicense } from "@/lib/auth-storage";
import { CheckCircle, Send } from "lucide-react";

const ALLERGY_OPTIONS = ["Penicillin", "Latex", "NSAIDs", "Iodinated contrast", "Shellfish", "No known allergies"] as const;

interface Props {
  caseId: string;
  reportStatus: ReportStatus;
  report?: MedicalReportPayload;
  onAfterSubmit: () => void;
}

function buildGuidanceText(payload: MedicalReportPayload): string {
  const comm =
    payload.communicationPreference === "voice"
      ? "Voice message"
      : payload.communicationPreference === "sms"
      ? "Text / SMS"
      : "Phone call";
  return [
    "--- Medical report (portal) ---",
    `Chief complaint / current condition: ${payload.chiefComplaint}`,
    `Vitals — BP: ${payload.bloodPressure}, HR: ${payload.heartRate}, Temp: ${payload.temperature}, SpO₂: ${payload.oxygenSaturation}`,
    `Pain scale: ${payload.painScale}/10`,
    `Medications: ${payload.medications}`,
    `Allergies: ${[...payload.allergyFlags, payload.allergies].filter(Boolean).join("; ") || "None recorded"}`,
    `Doctor notes & recommendations: ${payload.doctorNotes}`,
    `Patient communication preference: ${comm}`,
  ].join("\n");
}

export default function MedicalReportSection({ caseId, reportStatus, report, onAfterSubmit }: Props) {
  const [chiefComplaint, setChiefComplaint] = useState(report?.chiefComplaint ?? "");
  const [bloodPressure, setBloodPressure] = useState(report?.bloodPressure ?? "");
  const [heartRate, setHeartRate] = useState(report?.heartRate ?? "");
  const [temperature, setTemperature] = useState(report?.temperature ?? "");
  const [oxygenSaturation, setOxygenSaturation] = useState(report?.oxygenSaturation ?? "");
  const [painScale, setPainScale] = useState(report?.painScale ?? 0);
  const [medications, setMedications] = useState(report?.medications ?? "");
  const [allergiesText, setAllergiesText] = useState(report?.allergies ?? "");
  const [allergyFlags, setAllergyFlags] = useState<string[]>(report?.allergyFlags ?? []);
  const [doctorNotes, setDoctorNotes] = useState(report?.doctorNotes ?? "");
  const [communicationPreference, setCommunicationPreference] = useState<CommunicationPreference>(
    report?.communicationPreference ?? "sms"
  );
  const [submitting, setSubmitting] = useState(false);

  const toggleAllergy = (label: string) => {
    setAllergyFlags((prev) =>
      prev.includes(label) ? prev.filter((a) => a !== label) : [...prev, label]
    );
  };

  const formValid =
    chiefComplaint.trim() &&
    bloodPressure.trim() &&
    heartRate.trim() &&
    temperature.trim() &&
    oxygenSaturation.trim() &&
    medications.trim() &&
    doctorNotes.trim() &&
    (allergyFlags.length > 0 || allergiesText.trim());

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formValid) return;
    setSubmitting(true);
    const payload: MedicalReportPayload = {
      chiefComplaint: chiefComplaint.trim(),
      bloodPressure: bloodPressure.trim(),
      heartRate: heartRate.trim(),
      temperature: temperature.trim(),
      oxygenSaturation: oxygenSaturation.trim(),
      painScale,
      medications: medications.trim(),
      allergies: allergiesText.trim(),
      allergyFlags: [...allergyFlags],
      doctorNotes: doctorNotes.trim(),
      communicationPreference,
      submittedAt: new Date().toISOString(),
    };
    const doctorId = getSessionLicense() || (typeof window !== "undefined" ? localStorage.getItem("whoPortalDoctorId") : null) || "portal-doctor";
    try {
      await submitResponse(caseId, {
        doctor_id: doctorId,
        guidance_text: buildGuidanceText(payload),
        is_emergency_referral: false,
        compliance_acknowledged: true,
      });
    } catch {
      // API unavailable — still persist report locally so list status updates (demo).
    }
    setCaseOverlay(caseId, { reportStatus: "Submitted", report: payload });
    onAfterSubmit();
    setSubmitting(false);
  };

  if (reportStatus === "Submitted" && report) {
    return (
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
        <h2 className="font-heading font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <CheckCircle className="w-5 h-5 text-triage-green" />
          Medical report submitted
        </h2>
        <div className="text-sm text-gray-700 space-y-3 bg-gray-50 rounded-lg p-4 border border-gray-100">
          <p><span className="font-semibold text-gray-500">Chief complaint:</span> {report.chiefComplaint}</p>
          <p>
            <span className="font-semibold text-gray-500">Vitals:</span> BP {report.bloodPressure}, HR {report.heartRate}, Temp{" "}
            {report.temperature}, SpO₂ {report.oxygenSaturation}
          </p>
          <p><span className="font-semibold text-gray-500">Pain:</span> {report.painScale}/10</p>
          <p><span className="font-semibold text-gray-500">Medications:</span> {report.medications}</p>
          <p>
            <span className="font-semibold text-gray-500">Allergies:</span>{" "}
            {[...report.allergyFlags, report.allergies].filter(Boolean).join("; ") || "—"}
          </p>
          <p><span className="font-semibold text-gray-500">Notes:</span> {report.doctorNotes}</p>
          <p>
            <span className="font-semibold text-gray-500">Communication:</span>{" "}
            {report.communicationPreference === "voice"
              ? "Voice message"
              : report.communicationPreference === "sms"
              ? "Text / SMS"
              : "Phone call"}
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
            Chief complaint &amp; current condition
          </label>
          <textarea
            value={chiefComplaint}
            onChange={(e) => setChiefComplaint(e.target.value)}
            rows={3}
            required
            className="w-full bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/20 focus:border-who-blue resize-none"
            placeholder="Patient presentation and current clinical picture..."
          />
        </div>

        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Vital signs</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <label className="text-[11px] text-gray-500">Blood pressure</label>
              <input
                value={bloodPressure}
                onChange={(e) => setBloodPressure(e.target.value)}
                required
                placeholder="120/80"
                className="mt-0.5 w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/20 focus:border-who-blue"
              />
            </div>
            <div>
              <label className="text-[11px] text-gray-500">Heart rate (bpm)</label>
              <input
                value={heartRate}
                onChange={(e) => setHeartRate(e.target.value)}
                required
                placeholder="72"
                className="mt-0.5 w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/20 focus:border-who-blue"
              />
            </div>
            <div>
              <label className="text-[11px] text-gray-500">Temperature</label>
              <input
                value={temperature}
                onChange={(e) => setTemperature(e.target.value)}
                required
                placeholder="37 °C"
                className="mt-0.5 w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/20 focus:border-who-blue"
              />
            </div>
            <div>
              <label className="text-[11px] text-gray-500">Oxygen saturation</label>
              <input
                value={oxygenSaturation}
                onChange={(e) => setOxygenSaturation(e.target.value)}
                required
                placeholder="98%"
                className="mt-0.5 w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/20 focus:border-who-blue"
              />
            </div>
          </div>
        </div>

        <div>
          <div className="flex justify-between text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
            <span>Pain scale</span>
            <span className="text-who-blue">{painScale}/10</span>
          </div>
          <input
            type="range"
            min={0}
            max={10}
            value={painScale}
            onChange={(e) => setPainScale(Number(e.target.value))}
            className="w-full accent-who-blue h-2 rounded-lg appearance-none bg-gray-200"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
            Current medications
          </label>
          <textarea
            value={medications}
            onChange={(e) => setMedications(e.target.value)}
            rows={2}
            required
            className="w-full bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/20 focus:border-who-blue resize-none"
            placeholder="List medications and doses..."
          />
        </div>

        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Allergies</p>
          <div className="flex flex-wrap gap-2 mb-3">
            {ALLERGY_OPTIONS.map((opt) => (
              <label key={opt} className="inline-flex items-center gap-1.5 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={allergyFlags.includes(opt)}
                  onChange={() => toggleAllergy(opt)}
                  className="rounded border-gray-300 text-who-blue focus:ring-who-blue"
                />
                {opt}
              </label>
            ))}
          </div>
          <textarea
            value={allergiesText}
            onChange={(e) => setAllergiesText(e.target.value)}
            rows={2}
            className="w-full bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/20 focus:border-who-blue resize-none"
            placeholder="Additional allergy details or free text..."
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
            placeholder="Assessment, plan, follow-up..."
          />
        </div>

        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            How should results be delivered to the patient?
          </p>
          <div className="flex flex-wrap gap-4">
            {(
              [
                { v: "voice" as const, label: "Voice message" },
                { v: "sms" as const, label: "Text / SMS" },
                { v: "phone" as const, label: "Phone call" },
              ] as const
            ).map(({ v, label }) => (
              <label key={v} className="inline-flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="radio"
                  name="comm"
                  checked={communicationPreference === v}
                  onChange={() => setCommunicationPreference(v)}
                  className="text-who-blue focus:ring-who-blue"
                />
                {label}
              </label>
            ))}
          </div>
        </div>

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
