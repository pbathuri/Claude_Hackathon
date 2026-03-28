import { AlertOctagon } from "lucide-react";

interface Props {
  flags: string[];
  compact?: boolean;
}

export default function RedFlagBadge({ flags, compact = false }: Props) {
  if (flags.length === 0) return null;

  if (compact) {
    return (
      <div className="flex items-center gap-1.5">
        <AlertOctagon className="w-3.5 h-3.5 text-triage-red shrink-0" />
        <span className="text-[11px] font-semibold text-triage-red">{flags.length} red flag{flags.length > 1 ? "s" : ""}</span>
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      {flags.map((flag, i) => (
        <div
          key={i}
          className="flex items-center gap-2 bg-red-50 border border-red-100 rounded-lg px-3 py-2"
        >
          <AlertOctagon className="w-3.5 h-3.5 text-triage-red shrink-0" />
          <span className="text-xs font-medium text-red-800">{flag}</span>
        </div>
      ))}
    </div>
  );
}
