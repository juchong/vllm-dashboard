"""
Container management API endpoints
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from deps import get_current_user, require_role
from models.auth_models import User
from rate_limit import enforce_heavy_api_limits
from services.docker_service import DockerService
from security import audit_event

router = APIRouter()


class ContainerAction(BaseModel):
    container_name: str
    profile: Optional[str] = None


@router.post("/start")
async def start_container(action: ContainerAction, request: Request, current_user: User = Depends(require_role("admin"))):
    """Start a vLLM container"""
    enforce_heavy_api_limits(request, "container_control")
    docker_service: DockerService = request.app.state.docker_service
    
    try:
        request.state.current_user = current_user
        request.app.state.cooldown_guard.check(f"{current_user.id}:container-start:{action.container_name}")
        result = docker_service.start_container(
            action.container_name,
            profile=action.profile
        )
        audit_event(request, "start_container", action.container_name, "success")
        return {"status": "success", "message": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.post("/stop")
async def stop_container(action: ContainerAction, request: Request, current_user: User = Depends(require_role("admin"))):
    """Stop a vLLM container"""
    enforce_heavy_api_limits(request, "container_control")
    docker_service: DockerService = request.app.state.docker_service
    
    try:
        request.state.current_user = current_user
        request.app.state.cooldown_guard.check(f"{current_user.id}:container-stop:{action.container_name}")
        result = docker_service.stop_container(action.container_name)
        audit_event(request, "stop_container", action.container_name, "success")
        return {"status": "success", "message": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.post("/restart")
async def restart_container(action: ContainerAction, request: Request, current_user: User = Depends(require_role("operator"))):
    """Restart a vLLM container"""
    enforce_heavy_api_limits(request, "container_control")
    docker_service: DockerService = request.app.state.docker_service
    
    try:
        request.state.current_user = current_user
        request.app.state.cooldown_guard.check(f"{current_user.id}:container-restart:{action.container_name}")
        result = docker_service.restart_container(action.container_name)
        audit_event(request, "restart_container", action.container_name, "success")
        return {"status": "success", "message": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/status")
async def get_container_status(request: Request, current_user: User = Depends(get_current_user)):
    """Get status of all vLLM containers"""
    docker_service: DockerService = request.app.state.docker_service
    
    try:
        status = docker_service.get_container_status()
        return {"status": "success", "data": status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/logs")
async def get_container_logs(
    request: Request,
    container_name: str,
    tail: int = 100,
    follow: bool = False,
    current_user: User = Depends(get_current_user),
):
    """Get container logs with optional streaming"""
    docker_service: DockerService = request.app.state.docker_service
    
    tail = max(1, min(tail, 10000))
    try:
        enforce_heavy_api_limits(request, "container_logs")
        if follow:
            # Streaming response for real-time logs
            return docker_service.stream_container_logs(container_name, tail=tail)
        else:
            logs = docker_service.get_container_logs(container_name, tail=tail)
            return {"status": "success", "logs": logs}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
