"""
FastAPI backend for vLLM Dashboard
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from api import auth, config, containers, models, monitoring, vllm, websockets
from database import get_db, init_db
from services.config_service import ConfigService
from services.docker_service import DockerService
from services.download_manager import DownloadManager
from services.gpu_service import GPUService
from services.hf_service import HuggingFaceService
from services.vllm_service import VLLMService


def _ensure_initial_admin():
    """Create default admin user if no users exist."""
    import logging
    import os
    from models.auth_models import User
    from database import SessionLocal

    logger = logging.getLogger(__name__)
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            from services.auth_service import AuthService
            svc = AuthService(db)
            username = os.environ.get("INITIAL_ADMIN_USER", "admin")
            password = os.environ.get("INITIAL_ADMIN_PASSWORD", "admin123")
            try:
                svc.create_user(username, password)
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
    app.state.vllm_service = VLLMService(app.state.docker_service)
    app.state.download_manager = DownloadManager(app.state.hf_service, app.state.config_service)

    yield


app = FastAPI(
    title="vLLM Dashboard API",
    description="API for managing vLLM containers, models, and monitoring",
    version="1.0.0",
    lifespan=lifespan
)


# Security headers
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# CORS Configuration - restrict origins when using credentials
_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:8080,http://localhost:5173,http://127.0.0.1:8080,http://127.0.0.1:5173,https://vllm-dashboard.chongflix.tv,http://vllm-dashboard.chongflix.tv")
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
