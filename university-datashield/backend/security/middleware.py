# backend/security/middleware.py
"""
Production Security & Hardening Middlewares for Phase 11.
Provides correlation IDs, strict security response headers, and payload size bounds.
"""

from __future__ import annotations
import uuid
import time
import logging
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from config import settings

logger = logging.getLogger("datashield.security")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Appends standard OWASP recommended security headers and correlation identifiers.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Correlation ID
        request_id = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:10]}"
        request.state.request_id = request_id

        start_time = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Inject Security Headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"
        response.headers["X-DataShield-Environment"] = settings.ENVIRONMENT

        # Safe structured logging without personal data
        if not request.url.path.startswith("/health") and not request.url.path.startswith("/ready"):
            logger.info(
                "request_id=%s method=%s path=%s status=%d duration_ms=%.2f",
                request_id,
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )

        return response


class PayloadSizeLimiterMiddleware(BaseHTTPMiddleware):
    """
    Guards against denial-of-service via oversized dataset payloads.
    Enforces MAX_UPLOAD_SIZE_MB.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        content_length_str = request.headers.get("content-length")

        if content_length_str:
            try:
                content_length = int(content_length_str)
                if content_length > max_bytes:
                    logger.warning(
                        "Payload size exceeded: %d bytes (limit: %d bytes)",
                        content_length,
                        max_bytes,
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error_code": "PAYLOAD_TOO_LARGE",
                            "message": f"Request body exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB.",
                            "max_size_mb": settings.MAX_UPLOAD_SIZE_MB,
                        },
                    )
            except ValueError:
                pass

        return await call_next(request)
