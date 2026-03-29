"""
Unified session storage: Redis in production, in-memory fallback for local dev.

Key prefixes:
  twilio:sess:{call_sid}     — Twilio voice turn state (JSON), TTL 1h
  case:lang:{case_id}       — detected language
  case:stale:{case_id}      — stale turn counter (int as JSON)
  case:ai_hist:{case_id}    — list of prior assistant messages (JSON)
  case:nav:{case_id}        — ConversationNavigator snapshot (JSON), TTL 24h
  tts:{hash}                — MP3 bytes
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from config import REDIS_URL

logger = logging.getLogger(__name__)

_TTL_TWILIO_SESSION = 3600
_TTL_CASE = 86400
_TTL_TTS = 86400

_memory_json: dict[str, Any] = {}
_memory_bytes: dict[str, bytes] = {}
_redis = None


def _client():
    global _redis
    if _redis is False:
        return None
    if _redis is not None:
        return _redis
    if not REDIS_URL:
        logger.info("REDIS_URL not set — using in-memory session store")
        _redis = False
        return None
    try:
        import redis as redis_lib

        _redis = redis_lib.from_url(REDIS_URL, decode_responses=False, socket_connect_timeout=2)
        _redis.ping()
        logger.info("Session store using Redis")
        return _redis
    except Exception as exc:
        logger.warning("Redis connection failed — in-memory fallback: %s", exc)
        _redis = False
        return None


def _key(s: str) -> bytes:
    return s.encode("utf-8")


def set_json(key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
    r = _client()
    payload = json.dumps(value, default=str).encode("utf-8")
    if r is None:
        _memory_json[key] = value
        return
    k = _key(key)
    if ttl_seconds:
        r.setex(k, ttl_seconds, payload)
    else:
        r.set(k, payload)


def get_json(key: str) -> Any | None:
    r = _client()
    if r is None:
        return _memory_json.get(key)
    raw = r.get(_key(key))
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def delete(key: str) -> None:
    r = _client()
    if r is None:
        _memory_json.pop(key, None)
        _memory_bytes.pop(key, None)
        return
    r.delete(_key(key))


def set_bytes(key: str, value: bytes, ttl_seconds: Optional[int] = None) -> None:
    r = _client()
    if r is None:
        _memory_bytes[key] = value
        return
    k = _key(key)
    if ttl_seconds:
        r.setex(k, ttl_seconds, value)
    else:
        r.set(k, value)


def get_bytes(key: str) -> bytes | None:
    r = _client()
    if r is None:
        return _memory_bytes.get(key)
    raw = r.get(_key(key))
    return raw if raw else None


# --- Twilio call session ---

def twilio_session_set(call_sid: str, data: dict) -> None:
    set_json(f"twilio:sess:{call_sid}", data, _TTL_TWILIO_SESSION)


def twilio_session_get(call_sid: str) -> dict | None:
    val = get_json(f"twilio:sess:{call_sid}")
    return val if isinstance(val, dict) else None


def twilio_session_delete(call_sid: str) -> None:
    delete(f"twilio:sess:{call_sid}")


# --- Per-case caller / web session fields ---

def case_language_set(case_id: str, lang: str) -> None:
    set_json(f"case:lang:{case_id}", lang, _TTL_CASE)


def case_language_get(case_id: str) -> str | None:
    v = get_json(f"case:lang:{case_id}")
    return str(v) if v is not None else None


def case_language_delete(case_id: str) -> None:
    delete(f"case:lang:{case_id}")


def case_stale_set(case_id: str, n: int) -> None:
    set_json(f"case:stale:{case_id}", n, _TTL_CASE)


def case_stale_get(case_id: str) -> int:
    v = get_json(f"case:stale:{case_id}")
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def case_stale_delete(case_id: str) -> None:
    delete(f"case:stale:{case_id}")


def case_ai_history_get(case_id: str) -> list[str]:
    v = get_json(f"case:ai_hist:{case_id}")
    if isinstance(v, list):
        return [str(x) for x in v]
    return []


def case_ai_history_append(case_id: str, message: str) -> None:
    hist = case_ai_history_get(case_id)
    hist.append(message)
    set_json(f"case:ai_hist:{case_id}", hist, _TTL_CASE)


def case_ai_history_delete(case_id: str) -> None:
    delete(f"case:ai_hist:{case_id}")


def case_nav_set(case_id: str, snapshot: dict) -> None:
    set_json(f"case:nav:{case_id}", snapshot, _TTL_CASE)


def case_nav_get(case_id: str) -> dict | None:
    v = get_json(f"case:nav:{case_id}")
    return v if isinstance(v, dict) else None


def case_nav_delete(case_id: str) -> None:
    delete(f"case:nav:{case_id}")


def case_clear_all(case_id: str) -> None:
    case_language_delete(case_id)
    case_stale_delete(case_id)
    case_ai_history_delete(case_id)
    case_nav_delete(case_id)


# --- TTS cache ---

def tts_cache_get(cache_key: str) -> bytes | None:
    return get_bytes(f"tts:{cache_key}")


def tts_cache_set(cache_key: str, audio: bytes) -> None:
    set_bytes(f"tts:{cache_key}", audio, _TTL_TTS)
