"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Case } from "@/types";
import { getCase, assignDoctor, submitResponse, formatDate, timeAgo } from "@/lib/api";
import ComplianceBanner from "@/components/ComplianceBanner";
import UrgencyBadge from "@/components/UrgencyBadge";
import CountryIndicator from "@/components/CountryIndicator";
import PriorityBar from "@/components/PriorityBar";
import RedFlagBadge from "@/components/RedFlagBadge";
import KGInsightsPanel from "@/components/KGInsightsPanel";
import LoadingSpinner from "@/components/LoadingSpinner";
import {
  ArrowLeft,
  Clock,
  MapPin,
  Thermometer,
  Timer,
  FileText,
  UserPlus,
  Send,
  CheckCircle,
} from "lucide-react";

export default function CaseDetailPage({ params }: { params: { id: string } }) {
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [loading, setLoading] = useState(true);
  const [assigning, setAssigning] = useState(false);
  const [assigned, setAssigned] = useState(false);
  const [responseText, setResponseText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    getCase(params.id).then((data) => {
      setCaseData(data);
      setLoading(false);
      if (data?.status === "assigned") setAssigned(true);
    });
  }, [params.id]);

  const handleAssign = async () => {
    if (!caseData) return;
    setAssigning(true);
    await assignDoctor(caseData.caseId);
    setAssigning(false);
    setAssigned(true);
  };

  const handleSubmitResponse = async () => {
    if (!caseData || !responseText.trim()) return;
    setSubmitting(true);
    await submitResponse(caseData.caseId, responseText);
    setSubmitting(false);
    setSubmitted(true);
    setResponseText("");
  };

  if (loading) return <LoadingSpinner text="Loading case details..." />;

  if (!caseData) {
    return (
      <div className="text-center py-20">
        <p className="text-lg font-heading font-semibold text-gray-500">Case not found</p>
        <Link href="/cases" className="text-sm text-who-blue hover:underline mt-2 inline-block">
          &larr; Back to cases
        </Link>
      </div>
    );
  }

  const painColor =
    caseData.painScore >= 7
      ? "text-triage-red"
      : caseData.painScore >= 4
      ? "text-triage-yellow"
      : "text-triage-green";

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href="/cases"
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-who-blue transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Case Queue
      </Link>

      {/* Compliance Banner */}
      <ComplianceBanner />

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Main Content - 2/3 */}
        <div className="xl:col-span-2 space-y-6">
          {/* Case Header */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
            <div className="flex flex-wrap items-start justify-between gap-4 mb-5">
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <h1 className="text-2xl font-heading font-bold text-gray-900">
                    {caseData.patientAlias}
                  </h1>
                  <UrgencyBadge urgency={caseData.urgency} size="lg" />
                </div>
                <div className="flex flex-wrap items-center gap-3 text-sm text-gray-500">
                  <CountryIndicator
                    country={caseData.country}
                    tier={caseData.countryTier}
                    showTier
                  />
                  <span className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" />
                    {formatDate(caseData.submittedAt)} ({timeAgo(caseData.submittedAt)})
                  </span>
                </div>
              </div>

              {/* Assign Button */}
              <button
                onClick={handleAssign}
                disabled={assigned || assigning}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
                  assigned
                    ? "bg-triage-green/10 text-triage-green border border-triage-green/20 cursor-default"
                    : "bg-who-blue text-white hover:bg-who-blue-dark shadow-sm"
                }`}
              >
                {assigned ? (
                  <>
                    <CheckCircle className="w-4 h-4" />
                    Assigned
                  </>
                ) : assigning ? (
                  "Assigning..."
                ) : (
                  <>
                    <UserPlus className="w-4 h-4" />
                    Assign to Me
                  </>
                )}
              </button>
            </div>

            {/* Priority Score */}
            <div className="mb-5">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Priority Score
                </span>
                <span className="text-sm font-heading font-bold text-gray-900">
                  {caseData.priorityScore}/100
                </span>
              </div>
              <PriorityBar score={caseData.priorityScore} showLabel={false} />
            </div>

            {/* Case Metadata */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="flex items-center gap-1.5 mb-1">
                  <Thermometer className="w-3.5 h-3.5 text-gray-400" />
                  <span className="text-[11px] font-semibold text-gray-400 uppercase">Pain Score</span>
                </div>
                <p className={`text-xl font-heading font-bold ${painColor}`}>
                  {caseData.painScore}<span className="text-sm text-gray-400">/10</span>
                </p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="flex items-center gap-1.5 mb-1">
                  <Timer className="w-3.5 h-3.5 text-gray-400" />
                  <span className="text-[11px] font-semibold text-gray-400 uppercase">Duration</span>
                </div>
                <p className="text-lg font-heading font-bold text-gray-900">{caseData.symptomDuration}</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="flex items-center gap-1.5 mb-1">
                  <MapPin className="w-3.5 h-3.5 text-gray-400" />
                  <span className="text-[11px] font-semibold text-gray-400 uppercase">Body Area</span>
                </div>
                <p className="text-lg font-heading font-bold text-gray-900">{caseData.bodyArea}</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="flex items-center gap-1.5 mb-1">
                  <FileText className="w-3.5 h-3.5 text-gray-400" />
                  <span className="text-[11px] font-semibold text-gray-400 uppercase">Consent</span>
                </div>
                <p className="text-lg font-heading font-bold text-triage-green">
                  {caseData.consentGiven ? "Given" : "Pending"}
                </p>
              </div>
            </div>
          </div>

          {/* Symptom Summary */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
            <h2 className="font-heading font-semibold text-gray-900 mb-3">Symptom Summary</h2>
            <p className="text-sm text-gray-700 leading-relaxed bg-blue-50/50 border border-blue-100/50 rounded-lg p-4">
              {caseData.symptomSummary}
            </p>
          </div>

          {/* Red Flags */}
          {caseData.redFlagIndicators.length > 0 && (
            <div className="bg-white rounded-xl border border-red-100 shadow-sm p-6">
              <h2 className="font-heading font-semibold text-triage-red mb-3 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-triage-red animate-pulse" />
                Red Flag Indicators
              </h2>
              <RedFlagBadge flags={caseData.redFlagIndicators} />
            </div>
          )}

          {/* AI Structured Notes */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
            <h2 className="font-heading font-semibold text-gray-900 mb-3">AI Structured Notes</h2>
            <div className="text-sm text-gray-700 leading-relaxed bg-gray-50 rounded-lg p-4 border border-gray-100">
              {caseData.aiStructuredNotes}
            </div>
          </div>

          {/* Doctor Response */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
            <h2 className="font-heading font-semibold text-gray-900 mb-3">Doctor Response</h2>
            {submitted ? (
              <div className="flex items-center gap-2 text-triage-green bg-green-50 rounded-lg p-4 border border-green-100">
                <CheckCircle className="w-5 h-5" />
                <span className="text-sm font-medium">Response submitted successfully</span>
              </div>
            ) : (
              <div className="space-y-3">
                <textarea
                  value={responseText}
                  onChange={(e) => setResponseText(e.target.value)}
                  placeholder="Enter your clinical assessment and recommendations..."
                  rows={4}
                  className="w-full bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/20 focus:border-who-blue resize-none"
                />
                <button
                  onClick={handleSubmitResponse}
                  disabled={submitting || !responseText.trim()}
                  className="flex items-center gap-2 px-4 py-2 bg-who-blue text-white rounded-lg text-sm font-semibold hover:bg-who-blue-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Send className="w-4 h-4" />
                  {submitting ? "Submitting..." : "Submit Response"}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* KG Insights Panel - 1/3 */}
        <div className="xl:col-span-1">
          <div className="sticky top-6">
            <KGInsightsPanel caseData={caseData} />
          </div>
        </div>
      </div>
    </div>
  );
}
