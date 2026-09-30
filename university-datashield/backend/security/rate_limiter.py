# backend/security/rate_limiter.py
"""
Sliding-window in-memory rate limiter for Phase 11.
Protects security-critical endpoints (/scan, /pipeline/validate, /pipeline/publish, /auth)
against brute-force and resource exhaustion attacks.
"""

from __future__ import annotations
import time
from collections import defaultdict
from typing import Dict, List, Tuple
from fastapi import Request, HTTPException

from config import settings


class RateLimiter:
    def __init__(self, requests_per_minute: int = 60, enabled: bool = True):
        self.requests_per_minute = requests_per_minute
        self.enabled = enabled
        self._requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, client_key: str, limit: int | None = None, window_seconds: int = 60) -> Tuple[bool, int]:
        """
        Check whether client request is allowed under current sliding window.
        Returns: (is_allowed, retry_after_seconds)
        """
        if not self.enabled:
            return True, 0

        now = time.time()
        cutoff = now - window_seconds
        req_limit = limit or self.requests_per_minute

        # Clean old timestamps
        timestamps = self._requests[client_key]
        valid_timestamps = [t for t in timestamps if t > cutoff]
        self._requests[client_key] = valid_timestamps

        if len(valid_timestamps) >= req_limit:
            # Exceeded limit; compute retry after
            oldest = valid_timestamps[0]
            retry_after = max(1, int(cutoff - oldest + window_seconds))
            return False, retry_after

        # Record this request
        self._requests[client_key].append(now)
        return True, 0

    def reset(self) -> None:
        """Clear all tracked request history (useful for automated testing)."""
        self._requests.clear()


limiter = RateLimiter(
    requests_per_minute=settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
    enabled=settings.RATE_LIMIT_ENABLED,
)


async def rate_limit_dependency(request: Request) -> None:
    """FastAPI dependency for applying rate limiting to endpoints."""
    if not settings.RATE_LIMIT_ENABLED:
        return

    # Client identifier: forwarded header, client host, or authorization token
    client_ip = request.client.host if request.client else "127.0.0.1"
    auth_header = request.headers.get("Authorization", "")
    client_key = f"{client_ip}:{auth_header[:16]}" if auth_header else client_ip

    allowed, retry_after = limiter.is_allowed(client_key)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error_code": "RATE_LIMIT_EXCEEDED",
                "message": f"Rate limit exceeded. Maximum {settings.RATE_LIMIT_REQUESTS_PER_MINUTE} requests per minute.",
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )
