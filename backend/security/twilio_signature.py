"""Validate Twilio webhook signatures (X-Twilio-Signature)."""
import logging
import os

from fastapi import HTTPException, Request

from config import TWILIO_AUTH_TOKEN

logger = logging.getLogger(__name__)


def _normalize_public_base(raw: str) -> str:
    """Ensure https:// origin; users often paste host only."""
    s = raw.strip().rstrip("/")
    if not s:
        return ""
    if not s.startswith(("http://", "https://")):
        s = "https://" + s.lstrip("/")
    return s


async def verify_twilio_webhook(request: Request) -> None:
    """
    Ensures POST is from Twilio. Set SKIP_TWILIO_SIGNATURE=1 for local testing.
    If PUBLIC_BASE_URL is set, it is used as the webhook URL (must match Twilio console).
    """
    if os.environ.get("SKIP_TWILIO_SIGNATURE", "").lower() in ("1", "true", "yes"):
        return
    if not TWILIO_AUTH_TOKEN:
        logger.warning("TWILIO_AUTH_TOKEN not set — skipping signature validation")
        return

    try:
        from twilio.request_validator import RequestValidator
    except ImportError:
        logger.warning("twilio package not installed — skipping signature validation")
        return

    form = await request.form()
    params = {k: str(v) for k, v in form.items()}
    signature = request.headers.get("X-Twilio-Signature") or ""
    public_base = _normalize_public_base(os.environ.get("PUBLIC_BASE_URL", ""))
    path = request.url.path
    if request.url.query:
        path = f"{path}?{request.url.query}"
    url = f"{public_base}{path}" if public_base else str(request.url)

    if RequestValidator(TWILIO_AUTH_TOKEN).validate(url, params, signature):
        return
    raise HTTPException(status_code=403, detail="Invalid Twilio signature")
