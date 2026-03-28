"""
Browser Web Speech API transcript persistence.

Uses Redis when REDIS_URL is set; otherwise an in-process dict (single-worker dev only).
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from config import BROWSER_STT_TTL_SECONDS, REDIS_URL

logger = logging.getLogger(__name__)

_KEY_PREFIX = "caller:browser_stt:"

_redis = None
_memory: dict[str, dict[str, Any]] = {}


def _get_redis():
    global _redis
    if _redis is False:
        return None
    if _redis is not None:
        return _redis
    if not REDIS_URL:
        _redis = False
        return None
    try:
        import redis as redis_lib

        _redis = redis_lib.from_url(REDIS_URL, decode_responses=True)
        _redis.ping()
        logger.info("[Browser STT] Redis connected")
        return _redis
    except Exception as exc:
        logger.warning("[Browser STT] Redis unavailable, using in-memory store: %s", exc)
        _redis = False
        return None


def push_segment(
    case_id: str,
    text: str,
    *,
    lang: str = "",
    is_final: bool = True,
) -> dict[str, Any]:
    """Append a transcript segment and return the full stored document."""
    if not case_id or not text.strip():
        return get_state(case_id)

    now = time.time()
    segment = {
        "text": text.strip(),
        "t": now,
        "lang": lang or "",
        "is_final": is_final,
    }

    r = _get_redis()
    key = _KEY_PREFIX + case_id

    if r is not None:
        raw = r.get(key)
        data = json.loads(raw) if raw else _empty_state(case_id)
        data["segments"].append(segment)
        data["full_text"] = _join_segments(data["segments"])
        data["updated_at"] = now
        ttl = max(60, BROWSER_STT_TTL_SECONDS)
        r.setex(key, ttl, json.dumps(data))
        return data

    data = _memory.get(case_id) or _empty_state(case_id)
    data["segments"].append(segment)
    data["full_text"] = _join_segments(data["segments"])
    data["updated_at"] = now
    _memory[case_id] = data
    return data


def _empty_state(case_id: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "segments": [],
        "full_text": "",
        "updated_at": None,
    }


def _join_segments(segments: list[dict]) -> str:
    return " ".join(s["text"] for s in segments if s.get("text"))


def get_state(case_id: str) -> dict[str, Any]:
    if not case_id:
        return _empty_state("")

    r = _get_redis()
    key = _KEY_PREFIX + case_id
    if r is not None:
        raw = r.get(key)
        if raw:
            return json.loads(raw)
        return _empty_state(case_id)

    return _memory.get(case_id) or _empty_state(case_id)


def clear_state(case_id: str) -> None:
    if not case_id:
        return
    r = _get_redis()
    if r is not None:
        r.delete(_KEY_PREFIX + case_id)
    else:
        _memory.pop(case_id, None)
