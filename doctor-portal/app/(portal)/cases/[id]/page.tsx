"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Case } from "@/types";
import { getCase, assignDoctor, formatDate, timeAgo } from "@/lib/api";
import {
  getCaseOverlay,
  setCaseOverlay,
  subscribeOverlays,
  displayUrgency,
  type ClinicalUrgency,
} from "@/lib/case-overlays";
import ComplianceBanner from "@/components/ComplianceBanner";
import ClinicalUrgencyBadge from "@/components/ClinicalUrgencyBadge";
import CountryIndicator from "@/components/CountryIndicator";
import PriorityBar from "@/components/PriorityBar";
import RedFlagBadge from "@/components/RedFlagBadge";
import KGInsightsPanel from "@/components/KGInsightsPanel";
import LoadingSpinner from "@/components/LoadingSpinner";
import MedicalReportSection from "@/components/MedicalReportSection";
import { getSessionLicense } from "@/lib/auth-storage";
import {
  ArrowLeft,
  Clock,
  MapPin,
  Thermometer,
  Timer,
  FileText,
  UserPlus,
  CheckCircle,
  AlertCircle,
  User,
} from "lucide-react";

const URGENCY_OPTIONS: ClinicalUrgency[] = ["Low", "Medium", "High", "Critical"];

export default function CaseDetailPage() {
  const params = useParams();
  const caseIdParam = params?.id;
  const caseId =
    typeof caseIdParam === "string" ? caseIdParam : Array.isArray(caseIdParam) ? caseIdParam[0] ?? "" : "";

  const [caseData, setCaseData] = useState<Case | null>(null);
  const [loading, setLoading] = useState(true);
  const [assigning, setAssigning] = useState(false);
  const [assigned, setAssigned] = useState(false);
  const [assignError, setAssignError] = useState<string | null>(null);
  const [overlayTick, setOverlayTick] = useState(0);
  const kgSpecialtyRef = useRef<string>("General Medicine");

  const refreshOverlay = useCallback(() => setOverlayTick((t) => t + 1), []);

  const overlay = useMemo(() => {
    if (!caseData) return { reportStatus: "Pending" as const };
    return getCaseOverlay(caseData.caseId);
  }, [caseData, overlayTick]);

  const clinicalUrgency = caseData ? displayUrgency(caseData, overlay) : "Low";

  useEffect(() => {
    if (!caseId) {
      setCaseData(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    getCase(caseId)
      .then((data) => {
        if (cancelled) return;
        setCaseData(data);
        if (data?.status === "assigned" || data?.status === "responded" || data?.status === "in_review" || data?.status === "closed")
          setAssigned(true);
      })
      .catch(() => {
        if (!cancelled) setCaseData(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  useEffect(() => {
    return subscribeOverlays(refreshOverlay);
  }, [refreshOverlay]);

  const setClinicalUrgency = (u: ClinicalUrgency) => {
    if (!caseData) return;
    setCaseOverlay(caseData.caseId, { clinicalUrgency: u });
    refreshOverlay();
  };

  const handleAssign = async () => {
    if (!caseData) return;
    setAssigning(true);
    setAssignError(null);
    try {
      const docId = getSessionLicense() || "portal-doctor";
      await assignDoctor(caseData.caseId, docId);
      setAssigned(true);
    } catch (err) {
      setAssignError(err instanceof Error ? err.message : "Failed to assign doctor");
    } finally {
      setAssigning(false);
    }
  };

  const handleKGSpecialty = useCallback((specialty: string) => {
    kgSpecialtyRef.current = specialty;
  }, []);

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

  const diagnosisLabel =
    caseData.clinicalDiagnosis?.trim() || caseData.symptomSummary?.slice(0, 120) || "Pending documentation";

  return (
    <div className="space-y-6">
      <Link
        href="/cases"
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-who-blue transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to patient queue
      </Link>

      <ComplianceBanner />

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 space-y-6">
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
            <div className="flex flex-wrap items-start justify-between gap-4 mb-5">
              <div className="space-y-3">
                <div className="flex items-center gap-3 flex-wrap">
                  <h1 className="text-2xl font-heading font-bold text-gray-900">{caseData.patientAlias}</h1>
                  <ClinicalUrgencyBadge urgency={clinicalUrgency} size="lg" />
                  <span
                    className={`text-xs font-bold px-2.5 py-1 rounded-full border ${
                      overlay.reportStatus === "Submitted"
                        ? "bg-green-50 text-green-700 border-green-200"
                        : "bg-amber-50 text-amber-900 border-amber-200"
                    }`}
                  >
                    Status: {overlay.reportStatus}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-sm text-gray-600">
                  <span className="font-semibold text-gray-500">Clinical urgency</span>
                  <select
                    value={clinicalUrgency}
                    onChange={(e) => setClinicalUrgency(e.target.value as ClinicalUrgency)}
                    className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-who-blue/20 focus:border-who-blue"
                  >
                    {URGENCY_OPTIONS.map((u) => (
                      <option key={u} value={u}>
                        {u}
                      </option>
                    ))}
                  </select>
                  <span className="text-gray-400">·</span>
                  <span className="text-xs text-gray-500">
                    Report {overlay.reportStatus === "Pending" ? "awaiting submission" : "on file"}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-3 text-sm text-gray-500">
                  <CountryIndicator country={caseData.country} tier={caseData.countryTier} showTier />
                  <span className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" />
                    {formatDate(caseData.submittedAt)} ({timeAgo(caseData.submittedAt)})
                  </span>
                </div>
              </div>

              <div className="flex flex-col items-end gap-1">
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
                {assignError && (
                  <span className="flex items-center gap-1 text-xs text-triage-red">
                    <AlertCircle className="w-3 h-3" />
                    {assignError}
                  </span>
                )}
              </div>
            </div>

            <div className="rounded-xl border border-who-blue/15 bg-[#F0F7FC] p-4 mb-5">
              <h2 className="text-xs font-bold text-who-blue uppercase tracking-wide mb-3 flex items-center gap-2">
                <User className="w-4 h-4" />
                Patient information
              </h2>
              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                <div>
                  <dt className="text-gray-500 text-xs uppercase font-semibold">Name</dt>
                  <dd className="font-medium text-gray-900">{caseData.patientAlias}</dd>
                </div>
                <div>
                  <dt className="text-gray-500 text-xs uppercase font-semibold">Age</dt>
                  <dd className="font-medium text-gray-900">{caseData.patientAge != null ? `${caseData.patientAge}` : "Not recorded"}</dd>
                </div>
                <div>
                  <dt className="text-gray-500 text-xs uppercase font-semibold">Gender</dt>
                  <dd className="font-medium text-gray-900">{caseData.patientGender?.trim() || "Not recorded"}</dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="text-gray-500 text-xs uppercase font-semibold">Diagnosis / presentation</dt>
                  <dd className="font-medium text-gray-900 leading-relaxed">{diagnosisLabel}</dd>
                </div>
              </dl>
            </div>

            <div className="mb-5">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Priority Score</span>
                <span className="text-sm font-heading font-bold text-gray-900">{caseData.priorityScore}/100</span>
              </div>
              <PriorityBar score={caseData.priorityScore} showLabel={false} />
            </div>

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
                <p className="text-lg font-heading font-bold text-triage-green">{caseData.consentGiven ? "Given" : "Pending"}</p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
            <h2 className="font-heading font-semibold text-gray-900 mb-3">Symptom Summary</h2>
            <p className="text-sm text-gray-700 leading-relaxed bg-blue-50/50 border border-blue-100/50 rounded-lg p-4">{caseData.symptomSummary}</p>
          </div>

          {(caseData.redFlagIndicators?.length ?? 0) > 0 && (
            <div className="bg-white rounded-xl border border-red-100 shadow-sm p-6">
              <h2 className="font-heading font-semibold text-triage-red mb-3 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-triage-red animate-pulse" />
                Red Flag Indicators
              </h2>
              <RedFlagBadge flags={caseData.redFlagIndicators ?? []} />
            </div>
          )}

          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
            <h2 className="font-heading font-semibold text-gray-900 mb-3">AI Structured Notes</h2>
            <div className="text-sm text-gray-700 leading-relaxed bg-gray-50 rounded-lg p-4 border border-gray-100">
              {caseData.aiStructuredNotes ?? "—"}
            </div>
          </div>

          <MedicalReportSection
            key={`${caseData.caseId}-${overlay.reportStatus}`}
            caseId={caseData.caseId}
            reportStatus={overlay.reportStatus}
            report={overlay.report}
            onAfterSubmit={refreshOverlay}
          />
        </div>

        <div className="xl:col-span-1">
          <div className="sticky top-6">
            <KGInsightsPanel caseData={caseData} kgInsights={caseData.kgInsights} onSpecialtyResolved={handleKGSpecialty} />
          </div>
        </div>
      </div>
    </div>
  );
}
