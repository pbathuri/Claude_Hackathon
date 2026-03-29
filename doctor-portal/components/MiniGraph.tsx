interface GraphPath {
  from: string;
  to: string;
  weight: number;
  type: string;
}

interface Props {
  paths: GraphPath[];
}

interface NodeData {
  name: string;
  x: number;
  y: number;
  category: "symptom" | "condition" | "specialty";
}

export default function MiniGraph({ paths }: Props) {
  if (!paths || paths.length === 0) return null;

  const symptoms = new Map<string, boolean>();
  const conditions = new Map<string, boolean>();
  const specialties = new Map<string, boolean>();

  paths.forEach((p) => {
    if (p.type === "symptom-condition") {
      symptoms.set(p.from, true);
      conditions.set(p.to, true);
    } else if (p.type === "condition-specialty") {
      conditions.set(p.from, true);
      specialties.set(p.to, true);
    }
  });

  const colX = { symptom: 70, condition: 230, specialty: 390 };
  const svgWidth = 460;

  const makeNodes = (
    names: Map<string, boolean>,
    category: NodeData["category"]
  ): NodeData[] =>
    [...names.keys()].map((name, i) => ({
      name,
      x: colX[category],
      y: 45 + i * 52,
      category,
    }));

  const symptomNodes = makeNodes(symptoms, "symptom");
  const conditionNodes = makeNodes(conditions, "condition");
  const specialtyNodes = makeNodes(specialties, "specialty");
  const allNodes = [...symptomNodes, ...conditionNodes, ...specialtyNodes];

  const maxY = Math.max(...allNodes.map((n) => n.y), 60);
  const svgHeight = maxY + 35;

  const nodeColors = {
    symptom: "#E63946",
    condition: "#F4A261",
    specialty: "#2A9D8F",
  };

  const truncate = (s: string, max: number) =>
    s.length > max ? s.slice(0, max - 1) + "\u2026" : s;

  return (
    <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="w-full" style={{ maxHeight: 280 }}>
      {/* Column headers */}
      <text x={colX.symptom} y={16} textAnchor="middle" fontSize="9" fill="#9CA3AF" fontWeight="600" letterSpacing="0.05em">
        SYMPTOMS
      </text>
      <text x={colX.condition} y={16} textAnchor="middle" fontSize="9" fill="#9CA3AF" fontWeight="600" letterSpacing="0.05em">
        CONDITIONS
      </text>
      <text x={colX.specialty} y={16} textAnchor="middle" fontSize="9" fill="#9CA3AF" fontWeight="600" letterSpacing="0.05em">
        SPECIALTY
      </text>

      {/* Edges */}
      {paths.map((p, i) => {
        const from = allNodes.find((n) => n.name === p.from);
        const to = allNodes.find((n) => n.name === p.to);
        if (!from || !to) return null;
        const mx = (from.x + to.x) / 2;
        return (
          <path
            key={i}
            d={`M ${from.x + 12} ${from.y} C ${mx} ${from.y}, ${mx} ${to.y}, ${to.x - 12} ${to.y}`}
            stroke={`rgba(0, 119, 182, ${0.25 + p.weight * 0.45})`}
            strokeWidth={1 + p.weight * 1.5}
            fill="none"
          />
        );
      })}

      {/* Nodes */}
      {allNodes.map((n, i) => {
        const color = nodeColors[n.category];
        return (
          <g key={i}>
            {n.category === "symptom" && (
              <circle cx={n.x} cy={n.y} r={7} fill={color} opacity={0.9} />
            )}
            {n.category === "condition" && (
              <rect x={n.x - 7} y={n.y - 7} width={14} height={14} rx={3} fill={color} opacity={0.9} />
            )}
            {n.category === "specialty" && (
              <polygon
                points={`${n.x},${n.y - 8} ${n.x + 8},${n.y + 5} ${n.x - 8},${n.y + 5}`}
                fill={color}
                opacity={0.9}
              />
            )}
            <text
              x={n.category === "symptom" ? n.x - 14 : n.category === "specialty" ? n.x + 14 : n.x}
              y={n.category === "condition" ? n.y + 22 : n.y + 4}
              textAnchor={n.category === "symptom" ? "end" : n.category === "specialty" ? "start" : "middle"}
              fontSize="9"
              fill="#4B5563"
              fontWeight="500"
            >
              {truncate(n.name, 20)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
