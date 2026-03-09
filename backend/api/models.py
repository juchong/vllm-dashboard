"""
Model management API endpoints
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from deps import get_current_user, require_role
from models.auth_models import User
from rate_limit import enforce_heavy_api_limits
from security import audit_event
from services.hf_service import HuggingFaceService

router = APIRouter()


class ModelDownloadRequest(BaseModel):
    model_name: str
    revision: Optional[str] = None


class ModelRenameRequest(BaseModel):
    old_path: str
    new_path: str


@router.post("/download")
async def download_model(request: Request, model_data: ModelDownloadRequest, current_user: User = Depends(require_role("operator"))):
    """Start a background model download and return task ID"""
    download_manager = request.app.state.download_manager

    try:
        enforce_heavy_api_limits(request, "model_download")
        task_id = download_manager.start_download(
            model_name=model_data.model_name,
            revision=model_data.revision,
        )
        return {
            "status": "success",
            "message": f"Download started for {model_data.model_name}",
            "task_id": task_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/download/status/{task_id}")
async def get_download_status(request: Request, task_id: str, current_user: User = Depends(get_current_user)):
    """Get status of a download task"""
    download_manager = request.app.state.download_manager
    status = download_manager.get_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Download task not found")
    return {"status": "success", "data": status}


@router.get("/download/active")
async def get_active_downloads(request: Request, current_user: User = Depends(get_current_user)):
    """Get all active downloads"""
    download_manager = request.app.state.download_manager
    downloads = download_manager.get_active_downloads()
    return {"status": "success", "data": downloads}


@router.get("/download/all")
async def get_all_downloads(request: Request, current_user: User = Depends(get_current_user)):
    """Get all downloads including completed/failed/resumable"""
    download_manager = request.app.state.download_manager
    downloads = download_manager.get_all_downloads()
    return {"status": "success", "data": downloads}


@router.post("/download/cancel/{task_id}")
async def cancel_download(request: Request, task_id: str, current_user: User = Depends(require_role("operator"))):
    """Cancel a download task"""
    download_manager = request.app.state.download_manager
    success = download_manager.cancel_download(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Download task not found or cannot be cancelled")
    return {"status": "success", "message": f"Download {task_id} cancelled"}


@router.post("/download/resume/{task_id}")
async def resume_download(request: Request, task_id: str, current_user: User = Depends(require_role("operator"))):
    """Resume a previously interrupted download"""
    download_manager = request.app.state.download_manager
    success = download_manager.resume_download(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Download task not found or cannot be resumed")
    return {"status": "success", "message": f"Download {task_id} resumed"}


@router.get("/list")
async def list_models(request: Request, current_user: User = Depends(get_current_user)):
    """List all downloaded models"""
    hf_service: HuggingFaceService = request.app.state.hf_service
    try:
        models = hf_service.list_models()
        return {"status": "success", "data": models}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.delete("/{model_path:path}")
async def delete_model(request: Request, model_path: str, current_user: User = Depends(require_role("admin"))):
    """Delete a model - runs in thread pool to avoid blocking on large models"""
    import asyncio
    hf_service: HuggingFaceService = request.app.state.hf_service
    try:
        request.state.current_user = current_user
        # Run blocking deletion in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, hf_service.delete_model, model_path)
        audit_event(request, "delete_model", model_path, "success")
        return {"status": "success", "message": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to delete model {model_path}")
        raise HTTPException(status_code=500, detail="An error occurred")


@router.post("/rename")
async def rename_model(request: Request, rename_data: ModelRenameRequest, current_user: User = Depends(require_role("admin"))):
    """Rename a model"""
    hf_service: HuggingFaceService = request.app.state.hf_service
    try:
        request.state.current_user = current_user
        result = hf_service.rename_model(
            old_path=rename_data.old_path,
            new_path=rename_data.new_path,
        )
        audit_event(request, "rename_model", rename_data.old_path, "success", {"new_path": rename_data.new_path})
        return {"status": "success", "message": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/validate/{model_name:path}")
async def validate_model(request: Request, model_name: str, current_user: User = Depends(get_current_user)):
    """Validate a model name exists on HuggingFace"""
    hf_service: HuggingFaceService = request.app.state.hf_service
    try:
        result = hf_service.validate_model_name(model_name)
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")


@router.get("/revisions/{model_name:path}")
async def get_model_revisions(request: Request, model_name: str, current_user: User = Depends(get_current_user)):
    """Get available revisions for a model"""
    hf_service: HuggingFaceService = request.app.state.hf_service
    try:
        result = hf_service.get_model_revisions(model_name)
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred")
