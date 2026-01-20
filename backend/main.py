"""
FastAPI backend for vLLM Dashboard
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api import containers, models, monitoring, config, websockets, vllm
from services.docker_service import DockerService
from services.hf_service import HuggingFaceService
from services.gpu_service import GPUService
from services.config_service import ConfigService
from services.vllm_service import VLLMService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup"""
    # Initialize services
    app.state.docker_service = DockerService()
    app.state.hf_service = HuggingFaceService()
    app.state.gpu_service = GPUService()
    app.state.config_service = ConfigService()
    app.state.vllm_service = VLLMService(app.state.docker_service)
    
    # Start background tasks
    # GPU monitoring will be started via WebSocket
    
    yield
    
    # Cleanup on shutdown
    pass


app = FastAPI(
    title="vLLM Dashboard API",
    description="API for managing vLLM containers, models, and monitoring",
    version="1.0.0",
    lifespan=lifespan
)


# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include API routers
app.include_router(containers.router, prefix="/api/containers", tags=["containers"])
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["monitoring"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(vllm.router, prefix="/api/vllm", tags=["vllm"])
app.include_router(websockets.router, prefix="/ws", tags=["websockets"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "vLLM Dashboard API",
        "version": "1.0.0",
        "endpoints": {
            "containers": "/api/containers",
            "models": "/api/models",
            "monitoring": "/api/monitoring",
            "config": "/api/config",
            "vllm": "/api/vllm",
            "websockets": "/ws/updates"
        }
    }
