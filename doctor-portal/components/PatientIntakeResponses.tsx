"use client";

import type { Case } from "@/types";

function deliveryLabel(pref: string | undefined): string {
  const p = (pref || "").toLowerCase();
  if (p === "voice_message") return "Voice message";
  if (p === "sms") return "Text / SMS";
  if (p === "phone_call") return "Phone call";
  return pref?.replace(/_/g, " ") || "";
}

function Row({ label, value }: { label: string; value: string }) {
  const empty = !value?.trim();
  return (
    <div className="flex flex-col sm:flex-row sm:items-start gap-0.5 sm:gap-4 py-2.5 border-b border-gray-100 last:border-0">
      <dt className="text-xs font-semibold text-gray-500 uppercase tracking-wide sm:w-44 shrink-0">{label}</dt>
      <dd className={`text-sm flex-1 ${empty ? "text-gray-400 italic" : "text-gray-900"}`}>
        {empty ? "Not provided" : value}
      </dd>
    </div>
  );
}

export default function PatientIntakeResponses({ caseData }: { caseData: Case }) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6 mb-6">
      <h2 className="font-heading font-semibold text-gray-900 mb-4">Patient intake responses</h2>
      <p className="text-xs text-gray-500 mb-4">
        Read-only answers from the Twilio phone intake. These fields cannot be edited here.
      </p>
      <dl className="divide-y divide-gray-100 rounded-lg border border-gray-100 bg-gray-50/50 px-4">
        <Row label="Patient name" value={caseData.patientName ?? ""} />
        <Row label="Gender" value={caseData.patientGender ?? ""} />
        <Row label="Confirmed phone" value={caseData.patientPhone ?? ""} />
        <Row label="Result delivery preference" value={deliveryLabel(caseData.deliveryPreference)} />
        <Row label="Symptom duration" value={caseData.symptomDuration ?? ""} />
        <Row
          label="Allergies"
          value={(caseData.allergies ?? []).filter(Boolean).join(", ")}
        />
        <Row
          label="Current medications"
          value={(caseData.currentMedications ?? []).filter(Boolean).join(", ")}
        />
        <Row label="Body area affected" value={caseData.bodyArea ?? ""} />
        <Row label="Pain score" value={caseData.painScore != null ? `${caseData.painScore}/10` : ""} />
        <Row label="Symptom summary" value={caseData.symptomSummary ?? ""} />
      </dl>
    </div>
  );
}
