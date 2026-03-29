const config = {
  High: {
    bg: "bg-triage-red/10",
    text: "text-triage-red",
    border: "border-triage-red/30",
    dot: "bg-triage-red",
    label: "RED",
  },
  Medium: {
    bg: "bg-triage-yellow/10",
    text: "text-triage-yellow",
    border: "border-triage-yellow/30",
    dot: "bg-triage-yellow",
    label: "YELLOW",
  },
  Low: {
    bg: "bg-triage-green/10",
    text: "text-triage-green",
    border: "border-triage-green/30",
    dot: "bg-triage-green",
    label: "GREEN",
  },
};

const sizes = {
  sm: "text-[10px] px-2 py-0.5 gap-1",
  md: "text-xs px-2.5 py-1 gap-1.5",
  lg: "text-sm px-3 py-1.5 gap-1.5",
};

interface Props {
  urgency: "High" | "Medium" | "Low";
  size?: "sm" | "md" | "lg";
}

export default function UrgencyBadge({ urgency, size = "md" }: Props) {
  const c = config[urgency];
  return (
    <span
      className={`inline-flex items-center font-bold rounded-full border ${c.bg} ${c.text} ${c.border} ${sizes[size]}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
      {c.label}
    </span>
  );
}
