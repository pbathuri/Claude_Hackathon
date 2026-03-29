const flags: Record<string, string> = {
  Kenya: "\u{1F1F0}\u{1F1EA}",
  Nigeria: "\u{1F1F3}\u{1F1EC}",
  India: "\u{1F1EE}\u{1F1F3}",
  Philippines: "\u{1F1F5}\u{1F1ED}",
};

const tierDescriptions: Record<number, string> = {
  1: "Tier 1: Advanced healthcare infrastructure with specialist access",
  2: "Tier 2: Developing healthcare system, some specialty access",
  3: "Tier 3: Limited healthcare access — priority routing enabled",
};

interface Props {
  country: string;
  tier?: number;
  showTier?: boolean;
}

export default function CountryIndicator({ country, tier, showTier = false }: Props) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="text-base leading-none">{flags[country] || "\u{1F30D}"}</span>
      <span className="text-sm text-gray-700 font-medium">{country}</span>
      {showTier && tier && (
        <span className="group relative">
          <span
            className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${
              tier === 3
                ? "bg-red-50 text-red-600"
                : tier === 2
                ? "bg-amber-50 text-amber-600"
                : "bg-green-50 text-green-600"
            }`}
          >
            T{tier}
          </span>
          <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block w-52 p-2.5 bg-gray-900 text-white text-[11px] rounded-lg shadow-xl z-50 leading-relaxed">
            {tierDescriptions[tier]}
            <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
          </span>
        </span>
      )}
    </span>
  );
}
