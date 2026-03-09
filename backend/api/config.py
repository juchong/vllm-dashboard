"""
Configuration management API endpoints.
Config save/get is instance-scoped. Model metadata is global.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from deps import get_current_user, require_role
from models.auth_models import User
from security import audit_event
from services.config_service import ConfigService
from services.hf_service import HuggingFaceService, derive_model_type
from services.instance_registry import InstanceRegistry

router = APIRouter()


class ConfigPair(BaseModel):
    model_name: str
    config_path: str


class SaveConfigRequest(BaseModel):
    model_name: str
    config: Dict[str, Any]


class AssociateConfigRequest(BaseModel):
    model_name: str
    config_path: str


def _get_config_service(request: Request, instance_id: str) -> ConfigService:
    """Get a ConfigService scoped to the shared config directory.
    Model configs are shared across all instances; only active.yaml/env.active are per-instance.
    """
    registry: InstanceRegistry = request.app.state.instance_registry
    inst = registry.get_instance(instance_id)
    if inst is None:
        raise HTTPException(status_code=404, detail=f"Instance '{instance_id}' not found")
    return ConfigService(config_dir=registry.config_dir)


@router.get("/{instance_id}/templates")
async def get_config_templates(instance_id: str, request: Request,
                               current_user: User = Depends(get_current_user)):
    """Get available configuration templates."""
    config_service = _get_config_service(request, instance_id)
    try:
        templates = config_service.get_config_templates()
        return {"status": "success", "data": templates}
    except Exception:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.post("/{instance_id}/save")
async def save_config(
    instance_id: str,
    request: Request,
    config_data: SaveConfigRequest,
    current_user: User = Depends(require_role("admin")),
):
    """Save configuration for a model in an instance's config directory."""
    config_service = _get_config_service(request, instance_id)
    try:
        request.state.current_user = current_user
        result = config_service.save_config(
            model_name=config_data.model_name,
            config=config_data.config
        )
        audit_event(request, "save_config", config_data.model_name, "success", {"instance": instance_id})
        return {"status": "success", "message": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/{instance_id}/model/{model_name:path}")
async def get_model_config(
    instance_id: str,
    request: Request,
    model_name: str,
    current_user: User = Depends(get_current_user),
):
    """Get configuration for a specific model within an instance."""
    config_service = _get_config_service(request, instance_id)
    hf_service: HuggingFaceService = request.app.state.hf_service

    try:
        result = config_service.get_model_config(model_name)

        config = result.get("config") or {}
        model_path = config.get("model", model_name)

        detected_model_type = "dense_full"
        meta = hf_service.read_model_metadata(model_path)
        if meta:
            detected_model_type = derive_model_type(
                meta.get("num_experts", 0),
                meta.get("quant_method"),
                meta.get("weights_type"),
                meta.get("weights_bits"),
            )
            result["num_experts"] = meta.get("num_experts", 0)
            result["quant_method"] = meta.get("quant_method")
            result["architecture"] = meta.get("architecture")

        result["detected_model_type"] = detected_model_type
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="An error occurred")


class RegenerateConfigRequest(BaseModel):
    model_name: str


@router.post("/{instance_id}/regenerate")
async def regenerate_config(
    instance_id: str,
    request: Request,
    data: RegenerateConfigRequest,
    current_user: User = Depends(require_role("admin")),
):
    """Delete existing config and regenerate from model metadata on disk."""
    config_service = _get_config_service(request, instance_id)
    hf_service: HuggingFaceService = request.app.state.hf_service
    try:
        request.state.current_user = current_user
        model_dir = hf_service.resolve_model_dir(data.model_name)
        if not model_dir:
            raise ValueError(f"Model directory not found for {data.model_name}")
        result_path = config_service.regenerate_config_for_model(data.model_name, model_dir)
        if not result_path:
            raise ValueError("Config generation failed")
        result = config_service.get_model_config(data.model_name)
        audit_event(request, "regenerate_config", data.model_name, "success", {"instance": instance_id})
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.post("/{instance_id}/associate")
async def associate_config(
    instance_id: str,
    request: Request,
    pair_data: AssociateConfigRequest,
    current_user: User = Depends(require_role("admin")),
):
    """Associate a model with a configuration file."""
    config_service = _get_config_service(request, instance_id)
    try:
        request.state.current_user = current_user
        result = config_service.associate_config(
            model_name=pair_data.model_name,
            config_path=pair_data.config_path
        )
        audit_event(request, "associate_config", pair_data.config_path, "success",
                     {"model": pair_data.model_name, "instance": instance_id})
        return {"status": "success", "message": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/{instance_id}/pairs")
async def list_config_pairs(instance_id: str, request: Request,
                            current_user: User = Depends(get_current_user)):
    """List all model+configuration pairs for an instance."""
    config_service = _get_config_service(request, instance_id)
    try:
        pairs = config_service.list_config_pairs()
        return {"status": "success", "data": pairs}
    except Exception:
        raise HTTPException(status_code=500, detail="An error occurred")
