"""
Country detection from phone numbers and permission matrix enforcement.

Doctor portal v2 (Twilio): country is resolved using ONLY "+" and the next two
digits (e.g. "+01 8128034835" → "+01" → United States). No 3–4 digit prefixes.
PHONE_COUNTRY_MAP holds those two-digit keys. If the key is missing, libphonenumber
parses the full normalized number.
"""
import hashlib
import re
import phonenumbers
from phonenumbers import geocoder
from sqlalchemy.orm import Session

from models import CountryPermission, Patient

# Two-digit calling keys only: "+" plus exactly two digits (e.g. "+01", "+44", "+91").
# Twilio-style NANP uses "+01" rather than "+1".
PHONE_COUNTRY_MAP: dict[str, str] = {
    "+01": "United States",
    "+07": "Russia",
    "+20": "Egypt",
    "+27": "South Africa",
    "+30": "Greece",
    "+31": "Netherlands",
    "+32": "Belgium",
    "+33": "France",
    "+34": "Spain",
    "+36": "Hungary",
    "+39": "Italy",
    "+40": "Romania",
    "+41": "Switzerland",
    "+43": "Austria",
    "+44": "United Kingdom",
    "+45": "Denmark",
    "+46": "Sweden",
    "+47": "Norway",
    "+49": "Germany",
    "+81": "Japan",
    "+82": "South Korea",
    "+84": "Vietnam",
    "+86": "China",
    "+91": "India",
    "+52": "Mexico",
    "+55": "Brazil",
    "+54": "Argentina",
    "+56": "Chile",
    "+57": "Colombia",
    "+58": "Venezuela",
    "+51": "Peru",
    "+60": "Malaysia",
    "+61": "Australia",
    "+62": "Indonesia",
    "+63": "Philippines",
    "+64": "New Zealand",
    "+65": "Singapore",
    "+66": "Thailand",
    "+90": "Turkey",
    "+92": "Pakistan",
    "+98": "Iran",
}

# Same keys as PHONE_COUNTRY_MAP → ISO 3166-1 alpha-2 for DB and permissions.
PHONE_TWO_DIGIT_PREFIX_TO_ALPHA2: dict[str, str] = {
    "+01": "US",
    "+07": "RU",
    "+20": "EG",
    "+27": "ZA",
    "+30": "GR",
    "+31": "NL",
    "+32": "BE",
    "+33": "FR",
    "+34": "ES",
    "+36": "HU",
    "+39": "IT",
    "+40": "RO",
    "+41": "CH",
    "+43": "AT",
    "+44": "GB",
    "+45": "DK",
    "+46": "SE",
    "+47": "NO",
    "+49": "DE",
    "+81": "JP",
    "+82": "KR",
    "+84": "VN",
    "+86": "CN",
    "+91": "IN",
    "+52": "MX",
    "+55": "BR",
    "+54": "AR",
    "+56": "CL",
    "+57": "CO",
    "+58": "VE",
    "+51": "PE",
    "+60": "MY",
    "+61": "AU",
    "+62": "ID",
    "+63": "PH",
    "+64": "NZ",
    "+65": "SG",
    "+66": "TH",
    "+90": "TR",
    "+92": "PK",
    "+98": "IR",
}

# Display names when Case.detected_country_code is set but no CountryPermission row exists.
ALPHA2_ENGLISH_DISPLAY: dict[str, str] = {
    PHONE_TWO_DIGIT_PREFIX_TO_ALPHA2[k]: v for k, v in PHONE_COUNTRY_MAP.items()
}
ALPHA2_ENGLISH_DISPLAY.update(
    {
        "NG": "Nigeria",
        "IN": "India",
        "PH": "Philippines",
        "KE": "Kenya",
        "CA": "Canada",
        "DO": "Dominican Republic",
        "ZZ": "Unknown / International (Tier 4)",
    }
)


