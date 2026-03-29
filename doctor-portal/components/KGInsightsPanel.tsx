"use client";

import { useState, useEffect, useRef } from "react";
import { Case, KGNavigationResult } from "@/types";
import { navigateKG } from "@/lib/api";
import MiniGraph from "./MiniGraph";
import LoadingSpinner from "./LoadingSpinner";
import { Brain, Stethoscope, MessageCircle, Activity } from "lucide-react";

interface Props {
  caseData: Case;
  kgInsights?: KGNavigationResult;
  onSpecialtyResolved?: (specialty: string) => void;
}

function parseSymptoms(summary: string): string[] {
  return summary
    .split(/(?:,|\band\b|\bwith\b|;)+/i)
    .map((s) => s.trim().toLowerCase())
    .filter((s) => s.length > 2);
}

function hasData(insights?: KGNavigationResult): boolean {
  return !!(
    insights &&
    insights.conditions &&
    insights.conditions.length > 0
  );
}

const FALLBACK_KG: KGNavigationResult = {
  conditions: [],
  recommendedSpecialty: "General Medicine",
  followUpQuestions: [],
  bodySystemMapping: {},
  graphPaths: [],
};

export default function KGInsightsPanel({ caseData, kgInsights, onSpecialtyResolved }: Props) {
  const [result, setResult] = useState<KGNavigationResult | null>(null);
  const [loading, setLoading] = useState(true);
  const onSpecialtyRef = useRef(onSpecialtyResolved);
  onSpecialtyRef.current = onSpecialtyResolved;

  useEffect(() => {
    let cancelled = false;

    if (hasData(kgInsights)) {
      setResult(kgInsights!);
      setLoading(false);
      onSpecialtyRef.current?.(kgInsights!.recommendedSpecialty ?? "General Medicine");
      return;
    }

    setLoading(true);
    const symptoms = parseSymptoms(caseData?.symptomSummary ?? "");

    navigateKG(symptoms)
      .then((data) => {
        if (cancelled) return;
        setResult(data);
        setLoading(false);
        onSpecialtyRef.current?.(data.recommendedSpecialty ?? "General Medicine");
      })
      .catch(() => {
        if (cancelled) return;
        setResult(FALLBACK_KG);
        setLoading(false);
        onSpecialtyRef.current?.("General Medicine");
      });

    return () => {
      cancelled = true;
    };
  }, [caseData?.symptomSummary, kgInsights]);

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-sm">
        <LoadingSpinner text="Analyzing via Knowledge Graph..." />
      </div>
    );
  }

  if (!result) return null;

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 bg-gradient-to-r from-who-blue/5 to-transparent">
        <h2 className="font-heading font-bold text-gray-900 flex items-center gap-2">
          <Brain className="w-5 h-5 text-who-blue" />
          KG Insights
        </h2>
        <p className="text-xs text-gray-400 mt-0.5">
          {hasData(kgInsights) ? "From intake-time analysis" : "Generated from symptom graph navigation"}
        </p>
      </div>

      <div className="p-5 space-y-6">
        {/* Suggested Conditions */}
        <section>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2.5">
            Suggested Conditions
          </h3>
          <div className="space-y-2">
            {(result.conditions ?? []).map((c, i) => (
              <div
                key={i}
                className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2.5"
              >
                <div className="min-w-0 mr-3">
                  <p className="text-sm font-medium text-gray-800 truncate">{c.name}</p>
                  <p className="text-[11px] text-gray-400">{c.specialty}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <div className="w-14 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-who-blue transition-all duration-500"
                      style={{ width: `${c.score * 100}%` }}
                    />
                  </div>
                  <span className="text-[11px] font-mono text-gray-500 w-8 text-right tabular-nums">
                    {(c.score * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Recommended Specialty */}
        <div className="bg-who-blue/5 border border-who-blue/15 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-1.5">
            <Stethoscope className="w-4 h-4 text-who-blue" />
            <span className="text-[11px] font-semibold text-who-blue uppercase tracking-wide">
              Recommended Specialty
            </span>
          </div>
          <p className="text-lg font-heading font-bold text-gray-900">
            {result.recommendedSpecialty}
          </p>
        </div>

        {/* Follow-up Questions */}
        <section>
          <h3 className="flex items-center gap-2 text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2.5">
            <MessageCircle className="w-3.5 h-3.5" />
            Follow-up Questions
          </h3>
          <ul className="space-y-1.5">
            {(result.followUpQuestions ?? []).map((q, i) => (
              <li
                key={i}
                className="text-sm text-gray-600 bg-amber-50/60 rounded-lg px-3 py-2 border border-amber-100/60"
              >
                {q}
              </li>
            ))}
          </ul>
        </section>

        {/* Body System Mapping */}
        <section>
          <h3 className="flex items-center gap-2 text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2.5">
            <Activity className="w-3.5 h-3.5" />
            Body System Mapping
          </h3>
          <div className="space-y-2">
            {Object.entries(result.bodySystemMapping ?? {}).map(([system, symptomList]) => (
              <div key={system} className="flex items-start gap-2">
                <span className="text-[11px] font-semibold bg-gray-100 text-gray-700 px-2 py-0.5 rounded shrink-0 mt-0.5">
                  {system}
                </span>
                <div className="flex flex-wrap gap-1">
                  {(Array.isArray(symptomList) ? symptomList : []).map((s, i) => (
                    <span key={i} className="text-[11px] text-gray-500 bg-gray-50 border border-gray-100 px-2 py-0.5 rounded">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Mini Graph */}
        <section>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2.5">
            Graph Pathway
          </h3>
          <div className="bg-gray-50/70 rounded-lg p-3 border border-gray-100">
            <MiniGraph paths={result.graphPaths ?? []} />
            <div className="flex items-center justify-center gap-4 mt-3 pt-3 border-t border-gray-200">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-triage-red" />
                <span className="text-[10px] text-gray-500">Symptom</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-triage-yellow" />
                <span className="text-[10px] text-gray-500">Condition</span>
              </div>
              <div className="flex items-center gap-1.5">
                <svg width="10" height="10" viewBox="0 0 10 10">
                  <polygon points="5,0 10,10 0,10" fill="#2A9D8F" />
                </svg>
                <span className="text-[10px] text-gray-500">Specialty</span>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
