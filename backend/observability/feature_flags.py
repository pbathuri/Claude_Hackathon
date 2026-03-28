"""Feature flags for safe deployment and demo/production separation."""
import os

class FeatureFlags:
    DEMO_MODE = os.environ.get("DEMO_MODE", "1") == "1"
    ENABLE_KG = os.environ.get("ENABLE_KG", "1") == "1"
    ENABLE_EXTERNAL_APIS = os.environ.get("ENABLE_EXTERNAL_APIS", "1") == "1"
    ENABLE_TTS = os.environ.get("ENABLE_TTS", "1") == "1"
    ENABLE_BACKGROUND_JOBS = os.environ.get("ENABLE_BACKGROUND_JOBS", "1") == "1"
    ENABLE_MOCK_FALLBACK = os.environ.get("ENABLE_MOCK_FALLBACK", "0") == "1"
    KILL_SWITCH_PATIENT_AI = os.environ.get("KILL_SWITCH_PATIENT_AI", "0") == "1"
    
    @classmethod
    def summary(cls) -> dict:
        return {k: v for k, v in vars(cls).items() if not k.startswith("_") and isinstance(v, bool)}
