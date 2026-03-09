"""
vLLM management API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from deps import get_current_user, require_role
from models.auth_models import User
from rate_limit import enforce_heavy_api_limits
from security import audit_event, redact_env_content

router = APIRouter()


class SwitchConfigRequest(BaseModel):
    config_filename: str


@router.get("/configs")
async def list_configs(request: Request, current_user: User = Depends(get_current_user)):
    """List all available vLLM configurations"""
    vllm_service = request.app.state.vllm_service
    
    try:
        configs = vllm_service.list_configs()
        return {"status": "success", "data": configs}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/active")
async def get_active_config(request: Request, current_user: User = Depends(get_current_user)):
    """Get the currently active configuration"""
    vllm_service = request.app.state.vllm_service
    
    try:
        config = vllm_service.get_active_config()
        return {"status": "success", "data": config}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.post("/switch")
async def switch_config(request: Request, body: SwitchConfigRequest, current_user: User = Depends(require_role("admin"))):
    """Switch to a different configuration (restarts vLLM)"""
    enforce_heavy_api_limits(request, "vllm_control")
    vllm_service = request.app.state.vllm_service
    
    try:
        request.state.current_user = current_user
        request.app.state.cooldown_guard.check(f"{current_user.id}:switch")
        result = vllm_service.switch_config(body.config_filename)
        audit_event(request, "switch_config", body.config_filename, "success")
        return {"status": "success", "data": result}
    except ValueError as e:
        audit_event(request, "switch_config", body.config_filename, "denied", {"error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        audit_event(request, "switch_config", body.config_filename, "error")
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/status")
async def get_vllm_status(request: Request, current_user: User = Depends(get_current_user)):
    """Get the status of the vLLM container"""
    vllm_service = request.app.state.vllm_service
    
    try:
        status = vllm_service.get_vllm_status()
        return {"status": "success", "data": status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.post("/restart")
async def restart_vllm(request: Request, current_user: User = Depends(require_role("operator"))):
    """Restart the vLLM container"""
    enforce_heavy_api_limits(request, "vllm_control")
    vllm_service = request.app.state.vllm_service
    
    try:
        request.state.current_user = current_user
        request.app.state.cooldown_guard.check(f"{current_user.id}:restart")
        result = vllm_service.restart_vllm()
        audit_event(request, "restart_vllm", "vllm", "success")
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.post("/reload")
async def reload_config(request: Request, current_user: User = Depends(require_role("operator"))):
    """Re-read the active config YAML, regenerate active.yaml + env.active, and restart vLLM"""
    enforce_heavy_api_limits(request, "vllm_control")
    vllm_service = request.app.state.vllm_service
    
    try:
        request.state.current_user = current_user
        request.app.state.cooldown_guard.check(f"{current_user.id}:reload")
        result = vllm_service.reload_active_config()
        audit_event(request, "reload_config", result.get("config_filename", "unknown"), "success")
        return {"status": "success", "data": result}
    except ValueError as e:
        audit_event(request, "reload_config", "unknown", "denied", {"error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        audit_event(request, "reload_config", "unknown", "error")
        raise HTTPException(status_code=500, detail="An error occurred")


@router.post("/stop")
async def stop_vllm(request: Request, current_user: User = Depends(require_role("admin"))):
    """Stop the vLLM container"""
    enforce_heavy_api_limits(request, "vllm_control")
    vllm_service = request.app.state.vllm_service
    
    try:
        request.state.current_user = current_user
        request.app.state.cooldown_guard.check(f"{current_user.id}:stop")
        result = vllm_service.stop_vllm()
        audit_event(request, "stop_vllm", "vllm", "success")
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.post("/start")
async def start_vllm(request: Request, current_user: User = Depends(require_role("admin"))):
    """Start the vLLM container"""
    enforce_heavy_api_limits(request, "vllm_control")
    vllm_service = request.app.state.vllm_service
    
    try:
        request.state.current_user = current_user
        request.app.state.cooldown_guard.check(f"{current_user.id}:start")
        result = vllm_service.start_vllm()
        audit_event(request, "start_vllm", "vllm", "success")
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/proxy/status")
async def get_proxy_status(request: Request, current_user: User = Depends(get_current_user)):
    """Get the status of the vLLM proxy container"""
    vllm_service = request.app.state.vllm_service
    
    try:
        status = vllm_service.get_proxy_status()
        return {"status": "success", "data": status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/env/{filename}")
async def get_env_file(request: Request, filename: str, current_user: User = Depends(get_current_user)):
    """Get contents of env.active"""
    vllm_service = request.app.state.vllm_service
    
    try:
        content = vllm_service.get_env_file(filename)
        content = redact_env_content(content, {"HF_TOKEN", "OPENAI_API_KEY", "TOKEN", "PASSWORD", "SECRET_KEY"})
        return {"status": "success", "data": {"filename": filename, "content": content}}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/env/preview/{config_filename}")
async def get_env_preview(request: Request, config_filename: str, current_user: User = Depends(get_current_user)):
    """Get env var preview for a config."""
    vllm_service = request.app.state.vllm_service

    try:
        result = vllm_service.get_env_preview(config_filename)
        result["merged"] = {
            k: ("***REDACTED***" if any(m in k.upper() for m in ("TOKEN", "KEY", "PASSWORD", "SECRET")) else v)
            for k, v in result["merged"].items()
        }
        return {"status": "success", "data": result}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")
