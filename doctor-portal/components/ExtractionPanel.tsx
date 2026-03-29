"use client";

import { ExtractionItem } from "@/types";
import {
  ClipboardList,
  User,
  Bot,
  GitBranch,
  BookOpen,
} from "lucide-react";

interface ExtractionData {
  items: ExtractionItem[];
  total_facts: number;
  ai_extracted_count: number;
  patient_reported_count: number;
  label: string;
}

interface Props {
  extraction: ExtractionData;
}

const SOURCE_CONFIG: Record<
  string,
  { icon: typeof User; color: string; bg: string; label: string }
> = {
  patient_reported: {
    icon: User,
    color: "text-triage-green",
    bg: "bg-green-50",
    label: "Patient",
  },
  ai_extracted: {
    icon: Bot,
    color: "text-who-blue",
    bg: "bg-blue-50",
    label: "AI",
  },
  kg_inferred: {
    icon: GitBranch,
    color: "text-purple-600",
    bg: "bg-purple-50",
    label: "KG",
  },
  rule_derived: {
    icon: BookOpen,
    color: "text-amber-600",
    bg: "bg-amber-50",
    label: "Rule",
  },
};

const TYPE_LABELS: Record<string, string> = {
  symptom: "Symptom",
  severity: "Severity",
  duration: "Duration",
  body_area: "Body Area",
  medication: "Medication",
  allergy: "Allergy",
};

export default function ExtractionPanel({ extraction }: Props) {
  if (!extraction || extraction.items.length === 0) return null;

  // Group items by type
  const grouped = extraction.items.reduce<Record<string, ExtractionItem[]>>(
    (acc, item) => {
      const key = item.type;
      if (!acc[key]) acc[key] = [];
      acc[key].push(item);
      return acc;
    },
    {}
  );

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-heading font-semibold text-gray-900 flex items-center gap-2">
          <ClipboardList className="w-4 h-4 text-who-blue" />
          Structured Extraction
        </h2>
        <div className="flex items-center gap-3 text-[10px] font-medium">
          <span className="flex items-center gap-1 text-triage-green">
            <User className="w-3 h-3" />
            {extraction.patient_reported_count} patient-reported
          </span>
          <span className="flex items-center gap-1 text-who-blue">
            <Bot className="w-3 h-3" />
            {extraction.ai_extracted_count} AI-extracted
          </span>
        </div>
      </div>

      <p className="text-[10px] text-gray-400 italic mb-4">{extraction.label}</p>

      <div className="space-y-4">
        {Object.entries(grouped).map(([type, items]) => (
          <div key={type}>
            <h3 className="text-[11px] font-semibold uppercase tracking-wide text-gray-400 mb-2">
              {TYPE_LABELS[type] || type}
            </h3>
            <div className="flex flex-wrap gap-2">
              {items.map((item, i) => {
                const sourceConfig =
                  SOURCE_CONFIG[item.source] || SOURCE_CONFIG.ai_extracted;
                const Icon = sourceConfig.icon;
                return (
                  <div
                    key={i}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-sm ${sourceConfig.bg} border-gray-200`}
                  >
                    <Icon className={`w-3 h-3 ${sourceConfig.color}`} />
                    <span className="text-gray-800 font-medium">
                      {item.display || item.value}
                    </span>
                    {item.confidence !== undefined && item.confidence < 0.8 && (
                      <span className="text-[9px] text-amber-600 font-medium ml-1">
                        ~{Math.round(item.confidence * 100)}%
                      </span>
                    )}
                    {item.source_turn && (
                      <span className="text-[9px] text-gray-400 ml-1">
                        T{item.source_turn}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Source legend */}
      <div className="mt-4 pt-3 border-t border-gray-100 flex flex-wrap gap-4 text-[10px] text-gray-500">
        {Object.entries(SOURCE_CONFIG).map(([key, cfg]) => {
          const Icon = cfg.icon;
          return (
            <span key={key} className="flex items-center gap-1">
              <Icon className={`w-3 h-3 ${cfg.color}`} />
              {cfg.label}
            </span>
          );
        })}
      </div>
    </div>
  );
}
