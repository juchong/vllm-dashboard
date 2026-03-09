"""
Configuration management API endpoints
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from deps import get_current_user, require_role
from models.auth_models import User
from security import audit_event
from services.config_service import ConfigService
from services.hf_service import HuggingFaceService, derive_model_type

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


@router.get("/templates")
async def get_config_templates(request: Request, current_user: User = Depends(get_current_user)):
    """Get available configuration templates"""
    config_service: ConfigService = request.app.state.config_service
    
    try:
        templates = config_service.get_config_templates()
        return {"status": "success", "data": templates}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.post("/save")
async def save_config(
    request: Request,
    config_data: SaveConfigRequest,
    current_user: User = Depends(require_role("admin")),
):
    """Save configuration for a model (creates new model+config pair)"""
    config_service: ConfigService = request.app.state.config_service
    
    try:
        request.state.current_user = current_user
        result = config_service.save_config(
            model_name=config_data.model_name,
            config=config_data.config
        )
        audit_event(request, "save_config", config_data.model_name, "success")
        return {"status": "success", "message": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/model/{model_name:path}")
async def get_model_config(
    request: Request,
    model_name: str,
    current_user: User = Depends(get_current_user),
):
    """Get configuration for a specific model"""
    config_service: ConfigService = request.app.state.config_service
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
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.post("/associate")
async def associate_config(
    request: Request,
    pair_data: AssociateConfigRequest,
    current_user: User = Depends(require_role("admin")),
):
    """Associate a model with a configuration file"""
    config_service: ConfigService = request.app.state.config_service
    
    try:
        request.state.current_user = current_user
        result = config_service.associate_config(
            model_name=pair_data.model_name,
            config_path=pair_data.config_path
        )
        audit_event(request, "associate_config", pair_data.config_path, "success", {"model": pair_data.model_name})
        return {"status": "success", "message": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/pairs")
async def list_config_pairs(request: Request, current_user: User = Depends(get_current_user)):
    """List all model+configuration pairs"""
    config_service: ConfigService = request.app.state.config_service
    
    try:
        pairs = config_service.list_config_pairs()
        return {"status": "success", "data": pairs}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")
