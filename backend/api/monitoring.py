"""
Monitoring API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from deps import get_current_user
from models.auth_models import User
from services.docker_service import DockerService
from services.gpu_service import GPUService

router = APIRouter()


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
