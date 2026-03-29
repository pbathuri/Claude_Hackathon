"use client";

import { LanguageBanner as LanguageBannerType } from "@/types";
import {
  Globe,
  AlertTriangle,
  ShieldCheck,
  ShieldAlert,
  Languages,
  Phone,
} from "lucide-react";

interface Props {
  banner: LanguageBannerType;
}

const RISK_CONFIG = {
  none: {
    bg: "bg-gray-50",
    border: "border-gray-200",
    icon: ShieldCheck,
    iconColor: "text-triage-green",
    labelColor: "text-gray-600",
  },
  low: {
    bg: "bg-green-50",
    border: "border-green-200",
    icon: ShieldCheck,
    iconColor: "text-triage-green",
    labelColor: "text-triage-green",
  },
  medium: {
    bg: "bg-amber-50",
    border: "border-amber-200",
    icon: AlertTriangle,
    iconColor: "text-amber-600",
    labelColor: "text-amber-700",
  },
  high: {
    bg: "bg-red-50",
    border: "border-red-200",
    icon: ShieldAlert,
    iconColor: "text-triage-red",
    labelColor: "text-triage-red",
  },
};

export default function LanguageBanner({ banner }: Props) {
  const config = RISK_CONFIG[banner.risk_level] || RISK_CONFIG.none;
  const Icon = config.icon;

  return (
    <div
      className={`rounded-xl ${config.bg} ${config.border} border p-4`}
    >
      <div className="flex items-start gap-3">
        <Icon className={`w-5 h-5 mt-0.5 shrink-0 ${config.iconColor}`} />
        <div className="flex-1 min-w-0">
          {/* Header row */}
          <div className="flex flex-wrap items-center gap-2 mb-1.5">
            <span className="text-sm font-heading font-semibold text-gray-900 flex items-center gap-1.5">
              <Globe className="w-3.5 h-3.5 text-gray-400" />
              Patient Language: {banner.patient_language_name}
            </span>
            {banner.translation_used && (
              <span className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-white/60 text-gray-600 border border-gray-200">
                <Languages className="w-3 h-3" />
                Translation Active
              </span>
            )}
            {banner.code_switching_detected && (
              <span className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 border border-amber-200">
                Code-Switching
              </span>
            )}
          </div>

          {/* Risk label */}
          <p className={`text-sm ${config.labelColor}`}>
            {banner.risk_label}
          </p>

          {/* Details row */}
          <div className="flex flex-wrap items-center gap-4 mt-2 text-xs text-gray-500">
            {banner.translation_used && (
              <span>
                Confidence:{" "}
                <span
                  className={`font-semibold ${
                    banner.translation_confidence >= 0.8
                      ? "text-triage-green"
                      : banner.translation_confidence >= 0.6
                      ? "text-amber-600"
                      : "text-triage-red"
                  }`}
                >
                  {Math.round(banner.translation_confidence * 100)}%
                </span>
              </span>
            )}
            <span>
              Detection: <span className="font-medium text-gray-700">{banner.detection_method}</span>
            </span>
            {banner.detected_languages.length > 1 && (
              <span>
                Languages detected: {banner.detected_languages.join(", ")}
              </span>
            )}
          </div>

          {/* Interpreter recommendation */}
          {banner.interpreter_recommended && (
            <div className="mt-3 flex items-center gap-2 text-sm font-medium text-triage-red bg-red-100/60 rounded-lg px-3 py-2 border border-red-200/60">
              <Phone className="w-4 h-4 shrink-0" />
              Interpreter recommended for this case
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
