"use client";

import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import Link from "next/link";
import { Case } from "@/types";
import { loadPatientCases, timeAgo, subscribeCasesStream, getApiBase } from "@/lib/api";
import { mergeCasesWithOverlays, subscribeOverlays, type CaseWithOverlay } from "@/lib/case-overlays";
import ClinicalUrgencyBadge from "@/components/ClinicalUrgencyBadge";
import CountryIndicator from "@/components/CountryIndicator";
import PriorityBar from "@/components/PriorityBar";
import RedFlagBadge from "@/components/RedFlagBadge";
import LoadingSpinner from "@/components/LoadingSpinner";
import { Search, SlidersHorizontal, ArrowUpDown, ChevronRight, Bell } from "lucide-react";

const POLL_FALLBACK_MS = 15_000;

type SortKey = "priority" | "submitted" | "pain";
type SortDir = "asc" | "desc";

function stripeClass(u: CaseWithOverlay["displayUrgency"]) {
  if (u === "Critical") return "bg-triage-critical";
  if (u === "High") return "bg-triage-red";
  if (u === "Medium") return "bg-triage-yellow";
  return "bg-triage-green";
}

function playNotificationSound() {
  try {
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.setValueAtTime(1100, ctx.currentTime + 0.1);
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.3);
  } catch {
    // Web Audio not available
  }
}

