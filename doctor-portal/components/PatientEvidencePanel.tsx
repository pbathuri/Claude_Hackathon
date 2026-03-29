"use client";

import { useState } from "react";
import {
  MessageSquare,
  ChevronDown,
  ChevronUp,
  Languages,
  Eye,
  EyeOff,
} from "lucide-react";

interface PatientEvidence {
  turn_number: number;
  original_text: string;
  language: string;
  timestamp?: string;
  channel: string;
  label: string;
  english_translation?: string;
  translation_label?: string;
  translation_confidence?: number;
}

interface Props {
  evidence: PatientEvidence[];
  patientLanguage: string;
}

export default function PatientEvidencePanel({ evidence, patientLanguage }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [showTranslations, setShowTranslations] = useState(true);

  if (!evidence || evidence.length === 0) return null;

  const displayItems = expanded ? evidence : evidence.slice(0, 3);
  const hasTranslations = evidence.some((e) => e.english_translation);

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-heading font-semibold text-gray-900 flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-who-blue" />
          Patient Evidence
          <span className="text-xs font-normal text-gray-400 ml-1">
            ({evidence.length} turn{evidence.length !== 1 ? "s" : ""})
          </span>
        </h2>
        {hasTranslations && (
          <button
            onClick={() => setShowTranslations(!showTranslations)}
            className="flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-who-blue transition-colors px-2 py-1 rounded-md hover:bg-gray-50"
          >
            {showTranslations ? (
              <>
                <EyeOff className="w-3.5 h-3.5" />
                Hide translations
              </>
            ) : (
              <>
                <Eye className="w-3.5 h-3.5" />
                Show translations
              </>
            )}
          </button>
        )}
      </div>

      <div className="space-y-3">
        {displayItems.map((item, i) => (
          <div
            key={i}
            className="border border-gray-100 rounded-lg overflow-hidden"
          >
            {/* Original text */}
            <div className="p-3 bg-gray-50">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-[10px] font-semibold uppercase tracking-wide text-gray-400">
                  Turn {item.turn_number}
                </span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-200 text-gray-600 font-medium">
                  {item.language.toUpperCase()}
                </span>
                <span className="text-[10px] text-gray-400">{item.channel}</span>
                {item.timestamp && (
                  <span className="text-[10px] text-gray-400 ml-auto">
                    {new Date(item.timestamp).toLocaleTimeString()}
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-800 leading-relaxed">
                {item.original_text}
              </p>
              <p className="text-[10px] text-gray-400 mt-1 italic">{item.label}</p>
            </div>

            {/* Translation (if available and visible) */}
            {item.english_translation && showTranslations && (
              <div className="p-3 bg-blue-50/40 border-t border-blue-100/50">
                <div className="flex items-center gap-2 mb-1">
                  <Languages className="w-3 h-3 text-who-blue" />
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-who-blue">
                    {item.translation_label || "System Translation"}
                  </span>
                  {item.translation_confidence !== undefined && (
                    <span
                      className={`text-[10px] font-medium ${
                        item.translation_confidence >= 0.8
                          ? "text-triage-green"
                          : item.translation_confidence >= 0.6
                          ? "text-amber-600"
                          : "text-triage-red"
                      }`}
                    >
                      {Math.round(item.translation_confidence * 100)}% confidence
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-700 leading-relaxed">
                  {item.english_translation}
                </p>
              </div>
            )}
          </div>
        ))}
      </div>

      {evidence.length > 3 && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1.5 mt-3 text-xs font-medium text-who-blue hover:text-who-blue-dark transition-colors"
        >
          {expanded ? (
            <>
              <ChevronUp className="w-3.5 h-3.5" />
              Show less
            </>
          ) : (
            <>
              <ChevronDown className="w-3.5 h-3.5" />
              Show all {evidence.length} turns
            </>
          )}
        </button>
      )}
    </div>
  );
}