# ISO alpha-2 → alpha-3 mapping for WHO GHO API (extend as needed)
ALPHA2_TO_ALPHA3 = {
    "NG": "NGA", "IN": "IND", "PH": "PHL", "US": "USA", "GB": "GBR", "KE": "KEN",
    "ZA": "ZAF", "BD": "BGD", "PK": "PAK", "CA": "CAN", "AU": "AUS", "DE": "DEU",
    "FR": "FRA", "ES": "ESP", "IT": "ITA", "BR": "BRA", "MX": "MEX", "JP": "JPN",
    "CN": "CHN", "RU": "RUS", "GH": "GHA", "EG": "EGY", "ET": "ETH", "TZ": "TZA",
    "UG": "UGA", "RW": "RWA", "MW": "MWI", "ZM": "ZMB", "ZW": "ZWE", "AO": "AGO",
    "MZ": "MOZ", "SN": "SEN", "CI": "CIV", "CM": "CMR", "CD": "COD", "MA": "MAR",
    "DZ": "DZA", "TN": "TUN", "LY": "LBY", "SD": "SDN", "SS": "SSD", "SO": "SOM",
    "ER": "ERI", "DJ": "DJI", "TD": "TCD", "NE": "NER", "ML": "MLI", "BF": "BFA",
    "LR": "LBR", "SL": "SLE", "GM": "GMB", "GW": "GNB", "GN": "GIN", "CV": "CPV",
    "ST": "STP", "GA": "GAB", "CG": "COG", "CF": "CAF", "GQ": "GNQ", "BI": "BDI",
    "LS": "LSO", "BW": "BWA", "NA": "NAM", "SZ": "SWZ", "MG": "MDG", "MU": "MUS",
    "SC": "SYC", "KM": "COM", "NL": "NLD", "BE": "BEL", "CH": "CHE", "AT": "AUT",
    "PL": "POL", "SE": "SWE", "NO": "NOR", "DK": "DNK", "FI": "FIN", "IE": "IRL",
    "PT": "PRT", "GR": "GRC", "CZ": "CZE", "HU": "HUN", "RO": "ROU", "BG": "BGR",
    "HR": "HRV", "RS": "SRB", "SI": "SVN", "SK": "SVK", "LT": "LTU", "LV": "LVA",
    "EE": "EST", "UA": "UKR", "BY": "BLR", "MD": "MDA", "GE": "GEO", "AM": "ARM",
    "AZ": "AZE", "KZ": "KAZ", "UZ": "UZB", "TM": "TKM", "TJ": "TJK", "KG": "KGZ",
    "AF": "AFG", "IR": "IRN", "IQ": "IRQ", "SA": "SAU", "AE": "ARE", "QA": "QAT",
    "KW": "KWT", "BH": "BHR", "OM": "OMN", "YE": "YEM", "JO": "JOR", "LB": "LBN",
    "SY": "SYR", "IL": "ISR", "PS": "PSE", "TR": "TUR", "CY": "CYP", "NZ": "NZL",
    "FJ": "FJI", "PG": "PNG", "ID": "IDN", "MY": "MYS", "SG": "SGP", "TH": "THA",
    "VN": "VNM", "KH": "KHM", "LA": "LAO", "MM": "MMR", "KR": "KOR", "KP": "PRK",
    "TW": "TWN", "HK": "HKG", "MO": "MAC", "MN": "MNG", "NP": "NPL", "BT": "BTN",
    "LK": "LKA", "MV": "MDV", "BA": "BIH", "MK": "MKD", "AL": "ALB", "XK": "XKX",
    "LU": "LUX", "MT": "MLT", "IS": "ISL", "LI": "LIE", "MC": "MCO", "SM": "SMR",
    "VA": "VAT", "AD": "AND", "UY": "URY", "PY": "PRY", "BO": "BOL", "PE": "PER",
    "EC": "ECU", "CO": "COL", "VE": "VEN", "GY": "GUY", "SR": "SUR", "GF": "GUF",
    "FK": "FLK", "CL": "CHL", "AR": "ARG", "CR": "CRI", "PA": "PAN", "NI": "NIC",
    "HN": "HND", "SV": "SLV", "GT": "GTM", "BZ": "BLZ", "CU": "CUB", "JM": "JAM",
    "HT": "HTI", "DO": "DOM", "PR": "PRI", "TT": "TTO", "BB": "BRB", "BS": "BHS",
    "ZZ": "ZZZ",  # synthetic Tier 4 / unknown jurisdiction
}

