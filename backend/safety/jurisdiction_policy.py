"""Country-tier-aware action constraints per WHO alignment."""

from dataclasses import dataclass


@dataclass
class JurisdictionPolicy:
    country_code: str
    tier: int
    can_diagnose: bool
    can_treat: bool
    can_prescribe: bool
    can_refer: bool
    emergency_numbers: list[str]
    default_language: str = "en"

    @property
    def label(self) -> str:
        labels = {
            1: "Full diagnosis, treatment & prescribing",
            2: "Diagnosis & treatment, no prescribing",
            3: "Diagnosis & guidance, referral only",
            4: "Guidance only",
        }
        return labels.get(self.tier, "Unknown")


JURISDICTION_POLICIES = {
    "IN": JurisdictionPolicy("IN", 1, True, True, True, True, ["112", "108"], "hi"),
    "NG": JurisdictionPolicy("NG", 2, True, True, False, True, ["112", "199"], "en"),
    "KE": JurisdictionPolicy("KE", 3, True, False, False, True, ["999", "112"], "sw"),
    "PH": JurisdictionPolicy("PH", 3, True, False, False, True, ["911", "143"], "tl"),
    "ZZ": JurisdictionPolicy("ZZ", 4, False, False, False, True, ["112", "911", "999"], "en"),
}


def get_jurisdiction_policy(country_code: str) -> JurisdictionPolicy:
    return JURISDICTION_POLICIES.get(
        country_code,
        JurisdictionPolicy(country_code, 4, False, False, False, True, ["112", "911"]),
    )
