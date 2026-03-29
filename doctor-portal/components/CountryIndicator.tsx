const flags: Record<string, string> = {
  Kenya: "\u{1F1F0}\u{1F1EA}",
  Nigeria: "\u{1F1F3}\u{1F1EC}",
  India: "\u{1F1EE}\u{1F1F3}",
  Philippines: "\u{1F1F5}\u{1F1ED}",
  "United States": "\u{1F1FA}\u{1F1F8}",
  "Dominican Republic": "\u{1F1E9}\u{1F1F4}",
  Russia: "\u{1F1F7}\u{1F1FA}",
  Egypt: "\u{1F1EA}\u{1F1EC}",
  "South Africa": "\u{1F1FF}\u{1F1E6}",
  Greece: "\u{1F1EC}\u{1F1F7}",
  Netherlands: "\u{1F1F3}\u{1F1F1}",
  Belgium: "\u{1F1E7}\u{1F1EA}",
  France: "\u{1F1EB}\u{1F1F7}",
  Spain: "\u{1F1EA}\u{1F1F8}",
  Hungary: "\u{1F1ED}\u{1F1FA}",
  Italy: "\u{1F1EE}\u{1F1F9}",
  Romania: "\u{1F1F7}\u{1F1F4}",
  Switzerland: "\u{1F1E8}\u{1F1ED}",
  Austria: "\u{1F1E6}\u{1F1F9}",
  "United Kingdom": "\u{1F1EC}\u{1F1E7}",
  Denmark: "\u{1F1E9}\u{1F1F0}",
  Sweden: "\u{1F1F8}\u{1F1EA}",
  Norway: "\u{1F1F3}\u{1F1F4}",
  Canada: "\u{1F1E8}\u{1F1E6}",
  Germany: "\u{1F1E9}\u{1F1EA}",
  Japan: "\u{1F1EF}\u{1F1F5}",
  "South Korea": "\u{1F1F0}\u{1F1F7}",
  China: "\u{1F1E8}\u{1F1F3}",
  Mexico: "\u{1F1F2}\u{1F1FD}",
  Brazil: "\u{1F1E7}\u{1F1F7}",
  Vietnam: "\u{1F1FB}\u{1F1F3}",
  Indonesia: "\u{1F1EE}\u{1F1E9}",
  Pakistan: "\u{1F1F5}\u{1F1F0}",
  Turkey: "\u{1F1F9}\u{1F1F7}",
  Iran: "\u{1F1EE}\u{1F1F7}",
  Argentina: "\u{1F1E6}\u{1F1F7}",
  Chile: "\u{1F1E8}\u{1F1F1}",
  Colombia: "\u{1F1E8}\u{1F1F4}",
  Venezuela: "\u{1F1FB}\u{1F1EA}",
  Peru: "\u{1F1F5}\u{1F1EA}",
  Thailand: "\u{1F1F9}\u{1F1ED}",
  Singapore: "\u{1F1F8}\u{1F1EC}",
  Malaysia: "\u{1F1F2}\u{1F1FE}",
  Australia: "\u{1F1E6}\u{1F1FA}",
  "New Zealand": "\u{1F1F3}\u{1F1FF}",
  "Unknown / International (Tier 4)": "\u{1F30D}",
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