# User-assigned ISO 3166-1 alpha-2 for unknown / unmapped jurisdictions (Tier 4 policy)
TIER4_JURISDICTION_CODE = "ZZ"


def normalize_phone_e164(raw: str) -> str:
    """
    Turn Twilio-style caller IDs into a single +digits string for parsing / storage.
    Ignores client: and sip: identifiers (no geographic country).
    """
    s = (raw or "").strip()
    if not s:
        return ""
    low = s.lower()
    if low.startswith("client:") or low.startswith("sip:"):
        return ""
    digits = re.sub(r"\D", "", s)
    if not digits:
        return ""
    return f"+{digits}"


def extract_two_digit_country_prefix(raw: str) -> str | None:
    """
    v2 rule: take '+' and exactly the first two digit characters after it.
    If there is no '+', use the first two digits of the string's digit run.
    """
    s = (raw or "").strip()
    if not s:
        return None
    low = s.lower()
    if low.startswith("client:") or low.startswith("sip:"):
        return None
    idx = s.find("+")
    digits_after: list[str] = []
    if idx >= 0:
        for c in s[idx + 1 :]:
            if c.isdigit():
                digits_after.append(c)
                if len(digits_after) >= 2:
                    break
    else:
        for c in s:
            if c.isdigit():
                digits_after.append(c)
                if len(digits_after) >= 2:
                    break
    if len(digits_after) < 2:
        return None
    return "+" + "".join(digits_after)


def resolve_country_via_phone_map(raw: str) -> tuple[str, str] | None:
    """
    If the two-digit key is in PHONE_COUNTRY_MAP, return (iso_alpha2, english_name).
    Otherwise None (caller should use libphonenumber).
    """
    key = extract_two_digit_country_prefix(raw)
    if not key or key not in PHONE_COUNTRY_MAP:
        return None
    a2 = PHONE_TWO_DIGIT_PREFIX_TO_ALPHA2.get(key)
    if not a2:
        return None
    return (a2, PHONE_COUNTRY_MAP[key])


def parse_phone(phone_str: str) -> dict:
    """Parse an international phone number into country info."""
    normalized = normalize_phone_e164(phone_str)
    if not normalized:
        return {"error": "Could not parse phone number"}

    try:
        parsed = phonenumbers.parse(normalized, None)
    except phonenumbers.NumberParseException:
        return {"error": "Could not parse phone number"}

    if not phonenumbers.is_possible_number(parsed):
        return {"error": "Invalid phone number"}

    cc = phonenumbers.region_code_for_number(parsed)
    if not cc:
        return {"error": "Unknown region for phone number"}
    return {
        "e164": phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.E164
        ),
        "country_code": cc,
        "country_alpha3": ALPHA2_TO_ALPHA3.get(cc, cc),
        "country_name": geocoder.description_for_number(parsed, "en") or cc,
    }


def hash_phone(e164: str) -> str:
    """One-way SHA-256 hash for phone lookup (no storing raw numbers)."""
    return hashlib.sha256(e164.encode()).hexdigest()


def get_country_permissions(db: Session, country_code: str) -> CountryPermission | None:
    """Fetch the permission row for a country."""
    return db.query(CountryPermission).filter_by(country_code=country_code).first()


