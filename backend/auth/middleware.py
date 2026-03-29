"""
Authentication middleware scaffold.

Supports three modes:
- demo: no auth required (DEMO_MODE=1)
- api_key: X-API-Key header validated against known keys
- jwt: Bearer token validation (future)
"""
import os
import hashlib
import logging
from functools import wraps
from fastapi import Request, HTTPException, Depends
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

DEMO_MODE = os.environ.get("DEMO_MODE", "1") == "1"

_VALID_API_KEYS = set()
_VALID_API_KEY_HASHES = set()


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _load_api_keys():
    global _VALID_API_KEYS, _VALID_API_KEY_HASHES
    keys_str = os.environ.get("API_KEYS", "")
    if keys_str:
        _VALID_API_KEYS = {k.strip() for k in keys_str.split(",") if k.strip()}
    hashes_str = os.environ.get("API_KEY_HASHES", "")
    if hashes_str:
        _VALID_API_KEY_HASHES = {h.strip().lower() for h in hashes_str.split(",") if h.strip()}


_load_api_keys()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_actor(request: Request, api_key: str = Depends(api_key_header)) -> dict:
    """Extract and validate the current actor from the request.

    Returns dict with: actor_id, actor_type, roles
    In demo mode, returns a default actor.
    """
    if DEMO_MODE:
        return {
            "actor_id": "demo-user",
            "actor_type": "system",
            "roles": ["admin", "doctor", "caller_service"],
            "demo_mode": True,
        }

    if api_key:
        if api_key in _VALID_API_KEYS:
            return {
                "actor_id": f"apikey:{api_key[:8]}",
                "actor_type": "service",
                "roles": ["caller_service"],
                "demo_mode": False,
            }
        key_hash = _sha256_hex(api_key).lower()
        if key_hash in _VALID_API_KEY_HASHES:
            return {
                "actor_id": "apikey:hashed",
                "actor_type": "service",
                "roles": ["caller_service"],
                "demo_mode": False,
            }

    doctor_id = request.headers.get("X-Doctor-ID")
    if doctor_id:
        return {
            "actor_id": doctor_id,
            "actor_type": "doctor",
            "roles": ["doctor"],
            "demo_mode": False,
        }

    if not DEMO_MODE:
        raise HTTPException(status_code=401, detail="Authentication required")

    return {"actor_id": "anonymous", "actor_type": "unknown", "roles": [], "demo_mode": True}


def require_role(role: str):
    """Dependency that checks actor has the required role."""
    async def check(actor: dict = Depends(get_current_actor)):
        if actor.get("demo_mode"):
            return actor
        if role not in actor.get("roles", []):
            raise HTTPException(status_code=403, detail=f"Role '{role}' required")
        return actor
    return check
