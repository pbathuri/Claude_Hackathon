"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import { Case, Doctor } from "@/types";
import { getCases, getDoctors, timeAgo, subscribeCasesStream } from "@/lib/api";
import { mergeCasesWithOverlays, subscribeOverlays, type CaseWithOverlay } from "@/lib/case-overlays";
import StatsCard from "@/components/StatsCard";
import PieChart from "@/components/PieChart";
import BarChart from "@/components/BarChart";
import ClinicalUrgencyBadge from "@/components/ClinicalUrgencyBadge";
import CountryIndicator from "@/components/CountryIndicator";
import PriorityBar from "@/components/PriorityBar";
import LoadingSpinner from "@/components/LoadingSpinner";
import { FileText, AlertTriangle, CalendarClock, Gauge, UserCheck, Clock } from "lucide-react";

const POLL_FALLBACK_MS = 60_000;

function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

export default function DashboardPage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [loading, setLoading] = useState(true);
  const [overlayTick, setOverlayTick] = useState(0);

  const merged = useMemo(() => mergeCasesWithOverlays(cases), [cases, overlayTick]);

  const fetchData = useCallback(async () => {
    const [casesData, doctorsData] = await Promise.all([getCases(), getDoctors()]);
    setCases(casesData);
    setDoctors(doctorsData);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, POLL_FALLBACK_MS);
    const stopStream = subscribeCasesStream(() => {
      fetchData();
    });
    const stopOverlays = subscribeOverlays(() => setOverlayTick((t) => t + 1));
    return () => {
      clearInterval(interval);
      stopStream();
      stopOverlays();
    };
  }, [fetchData]);

  if (loading) return <LoadingSpinner text="Loading dashboard..." />;

  const highCount = merged.filter((c) => c.displayUrgency === "High" || c.displayUrgency === "Critical").length;
  const medCount = merged.filter((c) => c.displayUrgency === "Medium").length;
  const lowCount = merged.filter((c) => c.displayUrgency === "Low").length;
  const avgPriority = merged.length
    ? Math.round(merged.reduce((s, c) => s + c.priorityScore, 0) / merged.length)
    : 0;
  const todayCount = merged.filter((c) => {
    const d = new Date(c.submittedAt);
    const now = new Date();
    return d.toDateString() === now.toDateString();
  }).length;

  const countryCounts = merged.reduce<Record<string, number>>((acc, c) => {
    acc[c.country] = (acc[c.country] || 0) + 1;
    return acc;
  }, {});

  const recentCases: CaseWithOverlay[] = [...merged]
    .sort((a, b) => new Date(b.submittedAt).getTime() - new Date(a.submittedAt).getTime())
    .slice(0, 5);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-heading font-bold text-gray-900">
              {getGreeting()}, Doctor
            </h1>
            <span className="flex items-center gap-1.5 bg-green-50 border border-green-200 rounded-full px-2.5 py-0.5">
              <span className="w-2 h-2 rounded-full bg-triage-green animate-pulse" />
              <span className="text-[11px] font-bold text-triage-green uppercase tracking-wide">Live</span>
            </span>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            {new Date().toLocaleDateString("en-US", {
              weekday: "long",
              month: "long",
              day: "numeric",
              year: "numeric",
            })}
          </p>
        </div>
        <Link
          href="/cases"
          className="text-sm font-medium text-who-blue hover:text-who-blue-dark transition-colors"
        >
          View all cases &rarr;
        </Link>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="Total Cases"
          value={merged.length}
          subtitle={`${merged.filter((c) => c.status === "pending_review" || c.status === "intake_complete").length} pending review`}
          icon={FileText}
        />
        <StatsCard
          title="High / Critical"
          value={highCount}
          subtitle="Requires immediate attention"
          icon={AlertTriangle}
          iconBg="bg-triage-red/10"
          iconColor="text-triage-red"
        />
        <StatsCard
          title="Today's Cases"
          value={todayCount}
          subtitle="Submitted in last 24h"
          icon={CalendarClock}
          iconBg="bg-triage-green/10"
          iconColor="text-triage-green"
        />
        <StatsCard
          title="Avg Priority"
          value={avgPriority}
          subtitle="Across all active cases"
          icon={Gauge}
          iconBg="bg-triage-yellow/10"
          iconColor="text-triage-yellow"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-sm">
          <h2 className="font-heading font-semibold text-gray-900 mb-5">
            Triage Distribution
          </h2>
          <div className="flex justify-center">
            <PieChart
              segments={[
                { label: "High / Critical", value: highCount, color: "#E63946" },
                { label: "Medium", value: medCount, color: "#F4A261" },
                { label: "Low", value: lowCount, color: "#2A9D8F" },
              ]}
            />
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-sm">
          <h2 className="font-heading font-semibold text-gray-900 mb-5">
            Cases by Country
          </h2>
          <BarChart
            bars={Object.entries(countryCounts)
              .sort(([, a], [, b]) => b - a)
              .map(([country, count]) => ({
                label: country,
                value: count,
              }))}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-sm">
          <h2 className="font-heading font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <UserCheck className="w-5 h-5 text-who-blue" />
            Doctor Status
          </h2>
          {doctors.length === 0 ? (
            <div className="text-center py-8 text-gray-400">
              <UserCheck className="w-8 h-8 mx-auto mb-2 opacity-40" />
              <p className="text-sm font-medium">No doctors online</p>
              <p className="text-xs mt-1">Doctors will appear here once registered</p>
            </div>
          ) : (
            <div className="space-y-3">
              {doctors.map((doc) => (
                <div key={doc.id} className="flex items-center justify-between py-2">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-gray-100 flex items-center justify-center text-xs font-bold text-gray-600">
                      {doc.full_name.split(" ").map((n) => n[0]).join("").slice(0, 2)}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-800">{doc.full_name}</p>
                      <p className="text-[11px] text-gray-400">
                        {doc.specialization} &middot; {doc.country_code}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        doc.availability
                          ? "bg-triage-green animate-pulse"
                          : "bg-gray-300"
                      }`}
                    />
                    <span className="text-xs text-gray-500">
                      {doc.availability === "online" ? "Available" : "Offline"}
                    </span>
                    {doc.verified && (
                      <span className="text-[10px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded-full font-semibold ml-1">
                        Verified
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-sm">
          <h2 className="font-heading font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Clock className="w-5 h-5 text-who-blue" />
            Recent Cases
          </h2>
          <div className="space-y-3">
            {recentCases.map((c) => (
              <Link
                key={c.caseId}
                href={`/cases/${c.caseId}`}
                className="flex items-center gap-3 p-2.5 -mx-2.5 rounded-lg hover:bg-gray-50 transition-colors group"
              >
                <div
                  className={`w-1 h-10 rounded-full shrink-0 ${
                    c.displayUrgency === "Critical"
                      ? "bg-triage-critical"
                      : c.displayUrgency === "High"
                      ? "bg-triage-red"
                      : c.displayUrgency === "Medium"
                      ? "bg-triage-yellow"
                      : "bg-triage-green"
                  }`}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                    <span className="text-sm font-semibold text-gray-800 group-hover:text-who-blue transition-colors">
                      {c.patientAlias}
                    </span>
                    <CountryIndicator country={c.country} />
                    <ClinicalUrgencyBadge urgency={c.displayUrgency} size="sm" />
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                        c.reportStatus === "Submitted"
                          ? "bg-green-50 text-green-700 border border-green-100"
                          : "bg-amber-50 text-amber-800 border border-amber-100"
                      }`}
                    >
                      Report: {c.reportStatus}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 truncate">{c.symptomSummary}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-[10px] text-gray-400 mt-1">{timeAgo(c.submittedAt)}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
