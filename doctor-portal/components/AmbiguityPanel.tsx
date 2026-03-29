"use client";

import {
  HelpCircle,
  AlertTriangle,
  Languages,
  Shield,
  MessageSquareWarning,
} from "lucide-react";

interface AmbiguityItem {
  type: string;
  flag: string;
  context: string;
}

interface AmbiguityData {
  unresolved_items: AmbiguityItem[];
  has_unresolved: boolean;
  count: number;
  label: string;
}

interface Props {
  ambiguity: AmbiguityData;
}

const TYPE_CONFIG: Record<
  string,
  { icon: typeof HelpCircle; color: string; bg: string }
> = {
  translation: {
    icon: Languages,
    color: "text-amber-600",
    bg: "bg-amber-50",
  },
  system: {
    icon: Shield,
    color: "text-red-600",
    bg: "bg-red-50",
  },
  guard: {
    icon: MessageSquareWarning,
    color: "text-orange-600",
    bg: "bg-orange-50",
  },
};

export default function AmbiguityPanel({ ambiguity }: Props) {
  if (!ambiguity || !ambiguity.has_unresolved) return null;

  return (
    <div className="bg-white rounded-xl border border-amber-200 shadow-sm p-6">
      <h2 className="font-heading font-semibold text-amber-800 flex items-center gap-2 mb-1">
        <AlertTriangle className="w-4 h-4 text-amber-600" />
        Unresolved Ambiguities
        <span className="text-xs font-normal text-amber-500 ml-1">
          ({ambiguity.count})
        </span>
      </h2>
      <p className="text-[10px] text-amber-600/80 italic mb-4">{ambiguity.label}</p>

      <div className="space-y-2">
        {ambiguity.unresolved_items.map((item, i) => {
          const cfg = TYPE_CONFIG[item.type] || TYPE_CONFIG.system;
          const Icon = cfg.icon;
          return (
            <div
              key={i}
              className={`flex items-start gap-2.5 rounded-lg p-3 ${cfg.bg} border border-gray-100`}
            >
              <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${cfg.color}`} />
              <div>
                <p className="text-sm text-gray-800 font-medium">{item.flag}</p>
                <p className="text-xs text-gray-500 mt-0.5">{item.context}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
