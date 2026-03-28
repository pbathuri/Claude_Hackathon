"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Case } from "@/types";
import { getCases, timeAgo } from "@/lib/api";
import StatsCard from "@/components/StatsCard";
import PieChart from "@/components/PieChart";
import BarChart from "@/components/BarChart";
import UrgencyBadge from "@/components/UrgencyBadge";
import CountryIndicator from "@/components/CountryIndicator";
import PriorityBar from "@/components/PriorityBar";
import LoadingSpinner from "@/components/LoadingSpinner";
import { FileText, AlertTriangle, CalendarClock, Gauge, UserCheck, Clock } from "lucide-react";

const mockDoctors = [
  { name: "Dr. Amara", status: "online" as const, cases: 3 },
  { name: "Dr. Chen", status: "busy" as const, cases: 5 },
  { name: "Dr. Müller", status: "offline" as const, cases: 0 },
  { name: "Dr. Okafor", status: "online" as const, cases: 2 },
];

function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

export default function DashboardPage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCases().then((data) => {
      setCases(data);
      setLoading(false);
    });
  }, []);

  if (loading) return <LoadingSpinner text="Loading dashboard..." />;

  const highCount = cases.filter((c) => c.urgency === "High").length;
  const medCount = cases.filter((c) => c.urgency === "Medium").length;
  const lowCount = cases.filter((c) => c.urgency === "Low").length;
  const avgPriority = cases.length
    ? Math.round(cases.reduce((s, c) => s + c.priorityScore, 0) / cases.length)
    : 0;
  const todayCount = cases.filter((c) => {
    const d = new Date(c.submittedAt);
    const now = new Date();
    return d.toDateString() === now.toDateString();
  }).length;

  const countryCounts = cases.reduce<Record<string, number>>((acc, c) => {
    acc[c.country] = (acc[c.country] || 0) + 1;
    return acc;
  }, {});

  const recentCases = [...cases]
    .sort((a, b) => new Date(b.submittedAt).getTime() - new Date(a.submittedAt).getTime())
    .slice(0, 5);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-heading font-bold text-gray-900">
            {getGreeting()}, Doctor
          </h1>
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

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="Total Cases"
          value={cases.length}
          subtitle={`${cases.filter((c) => c.status === "pending").length} pending review`}
          icon={FileText}
        />
        <StatsCard
          title="High Urgency"
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

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Urgency Distribution */}
        <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-sm">
          <h2 className="font-heading font-semibold text-gray-900 mb-5">
            Triage Distribution
          </h2>
          <div className="flex justify-center">
            <PieChart
              segments={[
                { label: "Red (High)", value: highCount, color: "#E63946" },
                { label: "Yellow (Med)", value: medCount, color: "#F4A261" },
                { label: "Green (Low)", value: lowCount, color: "#2A9D8F" },
              ]}
            />
          </div>
        </div>

        {/* Cases by Country */}
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

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Doctor Status */}
        <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-sm">
          <h2 className="font-heading font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <UserCheck className="w-5 h-5 text-who-blue" />
            Doctor Status
          </h2>
          <div className="space-y-3">
            {mockDoctors.map((doc) => (
              <div key={doc.name} className="flex items-center justify-between py-2">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full bg-gray-100 flex items-center justify-center text-xs font-bold text-gray-600">
                    {doc.name.split(" ").map((n) => n[0]).join("")}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-800">{doc.name}</p>
                    <p className="text-[11px] text-gray-400">
                      {doc.cases} active case{doc.cases !== 1 ? "s" : ""}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      doc.status === "online"
                        ? "bg-triage-green animate-pulse"
                        : doc.status === "busy"
                        ? "bg-triage-yellow"
                        : "bg-gray-300"
                    }`}
                  />
                  <span className="text-xs text-gray-500 capitalize">{doc.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Cases */}
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
                    c.urgency === "High"
                      ? "bg-triage-red"
                      : c.urgency === "Medium"
                      ? "bg-triage-yellow"
                      : "bg-triage-green"
                  }`}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-sm font-semibold text-gray-800 group-hover:text-who-blue transition-colors">
                      {c.patientAlias}
                    </span>
                    <CountryIndicator country={c.country} />
                  </div>
                  <p className="text-xs text-gray-500 truncate">{c.symptomSummary}</p>
                </div>
                <div className="text-right shrink-0">
                  <UrgencyBadge urgency={c.urgency} size="sm" />
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
