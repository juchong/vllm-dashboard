"""
Configuration management API endpoints
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from deps import get_current_user
from models.auth_models import User
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
    current_user: User = Depends(get_current_user),
):
    """Save configuration for a model (creates new model+config pair)"""
    config_service: ConfigService = request.app.state.config_service
    
    try:
        result = config_service.save_config(
            model_name=config_data.model_name,
            config=config_data.config
        )
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
    
    try:
        config = config_service.get_model_config(model_name)
        return {"status": "success", "data": config}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.post("/associate")
async def associate_config(
    request: Request,
    pair_data: AssociateConfigRequest,
    current_user: User = Depends(get_current_user),
):
    """Associate a model with a configuration file"""
    config_service: ConfigService = request.app.state.config_service
    
    try:
        result = config_service.associate_config(
            model_name=pair_data.model_name,
            config_path=pair_data.config_path
        )
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
