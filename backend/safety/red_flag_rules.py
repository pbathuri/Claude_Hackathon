"""
Layered clinical safety engine for emergency detection.

Three detection tiers:
1. Exact keyword match (fastest, most reliable)
2. Pattern/phrase match (handles paraphrases)
3. Semantic similarity fallback (catches colloquial descriptions)

Design principle: ZERO false negatives on sentinel symptoms.
False positives are acceptable — better to over-triage than miss an emergency.
"""
import re
import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RedFlagSeverity(str, Enum):
    IMMEDIATE = "immediate"     # Route to emergency services NOW
    URGENT = "urgent"           # Escalate to next available doctor
    WARNING = "warning"         # Flag for clinician attention


@dataclass
class RedFlagResult:
    is_emergency: bool = False
    severity: RedFlagSeverity = RedFlagSeverity.WARNING
    flags: list[dict] = field(default_factory=list)
    action: str = "CONTINUE_INTAKE"
    emergency_numbers: list[str] = field(default_factory=list)

    @property
    def should_complete(self) -> bool:
        return self.is_emergency or self.severity == RedFlagSeverity.IMMEDIATE

    def add_flag(self, category: str, matched_text: str, severity: RedFlagSeverity, rule: str):
        self.flags.append({
            "category": category,
            "matched_text": matched_text,
            "severity": severity.value,
            "rule": rule,
            # Backward-compat keys used by caller.py and tests
            "flag": matched_text,
            "layer": category,
            "confidence": 0.95 if severity == RedFlagSeverity.IMMEDIATE else 0.80,
        })
        if severity == RedFlagSeverity.IMMEDIATE:
            self.is_emergency = True
            self.severity = RedFlagSeverity.IMMEDIATE
            self.action = "ROUTE_TO_EMERGENCY_SERVICES"
        elif severity == RedFlagSeverity.URGENT and self.severity != RedFlagSeverity.IMMEDIATE:
            self.severity = RedFlagSeverity.URGENT
            self.action = "ESCALATE_TO_DOCTOR"


# ── Tier 1: Exact keywords (canonical list — single source of truth) ─────

EMERGENCY_KEYWORDS_IMMEDIATE = [
    "chest pain", "chest tightness", "heart attack",
    "can't breathe", "cannot breathe", "difficulty breathing", "struggling to breathe",
    "stopped breathing", "not breathing",
    "stroke", "face drooping", "arm weakness", "slurred speech",
    "unconscious", "unresponsive", "passed out", "collapsed",
    "severe bleeding", "bleeding heavily", "blood everywhere", "hemorrhage",
    "seizure", "convulsions", "fitting",
    "suicidal", "want to die", "kill myself", "self-harm", "hurting myself",
    "anaphylaxis", "throat swelling", "throat closing", "allergic reaction severe",
    "poisoning", "overdose", "swallowed poison",
    "choking", "can't swallow",
]

EMERGENCY_KEYWORDS_URGENT = [
    "high fever", "very high fever", "burning up",
    "severe pain", "worst pain", "unbearable pain", "pain 10 out of 10",
    "coughing blood", "blood in vomit", "vomiting blood",
    "blood in stool", "black stool", "bloody stool",
    "sudden vision loss", "sudden blindness",
    "sudden weakness one side", "numbness one side",
    "severe headache worst ever", "thunderclap headache",
    "stiff neck with fever", "neck stiffness fever",
    "confusion", "disoriented", "altered consciousness",
    "pregnant bleeding", "pregnancy bleeding", "vaginal bleeding pregnant",
    "severe dehydration", "not urinating", "no urine output",
    "infant not feeding", "baby not breathing well", "child limp",
]

# ── Tier 2: Pattern matching (catches paraphrases and colloquial) ────────

