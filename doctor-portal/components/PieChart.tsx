interface Segment {
  label: string;
  value: number;
  color: string;
}

interface Props {
  segments: Segment[];
  size?: number;
  centerLabel?: string;
}

export default function PieChart({ segments, size = 180, centerLabel }: Props) {
  const total = segments.reduce((s, d) => s + d.value, 0);
  if (total === 0) return null;

  const r = 65;
  const strokeWidth = 26;
  const center = size / 2;
  const circumference = 2 * Math.PI * r;

  let accumulated = 0;
  const arcs = segments.map((seg) => {
    const dash = (seg.value / total) * circumference;
    const result = { ...seg, dash, offset: accumulated };
    accumulated += dash;
    return result;
  });

  return (
    <div className="flex flex-col items-center gap-4">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={center} cy={center} r={r} fill="none" stroke="#f3f4f6" strokeWidth={strokeWidth} />
        {arcs.map((arc, i) => (
          <circle
            key={i}
            cx={center}
            cy={center}
            r={r}
            fill="none"
            stroke={arc.color}
            strokeWidth={strokeWidth}
            strokeDasharray={`${arc.dash} ${circumference - arc.dash}`}
            strokeDashoffset={-arc.offset}
            strokeLinecap="round"
            transform={`rotate(-90 ${center} ${center})`}
            className="transition-all duration-700 ease-out"
          />
        ))}
        <text
          x={center}
          y={center - 8}
          textAnchor="middle"
          className="fill-gray-900 font-bold"
          fontSize="28"
          fontFamily="var(--font-heading)"
        >
          {total}
        </text>
        <text
          x={center}
          y={center + 12}
          textAnchor="middle"
          className="fill-gray-400"
          fontSize="11"
        >
          {centerLabel || "Total Cases"}
        </text>
      </svg>
      <div className="flex flex-wrap justify-center gap-x-4 gap-y-1">
        {segments.map((seg, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: seg.color }} />
            <span className="text-xs text-gray-600">
              {seg.label} ({seg.value})
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
