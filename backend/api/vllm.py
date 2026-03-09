"""
vLLM management API endpoints.
All endpoints are instance-scoped via {instance_id} path parameter.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from deps import get_current_user, require_role
from models.auth_models import User
from rate_limit import enforce_heavy_api_limits
from security import audit_event, redact_env_content
from services.instance_registry import InstanceRegistry

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_vllm_service(request: Request, instance_id: str):
    """Resolve VLLMService from the instance registry."""
    registry: InstanceRegistry = request.app.state.instance_registry
    try:
        return registry.get_vllm_service(instance_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Instance '{instance_id}' not found")


class SwitchConfigRequest(BaseModel):
    config_filename: str


@router.get("/{instance_id}/configs")
async def list_configs(instance_id: str, request: Request, current_user: User = Depends(get_current_user)):
    """List all available vLLM configurations for an instance."""
    vllm_service = _get_vllm_service(request, instance_id)
    try:
        configs = vllm_service.list_configs()
        return {"status": "success", "data": configs}
    except Exception:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/{instance_id}/active")
async def get_active_config(instance_id: str, request: Request, current_user: User = Depends(get_current_user)):
    """Get the currently active configuration for an instance."""
    vllm_service = _get_vllm_service(request, instance_id)
    try:
        config = vllm_service.get_active_config()
        return {"status": "success", "data": config}
    except Exception:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.post("/{instance_id}/switch")
async def switch_config(instance_id: str, request: Request, body: SwitchConfigRequest,
                        current_user: User = Depends(require_role("admin"))):
    """Switch to a different configuration (restarts vLLM)."""
    enforce_heavy_api_limits(request, "vllm_control")
    vllm_service = _get_vllm_service(request, instance_id)
    try:
        request.state.current_user = current_user
        request.app.state.cooldown_guard.check(f"{current_user.id}:switch:{instance_id}")
        result = vllm_service.switch_config(body.config_filename)
        audit_event(request, "switch_config", body.config_filename, "success", {"instance": instance_id})
        return {"status": "success", "data": result}
    except ValueError as e:
        audit_event(request, "switch_config", body.config_filename, "denied", {"error": str(e), "instance": instance_id})
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        audit_event(request, "switch_config", body.config_filename, "error", {"instance": instance_id})
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/{instance_id}/status")
async def get_vllm_status(instance_id: str, request: Request, current_user: User = Depends(get_current_user)):
    """Get the status of the vLLM container for an instance."""
    vllm_service = _get_vllm_service(request, instance_id)
    try:
        status = vllm_service.get_vllm_status()
        return {"status": "success", "data": status}
    except Exception:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.post("/{instance_id}/restart")
async def restart_vllm(instance_id: str, request: Request,
                       current_user: User = Depends(require_role("operator"))):
    """Restart the vLLM container for an instance."""
    enforce_heavy_api_limits(request, "vllm_control")
    vllm_service = _get_vllm_service(request, instance_id)
    try:
        request.state.current_user = current_user
        request.app.state.cooldown_guard.check(f"{current_user.id}:restart:{instance_id}")
        result = vllm_service.restart_vllm()
        audit_event(request, "restart_vllm", instance_id, "success")
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"[{instance_id}] restart_vllm failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{instance_id}/reload")
async def reload_config(instance_id: str, request: Request,
                        current_user: User = Depends(require_role("operator"))):
    """Re-read the active config YAML, regenerate active.yaml + env.active, and restart."""
    enforce_heavy_api_limits(request, "vllm_control")
    vllm_service = _get_vllm_service(request, instance_id)
    try:
        request.state.current_user = current_user
        request.app.state.cooldown_guard.check(f"{current_user.id}:reload:{instance_id}")
        result = vllm_service.reload_active_config()
        audit_event(request, "reload_config", result.get("config_filename", "unknown"), "success", {"instance": instance_id})
        return {"status": "success", "data": result}
    except ValueError as e:
        audit_event(request, "reload_config", "unknown", "denied", {"error": str(e), "instance": instance_id})
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.post("/{instance_id}/stop")
async def stop_vllm(instance_id: str, request: Request,
                    current_user: User = Depends(require_role("admin"))):
    """Stop the vLLM container for an instance."""
    enforce_heavy_api_limits(request, "vllm_control")
    vllm_service = _get_vllm_service(request, instance_id)
    try:
        request.state.current_user = current_user
        request.app.state.cooldown_guard.check(f"{current_user.id}:stop:{instance_id}")
        result = vllm_service.stop_vllm()
        audit_event(request, "stop_vllm", instance_id, "success")
        return {"status": "success", "data": result}
    except Exception:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.post("/{instance_id}/start")
async def start_vllm(instance_id: str, request: Request,
                     current_user: User = Depends(require_role("admin"))):
    """Start the vLLM container for an instance."""
    enforce_heavy_api_limits(request, "vllm_control")
    vllm_service = _get_vllm_service(request, instance_id)
    try:
        request.state.current_user = current_user
        request.app.state.cooldown_guard.check(f"{current_user.id}:start:{instance_id}")
        result = vllm_service.start_vllm()
        audit_event(request, "start_vllm", instance_id, "success")
        return {"status": "success", "data": result}
    except Exception as e:
        logger.exception(f"[{instance_id}] start_vllm failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{instance_id}/update-image")
async def update_image(instance_id: str, request: Request,
                       current_user: User = Depends(require_role("admin"))):
    """Pull latest vLLM image and restart container."""
    enforce_heavy_api_limits(request, "vllm_control")
    vllm_service = _get_vllm_service(request, instance_id)
    try:
        request.state.current_user = current_user
        request.app.state.cooldown_guard.check(f"{current_user.id}:update_image:{instance_id}")
        result = vllm_service.update_image()
        audit_event(request, "update_image", instance_id, "success" if result.get("success") else "error")
        return {"status": "success", "data": result}
    except ValueError as e:
        audit_event(request, "update_image", instance_id, "denied", {"error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/{instance_id}/proxy/status")
async def get_proxy_status(instance_id: str, request: Request,
                           current_user: User = Depends(get_current_user)):
    """Get the status of the vLLM proxy container for an instance."""
    vllm_service = _get_vllm_service(request, instance_id)
    try:
        status = vllm_service.get_proxy_status()
        return {"status": "success", "data": status}
    except Exception:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/{instance_id}/env/{filename}")
async def get_env_file(instance_id: str, filename: str, request: Request,
                       current_user: User = Depends(get_current_user)):
    """Get contents of env.active for an instance."""
    vllm_service = _get_vllm_service(request, instance_id)
    try:
        content = vllm_service.get_env_file(filename)
        content = redact_env_content(content, {"HF_TOKEN", "OPENAI_API_KEY", "TOKEN", "PASSWORD", "SECRET_KEY"})
        return {"status": "success", "data": {"filename": filename, "content": content}}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/{instance_id}/env/preview/{config_filename}")
async def get_env_preview(instance_id: str, config_filename: str, request: Request,
                          current_user: User = Depends(get_current_user)):
    """Get env var preview for a config."""
    vllm_service = _get_vllm_service(request, instance_id)
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
    except Exception:
        raise HTTPException(status_code=500, detail="An error occurred")
