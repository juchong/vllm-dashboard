"""
Model management API endpoints
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List
from services.hf_service import HuggingFaceService
from services.docker_service import DockerService
import os

router = APIRouter()


class ModelDownloadRequest(BaseModel):
    model_name: str
    revision: Optional[str] = None
    local_dir: Optional[str] = None


class ModelDeleteRequest(BaseModel):
    model_path: str


class ModelRenameRequest(BaseModel):
    old_path: str
    new_path: str


@router.post("/download")
async def download_model(
    request: Request,
    model_data: ModelDownloadRequest
):
    """Download a model from Hugging Face Hub"""
    hf_service: HuggingFaceService = request.app.state.hf_service
    
    try:
        result = hf_service.download_model(
            model_name=model_data.model_name,
            revision=model_data.revision,
            local_dir=model_data.local_dir
        )
        return {"status": "success", "message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_models(request: Request):
    """List all downloaded models"""
    hf_service: HuggingFaceService = request.app.state.hf_service
    
    try:
        models = hf_service.list_models()
        return {"status": "success", "data": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{model_path:path}")
async def delete_model(
    request: Request,
    model_path: str
):
    """Delete a model"""
    hf_service: HuggingFaceService = request.app.state.hf_service
    
    try:
        result = hf_service.delete_model(model_path)
        return {"status": "success", "message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rename")
async def rename_model(
    request: Request,
    rename_data: ModelRenameRequest
):
    """Rename a model"""
    hf_service: HuggingFaceService = request.app.state.hf_service
    
    try:
        result = hf_service.rename_model(
            old_path=rename_data.old_path,
            new_path=rename_data.new_path
        )
        return {"status": "success", "message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/load-config")
async def load_model_config(
    request: Request,
    model_name: str
):
    """Load configuration for a specific model"""
    config_service = request.app.state.config_service
    
    try:
        config = config_service.get_model_config(model_name)
        return {"status": "success", "data": config}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validate/{model_name:path}")
async def validate_model(
    request: Request,
    model_name: str
):
    """Validate a model name exists on HuggingFace"""
    hf_service: HuggingFaceService = request.app.state.hf_service
    
    try:
        result = hf_service.validate_model_name(model_name)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/revisions/{model_name:path}")
async def get_model_revisions(
    request: Request,
    model_name: str
):
    """Get available revisions for a model"""
    hf_service: HuggingFaceService = request.app.state.hf_service
    
    try:
        result = hf_service.get_model_revisions(model_name)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
