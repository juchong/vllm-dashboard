"""
Container management API endpoints
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from typing import Optional
from pydantic import BaseModel
from services.docker_service import DockerService
import asyncio

router = APIRouter()


class ContainerAction(BaseModel):
    container_name: str
    profile: Optional[str] = None


class ContainerLogsRequest(BaseModel):
    container_name: str
    tail: Optional[int] = 100
    follow: Optional[bool] = False


@router.post("/start")
async def start_container(action: ContainerAction, request: Request):
    """Start a vLLM container"""
    docker_service: DockerService = request.app.state.docker_service
    
    try:
        result = docker_service.start_container(
            action.container_name,
            profile=action.profile
        )
        return {"status": "success", "message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_container(action: ContainerAction, request: Request):
    """Stop a vLLM container"""
    docker_service: DockerService = request.app.state.docker_service
    
    try:
        result = docker_service.stop_container(action.container_name)
        return {"status": "success", "message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restart")
async def restart_container(action: ContainerAction, request: Request):
    """Restart a vLLM container"""
    docker_service: DockerService = request.app.state.docker_service
    
    try:
        result = docker_service.restart_container(action.container_name)
        return {"status": "success", "message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_container_status(request: Request):
    """Get status of all vLLM containers"""
    docker_service: DockerService = request.app.state.docker_service
    
    try:
        status = docker_service.get_container_status()
        return {"status": "success", "data": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs")
async def get_container_logs(
    request: Request,
    container_name: str,
    tail: int = 100,
    follow: bool = False
):
    """Get container logs with optional streaming"""
    docker_service: DockerService = request.app.state.docker_service
    
    try:
        if follow:
            # Streaming response for real-time logs
            return docker_service.stream_container_logs(container_name, tail=tail)
        else:
            logs = docker_service.get_container_logs(container_name, tail=tail)
            return {"status": "success", "logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
