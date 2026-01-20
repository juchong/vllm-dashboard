"""
Background download manager for HuggingFace models
"""

import threading
import uuid
import os
import shutil
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return current UTC time"""
    return datetime.now(timezone.utc)


class DownloadStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DownloadTask:
    id: str
    model_name: str
    revision: Optional[str]
    status: DownloadStatus = DownloadStatus.PENDING
    progress: str = ""
    error: Optional[str] = None
    started_at: datetime = field(default_factory=utc_now)
    completed_at: Optional[datetime] = None
    download_path: Optional[str] = None
    cancel_requested: bool = False


class DownloadManager:
    """Manages background model downloads"""
    
    def __init__(self, hf_service):
        self.hf_service = hf_service
        self.downloads: Dict[str, DownloadTask] = {}
        self._lock = threading.Lock()
    
    def start_download(self, model_name: str, revision: Optional[str] = None) -> str:
        """Start a background download and return task ID"""
        task_id = str(uuid.uuid4())[:8]
        
        task = DownloadTask(
            id=task_id,
            model_name=model_name,
            revision=revision
        )
        
        with self._lock:
            # Check if already downloading this model
            for existing in self.downloads.values():
                if existing.model_name == model_name and existing.status == DownloadStatus.DOWNLOADING:
                    raise ValueError(f"Model {model_name} is already being downloaded")
            
            self.downloads[task_id] = task
        
        # Start download in background thread
        thread = threading.Thread(
            target=self._download_worker,
            args=(task_id,),
            daemon=True
        )
        thread.start()
        
        return task_id
    
    def cancel_download(self, task_id: str) -> bool:
        """Cancel a download task"""
        task = self.downloads.get(task_id)
        if not task:
            return False
        
        if task.status not in (DownloadStatus.PENDING, DownloadStatus.DOWNLOADING):
            return False  # Can't cancel completed/failed/cancelled downloads
        
        with self._lock:
            task.cancel_requested = True
            task.status = DownloadStatus.CANCELLED
            task.error = "Download cancelled by user"
            task.completed_at = utc_now()
        
        # Try to clean up partial download
        if task.download_path and os.path.exists(task.download_path):
            try:
                shutil.rmtree(task.download_path)
                logger.info(f"Cleaned up partial download: {task.download_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up partial download: {e}")
        
        logger.info(f"Download cancelled: {task.model_name}")
        return True
    
    def _download_worker(self, task_id: str):
        """Worker thread that performs the download"""
        task = self.downloads.get(task_id)
        if not task:
            return
        
        # Check if cancelled before starting
        if task.cancel_requested:
            return
        
        try:
            # Set download path
            download_path = os.path.join(self.hf_service.models_dir, task.model_name)
            with self._lock:
                if task.cancel_requested:
                    return
                task.status = DownloadStatus.DOWNLOADING
                task.progress = "Starting download..."
                task.download_path = download_path
            
            logger.info(f"Starting download: {task.model_name} (revision: {task.revision})")
            
            # Perform the actual download
            result = self.hf_service.download_model(
                model_name=task.model_name,
                revision=task.revision
            )
            
            # Check if cancelled during download
            if task.cancel_requested:
                return
            
            with self._lock:
                task.status = DownloadStatus.COMPLETED
                task.progress = result
                task.completed_at = utc_now()
            
            logger.info(f"Download completed: {task.model_name}")
            
        except Exception as e:
            # Don't overwrite cancelled status
            if task.cancel_requested:
                return
            
            logger.error(f"Download failed: {task.model_name} - {str(e)}")
            with self._lock:
                task.status = DownloadStatus.FAILED
                task.error = str(e)
                task.completed_at = utc_now()
    
    def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a download task"""
        task = self.downloads.get(task_id)
        if not task:
            return None
        
        # Calculate current downloaded size if downloading
        downloaded_size = 0
        downloaded_size_human = "0 B"
        if task.download_path and os.path.exists(task.download_path):
            downloaded_size = self._get_directory_size(task.download_path)
            downloaded_size_human = self._format_size(downloaded_size)
        
        # Calculate elapsed time on server to avoid clock skew issues
        now = utc_now()
        elapsed_seconds = int((now - task.started_at).total_seconds())
        
        return {
            "id": task.id,
            "model_name": task.model_name,
            "revision": task.revision,
            "status": task.status.value,
            "progress": task.progress,
            "error": task.error,
            "started_at": task.started_at.isoformat(),
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "downloaded_size": downloaded_size,
            "downloaded_size_human": downloaded_size_human,
            "elapsed_seconds": elapsed_seconds
        }
    
    def _get_directory_size(self, path: str) -> int:
        """Get total size of directory in bytes"""
        total = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total += os.path.getsize(fp)
                    except (OSError, FileNotFoundError):
                        pass
        except Exception:
            pass
        return total
    
    def _format_size(self, size: int) -> str:
        """Format size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
    
    def get_active_downloads(self) -> list:
        """Get all active (pending or downloading) tasks"""
        with self._lock:
            return [
                self.get_status(task_id)
                for task_id, task in self.downloads.items()
                if task.status in (DownloadStatus.PENDING, DownloadStatus.DOWNLOADING)
            ]
    
    def get_all_downloads(self) -> list:
        """Get all downloads (including recent completed/failed)"""
        with self._lock:
            return [
                self.get_status(task_id)
                for task_id in self.downloads.keys()
            ]
    
    def cleanup_completed(self, max_age_seconds: int = 3600):
        """Remove completed/failed tasks older than max_age_seconds"""
        now = utc_now()
        with self._lock:
            to_remove = []
            for task_id, task in self.downloads.items():
                if task.completed_at:
                    age = (now - task.completed_at).total_seconds()
                    if age > max_age_seconds:
                        to_remove.append(task_id)
            for task_id in to_remove:
                del self.downloads[task_id]