def normalize_caller_jurisdiction(db: Session, caller_number: str) -> dict:
    """
    Map a Twilio From number to jurisdiction country code for permissions.

    - First: v2 PHONE_COUNTRY_MAP using '+' and the next two digits only.
    - Else: libphonenumber via parse_phone(normalized).
    - Still no match → Tier 4 (ZZ) with best-effort E.164.
    - Parsed country not in permission matrix → Tier 4 (ZZ) but preserve
      detected_country_code for audit on the Case.
    """
    raw = (caller_number or "").strip()
    normalized = normalize_phone_e164(raw)

    map_hit = resolve_country_via_phone_map(raw)
    if map_hit:
        a2, name = map_hit
        e164 = normalized if normalized else (f"+{re.sub(r'\D', '', raw)}" if raw else "")
        if not e164.startswith("+"):
            e164 = f"+{e164.lstrip('+')}" if e164 else "+00000000000"
        info = {
            "e164": e164,
            "country_code": a2,
            "country_alpha3": ALPHA2_TO_ALPHA3.get(a2, a2),
            "country_name": name,
        }
    else:
        info = parse_phone(raw)

    if "error" not in info:
        detected = info["country_code"]
        perm = get_country_permissions(db, detected)
        if perm is not None:
            return {
                "phone_info": info,
                "jurisdiction_code": detected,
                "detected_country_code": detected,
            }
        return {
            "phone_info": {
                **info,
                "country_code": TIER4_JURISDICTION_CODE,
                "country_name": info.get("country_name") or "Unknown region",
                "country_alpha3": ALPHA2_TO_ALPHA3.get(
                    TIER4_JURISDICTION_CODE, TIER4_JURISDICTION_CODE
                ),
            },
            "jurisdiction_code": TIER4_JURISDICTION_CODE,
            "detected_country_code": detected,
        }

    e164 = normalized if normalized else (
        raw if raw.startswith("+") else (f"+{re.sub(r'\D', '', raw)}" if raw else "+00000000000")
    )
    if not e164.startswith("+"):
        e164 = f"+{e164.lstrip('+')}" if e164 else "+00000000000"
    return {
        "phone_info": {
            "e164": e164,
            "country_code": TIER4_JURISDICTION_CODE,
            "country_alpha3": ALPHA2_TO_ALPHA3.get(
                TIER4_JURISDICTION_CODE, TIER4_JURISDICTION_CODE
            ),
            "country_name": "Unknown",
        },
        "jurisdiction_code": TIER4_JURISDICTION_CODE,
        "detected_country_code": None,
    }


def country_display_name_for_portal(
    case_country_code: str,
    detected_country_code: str | None,
    perms: dict[str, CountryPermission],
) -> str:
    """Human-readable country for doctor portal (e.g. Recent Cases) when jurisdiction is ZZ but phone country is known."""
    dc = (detected_country_code or "").strip().upper() or None
    if dc and dc not in ("ZZ",):
        row = perms.get(dc)
        if row:
            return row.country_name
        return ALPHA2_ENGLISH_DISPLAY.get(dc, dc)
    cc = (case_country_code or "").strip().upper()
    row = perms.get(cc)
    if row:
        return row.country_name
    return cc or "Unknown"


def check_teleconsult_allowed(db: Session, country_code: str) -> dict:
    """Return whether teleconsult is allowed and relevant disclaimers."""
    perm = get_country_permissions(db, country_code)
    if perm is None:
        return {
            "allowed": False,
            "reason": f"Country {country_code} not in permission matrix",
            "disclaimer": None,
        }
    return {
        "allowed": perm.allows_teleconsult,
        "permission_tier": perm.permission_tier,
        "requires_local_doctor": perm.requires_local_doctor,
        "allows_ai_triage": perm.allows_ai_triage,
        "allows_prescription": perm.allows_prescription,
        "disclaimer": perm.disclaimer_text,
        "data_law": perm.data_law,
        "max_retention_days": perm.max_retention_days,
    }


