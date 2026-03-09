"""Simple Redis-backed rate limiting helpers."""

import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from security import extract_client_ip

try:
    import redis
except Exception:  # pragma: no cover
    redis = None


class RateLimiter:
    def __init__(self) -> None:
        self.enabled = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() in {"1", "true", "yes"}
        self.redis_url = os.environ.get("RATE_LIMIT_REDIS_URL", "redis://localhost:6379/0")
        self._redis = None
        self._memory: dict[str, deque[float]] = defaultdict(deque)
        if redis is not None:
            try:
                self._redis = redis.from_url(self.redis_url, decode_responses=True)
                self._redis.ping()
            except Exception:
                self._redis = None

    def enforce(self, key: str, limit: int, window_seconds: int) -> None:
        if not self.enabled:
            return
        if self._redis is not None:
            bucket = int(time.time() // window_seconds)
            rk = f"ratelimit:{key}:{window_seconds}:{bucket}"
            count = int(self._redis.incr(rk))
            if count == 1:
                self._redis.expire(rk, window_seconds + 2)
            if count > limit:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            return

        now = time.time()
        dq = self._memory[key]
        threshold = now - window_seconds
        while dq and dq[0] <= threshold:
            dq.popleft()
        if len(dq) >= limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        dq.append(now)


rate_limiter = RateLimiter()


def enforce_login_limits(request: Request, username: str) -> None:
    ip = extract_client_ip(request)
    rate_limiter.enforce(f"login_ip:{ip}", limit=20, window_seconds=60)
    rate_limiter.enforce(f"login_user:{username}", limit=10, window_seconds=60)


def enforce_heavy_api_limits(request: Request, scope: str) -> None:
    ip = extract_client_ip(request)
    rate_limiter.enforce(f"heavy:{scope}:{ip}", limit=30, window_seconds=60)


def enforce_read_api_limits(request: Request, scope: str) -> None:
    ip = extract_client_ip(request)
    rate_limiter.enforce(f"read:{scope}:{ip}", limit=120, window_seconds=60)