EMERGENCY_PATTERNS = [
    (r"can.?t\s+breath", RedFlagSeverity.IMMEDIATE, "breathing_difficulty"),
    (r"struggling\s+to\s+breath", RedFlagSeverity.IMMEDIATE, "breathing_difficulty"),
    (r"hard\s+to\s+breath", RedFlagSeverity.IMMEDIATE, "breathing_difficulty"),
    (r"pain\s+in\s+(my\s+)?chest", RedFlagSeverity.IMMEDIATE, "chest_pain"),
    (r"my\s+chest\s+(hurts|is\s+tight|feels\s+heavy)", RedFlagSeverity.IMMEDIATE, "chest_pain"),
    (r"(want|going)\s+to\s+(die|kill|end)", RedFlagSeverity.IMMEDIATE, "suicidal_ideation"),
    (r"(hurt|harm|cut|injure)\s+(myself|self)", RedFlagSeverity.IMMEDIATE, "self_harm"),
    (r"can.?t\s+(move|feel)\s+(my\s+)?(arm|leg|side)", RedFlagSeverity.URGENT, "stroke_signs"),
    (r"face\s+(drooping|numb|droop)", RedFlagSeverity.URGENT, "stroke_signs"),
    (r"blood\s+(coming|from|in)\s+(my\s+)?(mouth|nose|ear|stool|urine)", RedFlagSeverity.URGENT, "bleeding"),
    (r"fever\s+(of\s+)?(10[4-9]|1[1-9]\d|[4-9]\d\s*c|40|41|42)", RedFlagSeverity.URGENT, "high_fever"),
    (r"(baby|child|infant)\s+(not\s+)?(breathing|moving|responding|feeding)", RedFlagSeverity.IMMEDIATE, "pediatric_emergency"),
    (r"pregnant\s+and\s+(bleeding|severe\s+pain|headache)", RedFlagSeverity.IMMEDIATE, "obstetric_emergency"),
]

# ── Multilingual emergency patterns ──────────────────────────────────────

MULTILINGUAL_EMERGENCY_PATTERNS = {
    "es": [
        (r"dolor\s+(de\s+)?pecho", RedFlagSeverity.IMMEDIATE, "chest_pain_es"),
        (r"no\s+puedo\s+respirar", RedFlagSeverity.IMMEDIATE, "breathing_es"),
        (r"ataque\s+al?\s+coraz[oó]n", RedFlagSeverity.IMMEDIATE, "heart_attack_es"),
        (r"derrame\s+cerebral", RedFlagSeverity.IMMEDIATE, "stroke_es"),
        (r"inconsciente", RedFlagSeverity.IMMEDIATE, "unconscious_es"),
        (r"suicid", RedFlagSeverity.IMMEDIATE, "suicidal_es"),
        (r"sangrado\s+severo", RedFlagSeverity.IMMEDIATE, "bleeding_es"),
    ],
    "fr": [
        (r"douleur\s+(à la\s+)?poitrine", RedFlagSeverity.IMMEDIATE, "chest_pain_fr"),
        (r"ne\s+peut\s+pas\s+respirer", RedFlagSeverity.IMMEDIATE, "breathing_fr"),
        (r"crise\s+cardiaque", RedFlagSeverity.IMMEDIATE, "heart_attack_fr"),
        (r"accident\s+vasculaire", RedFlagSeverity.IMMEDIATE, "stroke_fr"),
        (r"inconscient", RedFlagSeverity.IMMEDIATE, "unconscious_fr"),
        (r"suicid", RedFlagSeverity.IMMEDIATE, "suicidal_fr"),
        (r"h[eé]morragie", RedFlagSeverity.IMMEDIATE, "bleeding_fr"),
    ],
    "hi": [
        (r"छाती\s*में\s*दर्द", RedFlagSeverity.IMMEDIATE, "chest_pain_hi"),
        (r"सांस\s*नहीं", RedFlagSeverity.IMMEDIATE, "breathing_hi"),
        (r"दिल\s*का\s*दौरा", RedFlagSeverity.IMMEDIATE, "heart_attack_hi"),
        (r"बेहोश", RedFlagSeverity.IMMEDIATE, "unconscious_hi"),
        (r"आत्महत्या", RedFlagSeverity.IMMEDIATE, "suicidal_hi"),
        (r"खून\s*बह", RedFlagSeverity.IMMEDIATE, "bleeding_hi"),
    ],
    "ar": [
        (r"ألم.*صدر", RedFlagSeverity.IMMEDIATE, "chest_pain_ar"),
        (r"لا.*أستطيع.*التنفس", RedFlagSeverity.IMMEDIATE, "breathing_ar"),
        (r"نوبة.*قلبية", RedFlagSeverity.IMMEDIATE, "heart_attack_ar"),
        (r"فاقد.*الوعي", RedFlagSeverity.IMMEDIATE, "unconscious_ar"),
        (r"انتحار", RedFlagSeverity.IMMEDIATE, "suicidal_ar"),
        (r"نزيف.*حاد", RedFlagSeverity.IMMEDIATE, "bleeding_ar"),
    ],
    "sw": [
        (r"maumivu\s+ya\s+kifua", RedFlagSeverity.IMMEDIATE, "chest_pain_sw"),
        (r"siwezi\s+kupumua", RedFlagSeverity.IMMEDIATE, "breathing_sw"),
        (r"shambulio\s+la\s+moyo", RedFlagSeverity.IMMEDIATE, "heart_attack_sw"),
        (r"kupoteza\s+fahamu", RedFlagSeverity.IMMEDIATE, "unconscious_sw"),
        (r"kujiua", RedFlagSeverity.IMMEDIATE, "suicidal_sw"),
    ],
    "zh": [
        (r"胸痛", RedFlagSeverity.IMMEDIATE, "chest_pain_zh"),
        (r"无法呼吸", RedFlagSeverity.IMMEDIATE, "breathing_zh"),
        (r"心脏病", RedFlagSeverity.IMMEDIATE, "heart_attack_zh"),
        (r"中风", RedFlagSeverity.IMMEDIATE, "stroke_zh"),
        (r"昏迷", RedFlagSeverity.IMMEDIATE, "unconscious_zh"),
        (r"自杀", RedFlagSeverity.IMMEDIATE, "suicidal_zh"),
        (r"大出血", RedFlagSeverity.IMMEDIATE, "bleeding_zh"),
    ],
    "ha": [
        (r"ciwon\s+kirji", RedFlagSeverity.IMMEDIATE, "chest_pain_ha"),
        (r"ba.*zan.*iya.*numfashi", RedFlagSeverity.IMMEDIATE, "breathing_ha"),
        (r"bugun\s+zuciya", RedFlagSeverity.IMMEDIATE, "heart_attack_ha"),
    ],
}


