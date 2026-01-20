"""
Configuration management API endpoints
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from services.config_service import ConfigService

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
async def get_config_templates(request: Request):
    """Get available configuration templates"""
    config_service: ConfigService = request.app.state.config_service
    
    try:
        templates = config_service.get_config_templates()
        return {"status": "success", "data": templates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save")
async def save_config(
    request: Request,
    config_data: SaveConfigRequest
):
    """Save configuration for a model (creates new model+config pair)"""
    config_service: ConfigService = request.app.state.config_service
    
    try:
        result = config_service.save_config(
            model_name=config_data.model_name,
            config=config_data.config
        )
        return {"status": "success", "message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model/{model_name:path}")
async def get_model_config(
    request: Request,
    model_name: str
):
    """Get configuration for a specific model"""
    config_service: ConfigService = request.app.state.config_service
    
    try:
        config = config_service.get_model_config(model_name)
        return {"status": "success", "data": config}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/associate")
async def associate_config(
    request: Request,
    pair_data: AssociateConfigRequest
):
    """Associate a model with a configuration file"""
    config_service: ConfigService = request.app.state.config_service
    
    try:
        result = config_service.associate_config(
            model_name=pair_data.model_name,
            config_path=pair_data.config_path
        )
        return {"status": "success", "message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pairs")
async def list_config_pairs(request: Request):
    """List all model+configuration pairs"""
    config_service: ConfigService = request.app.state.config_service
    
    try:
        pairs = config_service.list_config_pairs()
        return {"status": "success", "data": pairs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
