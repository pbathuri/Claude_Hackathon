interface Bar {
  label: string;
  value: number;
  color?: string;
}

interface Props {
  bars: Bar[];
  maxValue?: number;
}

export default function BarChart({ bars, maxValue }: Props) {
  const max = maxValue || Math.max(...bars.map((b) => b.value), 1);

  return (
    <div className="space-y-3">
      {bars.map((bar, i) => (
        <div key={i} className="group">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-medium text-gray-600">{bar.label}</span>
            <span className="text-xs font-mono font-semibold text-gray-500 tabular-nums">{bar.value}</span>
          </div>
          <div className="h-6 bg-gray-50 rounded-md overflow-hidden border border-gray-100">
            <div
              className="h-full rounded-md transition-all duration-700 ease-out group-hover:opacity-90"
              style={{
                width: `${Math.max((bar.value / max) * 100, 0)}%`,
                background: bar.color || "#0077B6",
                minWidth: bar.value > 0 ? "4px" : "0",
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
