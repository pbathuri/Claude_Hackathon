"""Request ID middleware for traceability."""
import uuid
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("observability")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:12])
        request.state.request_id = request_id

        start = time.time()
        response = await call_next(request)
        elapsed = time.time() - start

        response.headers["X-Request-ID"] = request_id

        logger.info(
            "request_id=%s method=%s path=%s status=%s elapsed=%.3fs",
            request_id, request.method, request.url.path,
            response.status_code, elapsed,
        )

        return response
