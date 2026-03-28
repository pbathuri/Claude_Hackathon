"use client";

import { useState, useEffect } from "react";
import { KGStats, HottestPath, ConditionResult } from "@/types";
import { getKGStats, getHottestPaths, getConditions } from "@/lib/api";
import StatsCard from "@/components/StatsCard";
import LoadingSpinner from "@/components/LoadingSpinner";
import {
  GitBranch,
  Zap,
  BookOpen,
  Search,
  ArrowRight,
  Activity,
  Database,
  TrendingUp,
} from "lucide-react";

const specialtyColors: Record<string, string> = {
  "General Surgery": "#E63946",
  "Internal Medicine": "#0077B6",
  Cardiology: "#D62828",
  Neurology: "#6A4C93",
  Pediatrics: "#1982C4",
  Dermatology: "#F4A261",
  Urology: "#2A9D8F",
  Gynecology: "#E76F51",
  Pulmonology: "#264653",
  Orthopedics: "#606C38",
  "Emergency Medicine": "#BC4749",
  Psychiatry: "#7209B7",
};

export default function KnowledgeGraphPage() {
  const [stats, setStats] = useState<KGStats | null>(null);
  const [paths, setPaths] = useState<HottestPath[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResult, setSearchResult] = useState<ConditionResult | null>(null);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    Promise.all([getKGStats(), getHottestPaths()]).then(([s, p]) => {
      setStats(s);
      setPaths(p);
      setLoading(false);
    });
  }, []);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    setSearchResult(null);
    const result = await getConditions(searchQuery.trim());
    setSearchResult(result);
    setSearching(false);
  };

  if (loading) return <LoadingSpinner text="Loading knowledge graph..." />;

  const severityColor = (s: string) =>
    s === "High" ? "text-triage-red bg-triage-red/10" : s === "Medium" ? "text-triage-yellow bg-triage-yellow/10" : "text-triage-green bg-triage-green/10";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-heading font-bold text-gray-900 flex items-center gap-2">
          <GitBranch className="w-7 h-7 text-who-blue" />
          Knowledge Graph
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Medical knowledge graph powering AI triage decisions
        </p>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatsCard
            title="Total Nodes"
            value={stats.totalNodes.toLocaleString()}
            subtitle="Symptoms, conditions, specialties"
            icon={Database}
          />
          <StatsCard
            title="Total Edges"
            value={stats.totalEdges.toLocaleString()}
            subtitle="Medical relationships"
            icon={GitBranch}
            iconBg="bg-triage-green/10"
            iconColor="text-triage-green"
          />
          <StatsCard
            title="Learned Edges"
            value={stats.learnedEdges.toLocaleString()}
            subtitle="From real case data"
            icon={TrendingUp}
            iconBg="bg-triage-yellow/10"
            iconColor="text-triage-yellow"
          />
          <StatsCard
            title="Specialties"
            value={stats.specialties.length}
            subtitle="Medical disciplines covered"
            icon={Activity}
            iconBg="bg-purple-100"
            iconColor="text-purple-600"
          />
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Hottest Paths - 2/3 */}
        <div className="xl:col-span-2 bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
            <Zap className="w-5 h-5 text-triage-yellow" />
            <h2 className="font-heading font-semibold text-gray-900">Hottest Medical Pathways</h2>
          </div>
          <div className="divide-y divide-gray-50">
            {paths.map((path, i) => (
              <div key={i} className="px-6 py-3.5 flex items-center gap-4 hover:bg-gray-50/50 transition-colors">
                <span className="text-xs font-mono font-bold text-gray-300 w-5 text-right shrink-0">
                  {i + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-gray-800">{path.source}</span>
                    <ArrowRight className="w-3.5 h-3.5 text-gray-300 shrink-0" />
                    <span className="text-sm font-semibold text-who-blue">{path.target}</span>
                  </div>
                  <span className="text-[11px] text-gray-400">{path.pathType}</span>
                </div>
                <div className="shrink-0 flex items-center gap-2">
                  <div className="w-20 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-triage-yellow to-triage-red transition-all duration-500"
                      style={{ width: `${path.conductivity * 100}%` }}
                    />
                  </div>
                  <span className="text-xs font-mono font-semibold text-gray-600 w-10 text-right tabular-nums">
                    {(path.conductivity * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Symptom Search - 1/3 */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
            <h2 className="font-heading font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Search className="w-5 h-5 text-who-blue" />
              Symptom Explorer
            </h2>
            <div className="flex gap-2 mb-4">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                placeholder="e.g. fever, headache, cough..."
                className="flex-1 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/20 focus:border-who-blue"
              />
              <button
                onClick={handleSearch}
                disabled={searching || !searchQuery.trim()}
                className="px-3 py-2 bg-who-blue text-white rounded-lg text-sm font-semibold hover:bg-who-blue-dark transition-colors disabled:opacity-50"
              >
                {searching ? "..." : "Search"}
              </button>
            </div>

            {searchResult && (
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  Conditions for &ldquo;{searchResult.symptom}&rdquo;
                </p>
                <div className="space-y-2">
                  {searchResult.conditions.map((c, i) => (
                    <div key={i} className="bg-gray-50 rounded-lg p-3">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-gray-800">{c.name}</span>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${severityColor(c.severity)}`}>
                          {c.severity}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full bg-who-blue"
                            style={{ width: `${c.probability * 100}%` }}
                          />
                        </div>
                        <span className="text-[11px] font-mono text-gray-500 tabular-nums">
                          {(c.probability * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {!searchResult && !searching && (
              <div className="text-center py-6 text-gray-400">
                <BookOpen className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-xs">Enter a symptom to explore related conditions</p>
              </div>
            )}
          </div>

          {/* Specialty Heatmap */}
          {stats && (
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
              <h2 className="font-heading font-semibold text-gray-900 mb-4">
                Specialty Coverage
              </h2>
              <div className="grid grid-cols-2 gap-2">
                {stats.specialties.map((spec) => {
                  const color = specialtyColors[spec] || "#6B7280";
                  return (
                    <div
                      key={spec}
                      className="relative rounded-lg p-2.5 border border-gray-100 hover:border-gray-200 transition-colors overflow-hidden"
                    >
                      <div
                        className="absolute inset-0 opacity-[0.06]"
                        style={{ background: color }}
                      />
                      <div
                        className="w-2 h-2 rounded-full mb-1.5"
                        style={{ background: color }}
                      />
                      <p className="text-[11px] font-medium text-gray-700 leading-tight relative">
                        {spec}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Graph Last Updated */}
      {stats && (
        <p className="text-xs text-gray-400 text-center">
          Knowledge graph last updated: {new Date(stats.lastUpdated).toLocaleString()}
        </p>
      )}
    </div>
  );
}
