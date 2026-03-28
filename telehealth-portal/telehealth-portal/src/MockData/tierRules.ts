// ============================================================
// mockData/tierRules.ts
// Jurisdictional Permission Tier Definitions
// ============================================================

import { CountryTier, RecommendedAction, type TierRule } from "../types";

export const TIER_RULES: TierRule[] = [
  {
    tier: CountryTier.TIER_1,
    label: "Full Clinical Authority",
    description:
      "This jurisdiction permits full telehealth clinical authority including prescription issuance, treatment planning, and specialist referral.",
    allowedActions: [
      RecommendedAction.PRESCRIBE,
      RecommendedAction.LIMITED_TREATMENT,
      RecommendedAction.REFER_LOCAL,
      RecommendedAction.REFER_SPECIALIST,
      RecommendedAction.GUIDANCE_ONLY,
      RecommendedAction.ADVICE_ONLY,
      RecommendedAction.EMERGENCY_ESCALATION,
    ],
    restrictions: [],
    badgeColor: "#16a34a", // green-600
    uiWarning: undefined,
  },
  {
    tier: CountryTier.TIER_2,
    label: "Limited Treatment Authority",
    description:
      "This jurisdiction permits limited treatment recommendations and referrals, but does not allow prescription of controlled or scheduled medications.",
    allowedActions: [
      RecommendedAction.LIMITED_TREATMENT,
      RecommendedAction.REFER_LOCAL,
      RecommendedAction.REFER_SPECIALIST,
      RecommendedAction.GUIDANCE_ONLY,
      RecommendedAction.ADVICE_ONLY,
      RecommendedAction.EMERGENCY_ESCALATION,
    ],
    restrictions: [
      "Prescription of controlled substances is NOT permitted.",
      "Treatment authority limited to OTC-equivalent guidance.",
    ],
    badgeColor: "#2563eb", // blue-600
    uiWarning:
      "Prescription authority is restricted in this jurisdiction. You may recommend OTC treatments and referrals only.",
  },
  {
    tier: CountryTier.TIER_3,
    label: "Guidance & Referral Only",
    description:
      "This jurisdiction limits telehealth doctors to providing guidance and facilitating referrals. No treatment or prescription authority.",
    allowedActions: [
      RecommendedAction.REFER_LOCAL,
      RecommendedAction.REFER_SPECIALIST,
      RecommendedAction.GUIDANCE_ONLY,
      RecommendedAction.ADVICE_ONLY,
      RecommendedAction.EMERGENCY_ESCALATION,
    ],
    restrictions: [
      "Prescriptions are NOT permitted.",
      "Treatment recommendations are NOT permitted.",
      "Doctor may only provide informational guidance and refer to local facilities.",
    ],
    badgeColor: "#d97706", // amber-600
    uiWarning:
      "You are operating in a Guidance & Referral Only jurisdiction. Clinical treatment and prescription are not permitted here.",
  },
  {
    tier: CountryTier.TIER_4,
    label: "Advice Only",
    description:
      "This jurisdiction restricts telehealth doctors to general health advice only. Referral, treatment, and prescription are outside permitted scope.",
    allowedActions: [
      RecommendedAction.ADVICE_ONLY,
      RecommendedAction.EMERGENCY_ESCALATION,
    ],
    restrictions: [
      "Prescriptions are NOT permitted.",
      "Treatment recommendations are NOT permitted.",
      "Formal referrals are NOT permitted.",
      "Doctor may only provide general health advice and emergency escalation.",
    ],
    badgeColor: "#dc2626", // red-600
    uiWarning:
      "RESTRICTED JURISDICTION: You may only provide general health advice. All clinical actions including prescriptions and referrals are outside permitted scope.",
  },
];

/**
 * Lookup helper — returns TierRule by CountryTier enum value.
 */
export function getTierRule(tier: CountryTier): TierRule {
  const rule = TIER_RULES.find((r) => r.tier === tier);
  if (!rule) throw new Error(`No tier rule found for tier: ${tier}`);
  return rule;
}

// ============================================================
// Country → Tier Mapping (mock — 30 countries)
// ============================================================

export const COUNTRY_TIER_MAP: Record<string, CountryTier> = {
  // Tier 1 — Full Clinical Authority
  US: CountryTier.TIER_1,
  GB: CountryTier.TIER_1,
  CA: CountryTier.TIER_1,
  AU: CountryTier.TIER_1,
  DE: CountryTier.TIER_1,
  FR: CountryTier.TIER_1,

  // Tier 2 — Limited Treatment Authority
  BR: CountryTier.TIER_2,
  MX: CountryTier.TIER_2,
  ZA: CountryTier.TIER_2,
  IN: CountryTier.TIER_2,
  PH: CountryTier.TIER_2,
  NG: CountryTier.TIER_2,

  // Tier 3 — Guidance & Referral Only
  KE: CountryTier.TIER_3,
  GH: CountryTier.TIER_3,
  TZ: CountryTier.TIER_3,
  BD: CountryTier.TIER_3,
  ET: CountryTier.TIER_3,
  UG: CountryTier.TIER_3,

  // Tier 4 — Advice Only
  SD: CountryTier.TIER_4,
  ML: CountryTier.TIER_4,
  NE: CountryTier.TIER_4,
  AF: CountryTier.TIER_4,
  YE: CountryTier.TIER_4,
  SS: CountryTier.TIER_4,
};