def get_or_create_patient(
    db: Session, phone_e164: str, country_code: str, language: str = "en"
) -> Patient:
    """Find existing patient by phone hash or create new one."""
    ph = hash_phone(phone_e164)
    patient = db.query(Patient).filter_by(phone_hash=ph).first()
    if patient:
        return patient
    patient = Patient(
        phone_hash=ph,
        country_code=country_code,
        language=language,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


# ── Seed data for the three target countries ──
SEED_COUNTRIES = [
    {
        "country_code": "ZZ",
        "country_name": "Unknown / International (Tier 4)",
        "permission_tier": "advice_only",
        "country_tier": 4,
        "allows_teleconsult": True,
        "allows_ai_triage": True,
        "allows_prescription": False,
        "requires_local_doctor": True,
        "cross_border_allowed": False,
        "data_residency_required": False,
        "max_retention_days": 30,
        "regulatory_basis": "Default guidance-only policy for unmapped jurisdictions",
        "data_law": "Operator privacy policy; no specific national telemedicine license claimed",
        "disclaimer_text": (
            "This service provides general health information only — not a medical diagnosis "
            "or prescription. A clinician may review your case when available. "
            "If this is an emergency, contact your local emergency number or go to the nearest hospital."
        ),
        "notes": "Synthetic jurisdiction row for parse failures and countries outside the matrix.",
    },
    {
        "country_code": "NG",
        "country_name": "Nigeria",
        "permission_tier": "limited",
        "country_tier": 2,
        "allows_teleconsult": True,
        "allows_ai_triage": True,
        "allows_prescription": False,
        "requires_local_doctor": True,
        "cross_border_allowed": False,
        "data_residency_required": True,
        "max_retention_days": 90,
        "regulatory_basis": "MDCN Code of Ethics Rule 22; no dedicated telemedicine law",
        "data_law": "Nigeria Data Protection Act (NDPA) 2023",
        "disclaimer_text": (
            "This service provides health guidance only — not a medical diagnosis. "
            "A locally-licensed Nigerian doctor will review your case. "
            "If this is an emergency, call 112 or go to the nearest hospital."
        ),
        "notes": "Must register with CAC. Lagos requires HEFAMAA registration.",
    },
    {
        "country_code": "IN",
        "country_name": "India",
        "permission_tier": "regulated",
        "country_tier": 1,
        "allows_teleconsult": True,
        "allows_ai_triage": True,
        "allows_prescription": False,
        "requires_local_doctor": True,
        "cross_border_allowed": False,
        "data_residency_required": True,
        "max_retention_days": 90,
        "regulatory_basis": "Telemedicine Practice Guidelines 2020 (Appendix 5, IMC Regs)",
        "data_law": "IT Act 2000 + Digital Personal Data Protection Act 2023",
        "disclaimer_text": (
            "This service provides health guidance only — not a medical diagnosis. "
            "A locally-licensed Indian doctor will review your case. "
            "If this is an emergency, call 112 or go to the nearest hospital."
        ),
        "notes": "First consult can be remote. Patient-initiated = implied consent.",
    },
    {
        "country_code": "PH",
        "country_name": "Philippines",
        "permission_tier": "emerging",
        "country_tier": 3,
        "allows_teleconsult": True,
        "allows_ai_triage": True,
        "allows_prescription": False,
        "requires_local_doctor": True,
        "cross_border_allowed": False,
        "data_residency_required": False,
        "max_retention_days": 90,
        "regulatory_basis": "DOH-DILG-PHIC JAO 2021-0001; no dedicated law",
        "data_law": "Data Privacy Act 2012 (RA 10173)",
        "disclaimer_text": (
            "This service provides health guidance only — not a medical diagnosis. "
            "A PRC-licensed Filipino doctor will review your case. "
            "If this is an emergency, call 911 or go to the nearest hospital."
        ),
        "notes": "PRC-licensed physicians only. Informed consent required.",
    },
    {
        "country_code": "KE",
        "country_name": "Kenya",
        "permission_tier": "emerging",
        "country_tier": 3,
        "allows_teleconsult": True,
        "allows_ai_triage": True,
        "allows_prescription": False,
        "requires_local_doctor": True,
        "cross_border_allowed": False,
        "data_residency_required": False,
        "max_retention_days": 90,
        "regulatory_basis": "Kenya Health Act 2017; no dedicated telemedicine law",
        "data_law": "Data Protection Act 2019",
        "disclaimer_text": (
            "This service provides health guidance only — not a medical diagnosis. "
            "A locally-licensed Kenyan doctor will review your case. "
            "If this is an emergency, call 999 or go to the nearest hospital."
        ),
        "notes": "KMPDC-licensed physicians only. eHealth Strategy 2016-2030 supports telemedicine.",
    },
]


def seed_country_permissions(db: Session):
    """Insert seed country permission rows if they don't exist."""
    for data in SEED_COUNTRIES:
        existing = db.query(CountryPermission).filter_by(
            country_code=data["country_code"]
        ).first()
        if not existing:
            db.add(CountryPermission(**data))
    db.commit()
