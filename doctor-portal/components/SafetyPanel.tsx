"use client";

import { useState } from "react";
import { TriageBreakdown, SafetyTrigger } from "@/types";
import {
  Shield,
  AlertOctagon,
  ChevronDown,
  ChevronUp,
  Zap,
  Activity,
  Brain,
  Clock,
  Globe,
  AlertTriangle,
  Flame,
} from "lucide-react";

interface SafetyData {
  triage_level: string;
  triage_breakdown?: TriageBreakdown;
  triggers: SafetyTrigger[];
  trigger_count: number;
  emergency_detected: boolean;
  kg_confidence: number;
  label: string;
}

interface Props {
  safety: SafetyData;
  triageBreakdown?: TriageBreakdown;
}

const TRIAGE_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  RED: { bg: "bg-red-100", text: "text-triage-red", border: "border-red-200" },
  YELLOW: { bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-200" },
  GREEN: { bg: "bg-green-50", text: "text-triage-green", border: "border-green-200" },
  BLACK: { bg: "bg-gray-900", text: "text-white", border: "border-gray-700" },
};

const SEVERITY_CONFIG: Record<string, { color: string; icon: typeof AlertOctagon }> = {
  immediate: { color: "text-triage-red", icon: Flame },
  warning: { color: "text-amber-600", icon: AlertTriangle },
  info: { color: "text-gray-500", icon: Shield },
};

export default function SafetyPanel({ safety, triageBreakdown }: Props) {
  const [showBreakdown, setShowBreakdown] = useState(false);

  const breakdown = triageBreakdown || safety.triage_breakdown;
  const triageColor = TRIAGE_COLORS[safety.triage_level] || TRIAGE_COLORS.GREEN;

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
      <h2 className="font-heading font-semibold text-gray-900 flex items-center gap-2 mb-4">
        <Shield className="w-4 h-4 text-who-blue" />
        Safety & Triage
      </h2>

      {/* Triage Level */}
      <div className="flex items-center gap-3 mb-4">
        <span
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-bold ${triageColor.bg} ${triageColor.text} ${triageColor.border} border`}
        >
          {safety.triage_level}
        </span>
        {safety.emergency_detected && (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-semibold bg-red-100 text-triage-red border border-red-200 animate-pulse">
            <Flame className="w-3 h-3" />
            EMERGENCY DETECTED
          </span>
        )}
        {safety.kg_confidence > 0 && (
          <span className="text-xs text-gray-500">
            KG Confidence:{" "}
            <span className="font-semibold text-gray-700">
              {Math.round(safety.kg_confidence * 100)}%
            </span>
          </span>
        )}
      </div>

      {/* Triggers */}
      {safety.triggers.length > 0 && (
        <div className="mb-4">
          <h3 className="text-[11px] font-semibold uppercase tracking-wide text-gray-400 mb-2">
            Safety Triggers ({safety.trigger_count})
          </h3>
          <div className="space-y-2">
            {safety.triggers.map((trigger, i) => {
              const sev = SEVERITY_CONFIG[trigger.severity] || SEVERITY_CONFIG.info;
              const TriggerIcon = sev.icon;
              return (
                <div
                  key={i}
                  className="flex items-start gap-2 text-sm bg-gray-50 rounded-lg p-2.5 border border-gray-100"
                >
                  <TriggerIcon className={`w-4 h-4 mt-0.5 shrink-0 ${sev.color}`} />
                  <div>
                    <span className="text-gray-800">{trigger.description}</span>
                    {trigger.layer && (
                      <span className="ml-2 text-[10px] text-gray-400">
                        [{trigger.layer}]
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Triage Breakdown (expandable) */}
      {breakdown && (
        <div>
          <button
            onClick={() => setShowBreakdown(!showBreakdown)}
            className="flex items-center gap-1.5 text-xs font-medium text-who-blue hover:text-who-blue-dark transition-colors mb-2"
          >
            {showBreakdown ? (
              <ChevronUp className="w-3.5 h-3.5" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5" />
            )}
            {showBreakdown ? "Hide" : "Show"} triage score breakdown
          </button>

          {showBreakdown && (
            <div className="bg-gray-50 rounded-lg p-4 border border-gray-100 space-y-2.5">
              <ScoreRow
                icon={Activity}
                label="Base Score"
                value={breakdown.base_score}
              />
              <ScoreRow
                icon={Zap}
                label="Severity"
                value={breakdown.severity_score}
              />
              <ScoreRow
                icon={AlertOctagon}
                label="Red Flags"
                value={breakdown.red_flag_score}
                highlight={breakdown.red_flag_score > 0}
              />
              <ScoreRow
                icon={Activity}
                label="Symptom Count"
                value={breakdown.symptom_count_score}
              />
              <ScoreRow
                icon={Clock}
                label="Duration"
                value={breakdown.duration_score}
              />
              <ScoreRow
                icon={Brain}
                label="KG Confidence"
                value={breakdown.kg_confidence_score}
              />
              <ScoreRow
                icon={Globe}
                label="Country Tier"
                value={breakdown.country_tier_score}
              />

              <div className="pt-2 border-t border-gray-200 flex items-center justify-between">
                <span className="text-sm font-heading font-bold text-gray-900">
                  Total Priority
                </span>
                <span className="text-sm font-heading font-bold text-gray-900">
                  {breakdown.total_priority}
                </span>
              </div>

              {breakdown.explanation && (
                <p className="text-xs text-gray-500 mt-2 italic leading-relaxed">
                  {breakdown.explanation}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      <p className="text-[10px] text-gray-400 italic mt-3">{safety.label}</p>
    </div>
  );
}

function ScoreRow({
  icon: Icon,
  label,
  value,
  highlight = false,
}: {
  icon: typeof Activity;
  label: string;
  value: number;
  highlight?: boolean;
}) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="flex items-center gap-2 text-gray-600">
        <Icon className="w-3.5 h-3.5 text-gray-400" />
        {label}
      </span>
      <span
        className={`font-medium ${
          highlight ? "text-triage-red" : "text-gray-800"
        }`}
      >
        {value > 0 ? `+${value}` : value}
      </span>
    </div>
  );
}
