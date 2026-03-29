interface Props {
  score: number;
  showLabel?: boolean;
  size?: "sm" | "md";
}

export default function PriorityBar({ score, showLabel = true, size = "md" }: Props) {
  const color =
    score >= 75 ? "bg-triage-red" : score >= 40 ? "bg-triage-yellow" : "bg-triage-green";
  const height = size === "sm" ? "h-1.5" : "h-2";

  return (
    <div className="flex items-center gap-2">
      <div className={`flex-1 ${height} bg-gray-100 rounded-full overflow-hidden`}>
        <div
          className={`${height} rounded-full transition-all duration-700 ease-out ${color}`}
          style={{ width: `${Math.min(score, 100)}%` }}
        />
      </div>
      {showLabel && (
        <span className="text-xs font-mono font-semibold text-gray-600 w-8 text-right tabular-nums">
          {score}
        </span>
      )}
    </div>
  );
}
