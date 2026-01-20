"""
vLLM management API endpoints
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class SwitchConfigRequest(BaseModel):
    config_filename: str


class UpdateEnvRequest(BaseModel):
    content: str


@router.get("/configs")
async def list_configs(request: Request):
    """List all available vLLM configurations"""
    vllm_service = request.app.state.vllm_service
    
    try:
        configs = vllm_service.list_configs()
        return {"status": "success", "data": configs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active")
async def get_active_config(request: Request):
    """Get the currently active configuration"""
    vllm_service = request.app.state.vllm_service
    
    try:
        config = vllm_service.get_active_config()
        return {"status": "success", "data": config}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/switch")
async def switch_config(request: Request, body: SwitchConfigRequest):
    """Switch to a different configuration (restarts vLLM)"""
    vllm_service = request.app.state.vllm_service
    
    try:
        result = vllm_service.switch_config(body.config_filename)
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_vllm_status(request: Request):
    """Get the status of the vLLM container"""
    vllm_service = request.app.state.vllm_service
    
    try:
        status = vllm_service.get_vllm_status()
        return {"status": "success", "data": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restart")
async def restart_vllm(request: Request):
    """Restart the vLLM container"""
    vllm_service = request.app.state.vllm_service
    
    try:
        result = vllm_service.restart_vllm()
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_vllm(request: Request):
    """Stop the vLLM container"""
    vllm_service = request.app.state.vllm_service
    
    try:
        result = vllm_service.stop_vllm()
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start")
async def start_vllm(request: Request):
    """Start the vLLM container"""
    vllm_service = request.app.state.vllm_service
    
    try:
        result = vllm_service.start_vllm()
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/proxy/status")
async def get_proxy_status(request: Request):
    """Get the status of the vLLM proxy container"""
    vllm_service = request.app.state.vllm_service
    
    try:
        status = vllm_service.get_proxy_status()
        return {"status": "success", "data": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Environment file management endpoints

@router.get("/env")
async def list_env_files(request: Request):
    """List all environment files"""
    vllm_service = request.app.state.vllm_service
    
    try:
        env_files = vllm_service.list_env_files()
        return {"status": "success", "data": env_files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/env/{filename}")
async def get_env_file(request: Request, filename: str):
    """Get contents of a specific environment file"""
    vllm_service = request.app.state.vllm_service
    
    try:
        content = vllm_service.get_env_file(filename)
        return {"status": "success", "data": {"filename": filename, "content": content}}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/env/{filename}")
async def update_env_file(request: Request, filename: str, body: UpdateEnvRequest):
    """Update contents of a specific environment file"""
    vllm_service = request.app.state.vllm_service
    
    # Don't allow editing env.active - it's auto-generated
    if filename == "env.active":
        raise HTTPException(status_code=400, detail="env.active is auto-generated and cannot be edited directly")
    
    try:
        result = vllm_service.update_env_file(filename, body.content)
        return {"status": "success", "data": result}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