export default function CasesPage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [urgencyFilter, setUrgencyFilter] = useState("");
  const [countryFilter, setCountryFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [reportStatusFilter, setReportStatusFilter] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("priority");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [secondsAgo, setSecondsAgo] = useState(0);
  const [toast, setToast] = useState<string | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [overlayTick, setOverlayTick] = useState(0);
  const prevCountRef = useRef<number | null>(null);

  const merged = useMemo(() => mergeCasesWithOverlays(cases), [cases, overlayTick]);

  const fetchCases = useCallback(async () => {
    const { cases: data, error } = await loadPatientCases();
    setFetchError(error);
    if (error) {
      setLoading(false);
      return;
    }
    if (prevCountRef.current !== null && data.length > prevCountRef.current) {
      playNotificationSound();
      setToast(`${data.length - prevCountRef.current} new case(s) received`);
      setTimeout(() => setToast(null), 3000);
    }
    prevCountRef.current = data.length;
    setCases(data);
    setLastUpdated(new Date());
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchCases();
    const dataInterval = setInterval(fetchCases, POLL_FALLBACK_MS);
    const stopStream = subscribeCasesStream(() => {
      fetchCases();
    });
    const stopOverlays = subscribeOverlays(() => setOverlayTick((t) => t + 1));
    const tickInterval = setInterval(() => {
      setSecondsAgo((prev) => prev + 1);
    }, 1000);
    return () => {
      clearInterval(dataInterval);
      clearInterval(tickInterval);
      stopStream();
      stopOverlays();
    };
  }, [fetchCases]);

  useEffect(() => {
    setSecondsAgo(0);
  }, [lastUpdated]);

  const countries = useMemo(
    () => [...new Set(cases.map((c) => c.country))].sort(),
    [cases]
  );

  const filtered = useMemo(() => {
    let result = [...merged];

    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (c) =>
          c.patientAlias.toLowerCase().includes(q) ||
          c.symptomSummary.toLowerCase().includes(q) ||
          c.bodyArea.toLowerCase().includes(q)
      );
    }
    if (urgencyFilter) result = result.filter((c) => c.displayUrgency === urgencyFilter);
    if (countryFilter) result = result.filter((c) => c.country === countryFilter);
    if (statusFilter) result = result.filter((c) => c.status === statusFilter);
    if (reportStatusFilter) result = result.filter((c) => c.reportStatus === reportStatusFilter);

    result.sort((a, b) => {
      let diff = 0;
      switch (sortKey) {
        case "priority":
          diff = a.priorityScore - b.priorityScore;
          break;
        case "submitted": {
          const ta = a.submittedAt ? new Date(a.submittedAt).getTime() : 0;
          const tb = b.submittedAt ? new Date(b.submittedAt).getTime() : 0;
          diff = ta - tb;
          break;
        }
        case "pain":
          diff = a.painScore - b.painScore;
          break;
      }
      return sortDir === "desc" ? -diff : diff;
    });

    return result;
  }, [merged, search, urgencyFilter, countryFilter, statusFilter, reportStatusFilter, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  if (loading) return <LoadingSpinner text="Loading case queue..." />;

  return (
    <div className="space-y-6">
      {fetchError && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
          <p className="font-semibold">Could not sync with the API</p>
          <p className="mt-1 text-red-800/90">{fetchError}</p>
          <p className="mt-2 text-xs text-red-700/80">
            Check <code className="bg-red-100 px-1 rounded">NEXT_PUBLIC_API_URL</code> on Vercel (must match your Render API, e.g.{" "}
            <code className="bg-red-100 px-1 rounded">https://your-api.onrender.com</code>) and CORS. API base:{" "}
            <code className="bg-red-100 px-1 rounded">{getApiBase()}</code>
          </p>
          <button
            type="button"
            onClick={() => {
              setLoading(true);
              fetchCases();
            }}
            className="mt-3 text-xs font-semibold text-red-900 underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}
      {toast && (
        <div className="fixed top-4 right-4 z-50 animate-in slide-in-from-top-2 flex items-center gap-2 bg-who-blue text-white text-sm font-semibold px-4 py-2.5 rounded-lg shadow-lg">
          <Bell className="w-4 h-4" />
          {toast}
        </div>
      )}

      <div>
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-heading font-bold text-gray-900">Patient queue</h1>
          <span className="text-xs text-gray-400">
            Last updated {secondsAgo}s ago
          </span>
        </div>
        <p className="text-sm text-gray-500 mt-1">
          {merged.length} patients &middot; {merged.filter((c) => c.status === "pending_review" || c.status === "intake_complete").length} pending review
        </p>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <SlidersHorizontal className="w-4 h-4 text-gray-400" />
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Filters</span>
        </div>
        <div className="flex flex-wrap gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search patient, symptom, body area..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/20 focus:border-who-blue"
            />
          </div>
          <select
            value={urgencyFilter}
            onChange={(e) => setUrgencyFilter(e.target.value)}
            className="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/20 focus:border-who-blue"
          >
            <option value="">Clinical urgency</option>
            <option value="Critical">Critical</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>
          <select
            value={reportStatusFilter}
            onChange={(e) => setReportStatusFilter(e.target.value)}
            className="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/20 focus:border-who-blue"
          >
            <option value="">Report status</option>
            <option value="Pending">Pending</option>
            <option value="Submitted">Submitted</option>
          </select>
          <select
            value={countryFilter}
            onChange={(e) => setCountryFilter(e.target.value)}
            className="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/20 focus:border-who-blue"
          >
            <option value="">All Countries</option>
            {countries.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/20 focus:border-who-blue"
          >
            <option value="">Case status</option>
            <option value="pending_review">Pending Review</option>
            <option value="assigned">Assigned</option>
            <option value="responded">Responded</option>
            <option value="escalated">Escalated</option>
            <option value="closed">Closed</option>
          </select>
        </div>
      </div>

      <div className="flex items-center gap-1 text-xs text-gray-500">
        <span className="mr-1">Sort by:</span>
        {(["priority", "submitted", "pain"] as SortKey[]).map((key) => (
          <button
            key={key}
            onClick={() => toggleSort(key)}
            className={`px-2.5 py-1 rounded-md transition-colors flex items-center gap-1 ${
              sortKey === key
                ? "bg-who-blue/10 text-who-blue font-semibold"
                : "hover:bg-gray-100"
            }`}
          >
            {key === "priority" ? "Priority" : key === "submitted" ? "Time" : "Pain Score"}
            {sortKey === key && (
              <ArrowUpDown className="w-3 h-3" />
            )}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg font-heading font-semibold">No cases found</p>
          <p className="text-sm mt-1">
            {fetchError && cases.length > 0
              ? "Nothing matches your current filters. Clear filters or use Retry above if sync failed."
              : cases.length === 0
                ? fetchError
                  ? "Could not load cases from the API."
                  : "No cases in the database yet, or filters hide everything."
                : "Try adjusting your filters"}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((c) => (
            <Link
              key={c.caseId}
              href={`/cases/${c.caseId}`}
              className="block bg-white rounded-xl border border-gray-100 shadow-sm hover:shadow-md hover:border-who-blue/20 transition-all group"
            >
              <div className="flex items-stretch">
                <div className={`w-1.5 shrink-0 rounded-l-xl ${stripeClass(c.displayUrgency)}`} />

                <div className="flex-1 p-4 sm:p-5">
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-2 flex-wrap">
                        <span className="text-base font-heading font-bold text-gray-900 group-hover:text-who-blue transition-colors">
                          {c.patientAlias}
                        </span>
                        <ClinicalUrgencyBadge urgency={c.displayUrgency} size="sm" />
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded-full font-semibold border ${
                            c.reportStatus === "Submitted"
                              ? "bg-green-50 text-green-700 border-green-100"
                              : "bg-amber-50 text-amber-800 border-amber-100"
                          }`}
                        >
                          {c.reportStatus}
                        </span>
                        <CountryIndicator country={c.country} tier={c.countryTier} showTier />
                        {c.status && (
                          <span
                            className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                              c.status === "pending_review" || c.status === "intake_complete"
                                ? "bg-blue-50 text-blue-600"
                                : c.status === "assigned"
                                ? "bg-purple-50 text-purple-600"
                                : "bg-green-50 text-green-600"
                            }`}
                          >
                            {c.status}
                          </span>
                        )}
                      </div>

                      <p className="text-sm text-gray-600 mb-2">{c.symptomSummary}</p>

                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-400">
                        <span>Body: <strong className="text-gray-600">{c.bodyArea}</strong></span>
                        <span>Duration: <strong className="text-gray-600">{c.symptomDuration}</strong></span>
                        <span>Pain: <strong className="text-gray-600">{c.painScore}/10</strong></span>
                        <span>{timeAgo(c.submittedAt)}</span>
                      </div>

                      {c.redFlagIndicators.length > 0 && (
                        <div className="mt-2">
                          <RedFlagBadge flags={c.redFlagIndicators} compact />
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-4 sm:w-40 shrink-0">
                      <div className="flex-1">
                        <p className="text-[10px] text-gray-400 mb-1 uppercase tracking-wide font-semibold">Priority</p>
                        <PriorityBar score={c.priorityScore} />
                      </div>
                      <ChevronRight className="w-5 h-5 text-gray-300 group-hover:text-who-blue transition-colors shrink-0" />
                    </div>
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
