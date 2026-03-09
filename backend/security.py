"""Shared security helpers and middleware."""

import json
import logging
import os
import re
import time
from typing import Iterable, Optional

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("security")

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_EXEMPT_PREFIXES = ("/api/auth/login", "/api/auth/refresh")


def parse_csv_env(name: str, default: str) -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def extract_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def extract_client_ip_from_scope(scope: dict) -> str:
    """Extract client IP from ASGI scope (e.g. WebSocket). Uses X-Forwarded-For when behind proxy."""
    headers = dict(
        (k.decode().lower(), v.decode() if isinstance(v, bytes) else v)
        for k, v in scope.get("headers", [])
    )
    forwarded_for = headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    client = scope.get("client")
    if client:
        return client[0]
    return "unknown"


def validate_csrf_token(ws_token: Optional[str], cookie_token: Optional[str]) -> bool:
    """Validate CSRF token matching between WebSocket connection and cookies."""
    return ws_token is not None and cookie_token is not None and ws_token == cookie_token


def should_skip_csrf(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in CSRF_EXEMPT_PREFIXES)


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in MUTATING_METHODS and request.url.path.startswith("/api/"):
            if not should_skip_csrf(request.url.path):
                cookie_token = request.cookies.get("csrf_token")
                header_token = request.headers.get("x-csrf-token")
                if not cookie_token or not header_token or cookie_token != header_token:
                    raise HTTPException(status_code=403, detail="CSRF validation failed")
        return await call_next(request)


class CooldownGuard:
    """Simple in-memory cooldown guard for disruptive actions."""

    def __init__(self, cooldown_seconds: int = 5):
        self.cooldown_seconds = cooldown_seconds
        self._last_action: dict[str, float] = {}

    def check(self, key: str) -> None:
        now = time.time()
        last = self._last_action.get(key, 0.0)
        if now - last < self.cooldown_seconds:
            raise HTTPException(status_code=429, detail="Operation is cooling down")
        self._last_action[key] = now


# Regex to match KEY=value in log content where key contains sensitive terms
# Matches keys containing TOKEN, PASSWORD, SECRET, API_KEY, AUTH, CREDENTIAL (e.g. HF_TOKEN, OPENAI_API_KEY)
_LOG_REDACT_PATTERN = re.compile(
    r"((?:[A-Z_]*)?(?:TOKEN|PASSWORD|SECRET|API_KEY|AUTH|CREDENTIAL)(?:[A-Z_]*)?\s*=\s*)([^\s]+)",
    re.IGNORECASE,
)


def redact_log_content(content: str) -> str:
    """Mask sensitive key=value patterns in log content before returning to clients."""
    if not content:
        return content
    return _LOG_REDACT_PATTERN.sub(r"\1***REDACTED***", content)


def redact_env_content(content: str, sensitive_keys: Iterable[str]) -> str:
    if not content:
        return content
    keys = {k.upper() for k in sensitive_keys}
    redacted_lines: list[str] = []
    for line in content.splitlines():
        if "=" not in line or line.strip().startswith("#"):
            redacted_lines.append(line)
            continue
        key, _, value = line.partition("=")
        if key.strip().upper() in keys:
            redacted_lines.append(f"{key}=***REDACTED***")
        else:
            redacted_lines.append(f"{key}={value}")
    return "\n".join(redacted_lines)


def audit_event(request: Request, action: str, target: str, outcome: str, details: dict | None = None) -> None:
    payload = {
        "event": "security_audit",
        "action": action,
        "target": target,
        "outcome": outcome,
        "path": request.url.path,
        "method": request.method,
        "ip": extract_client_ip(request),
        "user_id": getattr(getattr(request.state, "current_user", None), "id", None),
        "username": getattr(getattr(request.state, "current_user", None), "username", None),
        "details": details or {},
    }
    logger.info(json.dumps(payload, sort_keys=True))
