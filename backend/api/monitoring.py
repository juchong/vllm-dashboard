"""
Monitoring API endpoints
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Any
from services.gpu_service import GPUService
from services.docker_service import DockerService

router = APIRouter()


@router.get("/gpu")
async def get_gpu_metrics(request: Request):
    """Get GPU metrics"""
    gpu_service: GPUService = request.app.state.gpu_service
    
    try:
        metrics = gpu_service.get_gpu_metrics()
        return {"status": "success", "data": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system")
async def get_system_metrics(request: Request):
    """Get system metrics"""
    gpu_service: GPUService = request.app.state.gpu_service
    
    try:
        metrics = gpu_service.get_system_metrics()
        return {"status": "success", "data": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/container")
async def get_container_metrics(request: Request):
    """Get container resource usage"""
    docker_service: DockerService = request.app.state.docker_service
    
    try:
        metrics = docker_service.get_container_metrics()
        return {"status": "success", "data": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