def detect_red_flags(
    text: str,
    country_code: str = "",
    *,
    language: str = "en",
    english_text: str | None = None,
    kg_context: dict | None = None,
) -> RedFlagResult:
    """
    Run layered emergency detection on patient text.
    Returns structured result with all flags found and recommended action.

    Accepts both new-style (country_code) and legacy (language/english_text/kg_context)
    parameters for backward compatibility.
    """
    result = RedFlagResult()
    text_lower = text.lower().strip()

    if not text_lower:
        return result

    # Determine which text to run English checks against
    en_text = english_text if english_text else text
    en_lower = en_text.lower().strip()

    # Tier 1: Exact keyword matching (on English text)
    for keyword in EMERGENCY_KEYWORDS_IMMEDIATE:
        if keyword in en_lower:
            result.add_flag("keyword", keyword, RedFlagSeverity.IMMEDIATE, f"exact_match:{keyword}")

    for keyword in EMERGENCY_KEYWORDS_URGENT:
        if keyword in en_lower:
            result.add_flag("keyword", keyword, RedFlagSeverity.URGENT, f"exact_match:{keyword}")

    # Tier 2: English pattern matching (on English text)
    for pattern, severity, category in EMERGENCY_PATTERNS:
        match = re.search(pattern, en_lower)
        if match:
            result.add_flag("pattern", match.group(), severity, f"pattern:{category}")

    # Tier 2b: Multilingual pattern matching (on original text)
    if language != "en":
        ml_patterns = MULTILINGUAL_EMERGENCY_PATTERNS.get(language, [])
        for pattern, severity, category in ml_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result.add_flag("multilingual_pattern", match.group(), severity, f"multilingual:{category}")

    # Tier 3: Knowledge graph activation check
    if kg_context:
        for cond in kg_context.get("activated_conditions", []):
            if cond.get("is_emergency") and cond.get("activation_score", 0) > 0.3:
                result.add_flag(
                    "knowledge_graph",
                    f"kg:{cond['condition']}",
                    RedFlagSeverity.IMMEDIATE,
                    f"kg_activation:{cond['condition']}",
                )

    # Add emergency numbers if emergency detected
    if result.is_emergency:
        result.emergency_numbers = _get_emergency_numbers(country_code)

    # Deduplicate flags by category+severity
    seen = set()
    unique_flags = []
    for f in result.flags:
        key = f"{f['category']}:{f['severity']}"
        if key not in seen:
            seen.add(key)
            unique_flags.append(f)
    result.flags = unique_flags

    if result.flags:
        logger.info("[Safety] Red flags detected: %d flags, severity=%s, action=%s",
                    len(result.flags), result.severity.value, result.action)

    return result


def _get_emergency_numbers(country_code: str) -> list[str]:
    NUMBERS = {
        "NG": ["112", "199"],
        "IN": ["112", "108"],
        "KE": ["999", "112"],
        "PH": ["911", "143"],
        "US": ["911"],
        "GB": ["999", "112"],
    }
    return NUMBERS.get(country_code, ["112", "911"])


def check_emergency_keywords(text: str) -> bool:
    """Legacy compatibility wrapper."""
    result = detect_red_flags(text)
    return result.is_emergency or result.severity == RedFlagSeverity.URGENT
