"""
Monitoring API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from deps import get_current_user
from models.auth_models import User
from services.docker_service import DockerService
from services.gpu_service import GPUService

router = APIRouter()


class PowerLimitRequest(BaseModel):
    limit_watts: int


@router.get("/gpu")
async def get_gpu_metrics(request: Request, current_user: User = Depends(get_current_user)):
    """Get GPU metrics"""
    gpu_service: GPUService = request.app.state.gpu_service
    
    try:
        metrics = gpu_service.get_gpu_metrics()
        return {"status": "success", "data": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/system")
async def get_system_metrics(request: Request, current_user: User = Depends(get_current_user)):
    """Get system metrics"""
    gpu_service: GPUService = request.app.state.gpu_service
    
    try:
        metrics = gpu_service.get_system_metrics()
        return {"status": "success", "data": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/container")
async def get_container_metrics(request: Request, current_user: User = Depends(get_current_user)):
    """Get container resource usage"""
    docker_service: DockerService = request.app.state.docker_service
    
    try:
        metrics = docker_service.get_container_metrics()
        return {"status": "success", "data": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/gpu/power")
async def get_gpu_power_info(request: Request, current_user: User = Depends(get_current_user)):
    """Get power constraints for all GPUs."""
    gpu_service: GPUService = request.app.state.gpu_service
    try:
        data = gpu_service.get_all_power_info()
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gpu/{gpu_index}/power")
async def set_gpu_power_limit(
    gpu_index: int,
    body: PowerLimitRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Set GPU power limit (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")

    gpu_service: GPUService = request.app.state.gpu_service
    try:
        result = gpu_service.set_power_limit(gpu_index, body.limit_watts)
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
