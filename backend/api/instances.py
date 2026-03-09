"""
Instance management API endpoints.
"""

import logging
from typing import Optional, List, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from deps import get_current_user, require_role
from models.auth_models import User
from security import audit_event
from services.instance_registry import InstanceRegistry

logger = logging.getLogger(__name__)
router = APIRouter()


class CreateInstanceRequest(BaseModel):
    id: str
    display_name: str
    port: int
    proxy_port: int
    subdomain: str
    gpu_device_ids: Optional[List[str]] = None
    api_key: Optional[str] = None
    expose_port: bool = False
    labels: Optional[Dict[str, str]] = None


class UpdateInstanceRequest(BaseModel):
    display_name: Optional[str] = None
    subdomain: Optional[str] = None
    gpu_device_ids: Optional[List[str]] = None
    api_key: Optional[str] = None
    expose_port: Optional[bool] = None
    labels: Optional[Dict[str, str]] = None


@router.get("")
async def list_instances(request: Request, current_user: User = Depends(get_current_user)):
    """List all vLLM instances with container status."""
    registry: InstanceRegistry = request.app.state.instance_registry
    instances = registry.list_instances()

    for inst in instances:
        try:
            svc = registry.get_vllm_service(inst["id"])
            inst["vllm_status"] = svc.get_vllm_status()
            inst["proxy_status"] = svc.get_proxy_status()
        except Exception:
            inst["vllm_status"] = {"status": "error", "running": False}
            inst["proxy_status"] = {"status": "error", "running": False}

    return {"status": "success", "data": instances}


@router.get("/{instance_id}")
async def get_instance(request: Request, instance_id: str, current_user: User = Depends(get_current_user)):
    """Get details for a single instance."""
    registry: InstanceRegistry = request.app.state.instance_registry
    inst = registry.get_instance(instance_id)
    if inst is None:
        raise HTTPException(status_code=404, detail=f"Instance '{instance_id}' not found")

    try:
        svc = registry.get_vllm_service(instance_id)
        inst["vllm_status"] = svc.get_vllm_status()
        inst["proxy_status"] = svc.get_proxy_status()
    except Exception:
        inst["vllm_status"] = {"status": "error", "running": False}
        inst["proxy_status"] = {"status": "error", "running": False}

    return {"status": "success", "data": inst}


@router.post("")
async def create_instance(
    request: Request,
    body: CreateInstanceRequest,
    current_user: User = Depends(require_role("admin")),
):
    """Create a new vLLM instance."""
    registry: InstanceRegistry = request.app.state.instance_registry
    try:
        request.state.current_user = current_user
        inst = registry.create_instance(
            instance_id=body.id,
            display_name=body.display_name,
            port=body.port,
            proxy_port=body.proxy_port,
            subdomain=body.subdomain,
            gpu_device_ids=body.gpu_device_ids,
            api_key=body.api_key,
            expose_port=body.expose_port,
            labels=body.labels,
        )
        audit_event(request, "create_instance", body.id, "success")
        return {"status": "success", "data": inst}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to create instance {body.id}")
        raise HTTPException(status_code=500, detail="An error occurred")


@router.put("/{instance_id}")
async def update_instance(
    request: Request,
    instance_id: str,
    body: UpdateInstanceRequest,
    current_user: User = Depends(require_role("admin")),
):
    """Update an instance's display name or subdomain."""
    registry: InstanceRegistry = request.app.state.instance_registry
    try:
        request.state.current_user = current_user
        kwargs = body.model_dump(exclude_none=True)
        inst = registry.update_instance(instance_id, **kwargs)
        audit_event(request, "update_instance", instance_id, "success")
        return {"status": "success", "data": inst}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to update instance {instance_id}")
        raise HTTPException(status_code=500, detail="An error occurred")


@router.delete("/{instance_id}")
async def delete_instance(
    request: Request,
    instance_id: str,
    current_user: User = Depends(require_role("admin")),
):
    """Delete an instance (stops containers, removes config dir)."""
    registry: InstanceRegistry = request.app.state.instance_registry
    try:
        request.state.current_user = current_user
        registry.delete_instance(instance_id)
        audit_event(request, "delete_instance", instance_id, "success")
        return {"status": "success", "message": f"Instance '{instance_id}' deleted"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to delete instance {instance_id}")
        raise HTTPException(status_code=500, detail="An error occurred")
