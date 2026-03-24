"""
FastAPI backend for vLLM Dashboard
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from api import auth, config, containers, instances, models, monitoring, vllm, websockets
from database import get_db, init_db
from security import CSRFMiddleware, CooldownGuard, parse_csv_env
from services.config_service import ConfigService
from services.docker_service import DockerService
from services.download_manager import DownloadManager
from services.gpu_service import GPUService
from services.hf_service import HuggingFaceService
from services.instance_registry import InstanceRegistry


def _ensure_initial_admin():
    """Create initial admin user if no users exist."""
    import logging
    import os
    import secrets
    from models.auth_models import User
    from database import SessionLocal

    logger = logging.getLogger(__name__)
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            from services.auth_service import AuthService
            svc = AuthService(db)
            username = os.environ.get("INITIAL_ADMIN_USER", "admin")
            password = os.environ.get("INITIAL_ADMIN_PASSWORD")
            
            # CRITICAL: Enforce strong password requirements for initial admin
            env_name = os.environ.get("ENVIRONMENT", "production").lower()
            
            if not password:
                # Never use insecure defaults in production
                if env_name in {"dev", "development"}:
                    # Only in dev, generate a random password
                    password = secrets.token_urlsafe(24)
                    logger.warning("Generated one-time initial admin password for development: %s", password)
                else:
                    # In production, require explicit password configuration
                    raise RuntimeError("INITIAL_ADMIN_PASSWORD must be set for first bootstrap in non-development mode")
            else:
                # Validate password strength
                if len(password) < 16:
                    raise RuntimeError("INITIAL_ADMIN_PASSWORD must be at least 16 characters")
                
                if not any(c.isupper() for c in password):
                    raise RuntimeError("INITIAL_ADMIN_PASSWORD must contain at least one uppercase letter")
                
                if not any(c.isdigit() for c in password):
                    raise RuntimeError("INITIAL_ADMIN_PASSWORD must contain at least one digit")
                
                # Check for common passwords
                common_passwords = ['admin123', 'admin', 'password', '1234567890', 'qwerty', '123456789', '12345678', '1234567', '123456', '12345', '1234', '123', '12', '1', '0', '']
                if password.lower() in common_passwords or password in common_passwords:
                    raise RuntimeError("INITIAL_ADMIN_PASSWORD is too common")
                
            try:
                svc.create_user(username, password, role="admin")
                logger.info("Created initial admin user: %s", username)
            except Exception as e:
                logger.exception("Failed to create initial admin: %s", e)
                raise
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup"""
    init_db()
    _ensure_initial_admin()

    app.state.docker_service = DockerService()
    app.state.hf_service = HuggingFaceService()
    app.state.gpu_service = GPUService()
    app.state.config_service = ConfigService()
    app.state.hf_service.config_service = app.state.config_service
    app.state.instance_registry = InstanceRegistry(
        config_dir=os.environ.get("VLLM_CONFIG_DIR", "/vllm-configs"),
        docker_service=app.state.docker_service,
        hf_service=app.state.hf_service,
    )
    app.state.download_manager = DownloadManager(app.state.hf_service, app.state.config_service)
    app.state.cooldown_guard = CooldownGuard(cooldown_seconds=int(os.environ.get("CONTROL_ACTION_COOLDOWN_SECONDS", "5")))

    yield


app = FastAPI(
    title="vLLM Dashboard API",
    description="API for managing vLLM containers, models, and monitoring",
    version="1.0.0",
    lifespan=lifespan
)

try:
    from slowapi import Limiter
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from slowapi.util import get_remote_address
    from limits.storage import storage_from_string

    redis_url = os.environ.get("RATE_LIMIT_REDIS_URL")
    if not redis_url:
        import logging as _rlog
        _rlog.getLogger(__name__).warning("RATE_LIMIT_REDIS_URL not set, skipping Redis-backed rate limiting")
        raise RuntimeError("no redis url")
    storage_from_string(redis_url)
    limiter = Limiter(key_func=get_remote_address, storage_uri=redis_url, default_limits=["200/minute"])
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request, exc):
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
except Exception:
    import logging as _log
    _log.getLogger(__name__).warning("slowapi rate limiting not available")
    app.state.limiter = None


# Security headers
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware)

allowed_hosts = parse_csv_env("ALLOWED_HOSTS", "localhost,127.0.0.1")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
if os.environ.get("FORCE_HTTPS_REDIRECT", "false").lower() in {"1", "true", "yes"}:
    app.add_middleware(HTTPSRedirectMiddleware)

# CORS Configuration - restrict origins when using credentials
_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:8080,http://localhost:3000,http://localhost:5173,http://127.0.0.1:8080,http://127.0.0.1:3000,http://127.0.0.1:5173")
_cors_origins_list = [o.strip() for o in _cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include API routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(instances.router, prefix="/api/instances", tags=["instances"])
app.include_router(containers.router, prefix="/api/containers", tags=["containers"])
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["monitoring"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(vllm.router, prefix="/api/vllm", tags=["vllm"])
app.include_router(websockets.router, prefix="/ws", tags=["websockets"])


@app.get("/")
async def root():
    """Root endpoint - minimal info."""
    return {"message": "vLLM Dashboard API", "version": "1.0.0"}
