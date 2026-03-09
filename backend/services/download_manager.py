"""
Background download manager for HuggingFace models.
Uses multiprocessing for true cancellation and persists state to disk.
"""

import multiprocessing
import uuid
import os
import json
import shutil
import time
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from collections import deque
import logging

from utils import format_size

logger = logging.getLogger(__name__)


def _validate_model_path(models_dir: str, model_name: str) -> None:
    """Ensure model_name does not escape models_dir (path traversal)."""
    if not model_name or ".." in model_name or os.path.isabs(model_name):
        raise ValueError("Invalid model name")
    try:
        local_dir = os.path.join(models_dir, model_name)
        real_local = os.path.realpath(os.path.normpath(local_dir))
        real_models = os.path.realpath(models_dir)
        if os.path.commonpath([real_models, real_local]) != real_models:
            raise ValueError("Invalid model name")
    except (ValueError, OSError):
        raise ValueError("Invalid model name")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DownloadStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RESUMABLE = "resumable"


@dataclass
class DownloadTask:
    id: str
    model_name: str
    revision: Optional[str]
    status: DownloadStatus = DownloadStatus.PENDING
    progress: str = ""
    error: Optional[str] = None
    started_at: str = ""
    completed_at: Optional[str] = None
    download_path: Optional[str] = None
    expected_size: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "model_name": self.model_name,
            "revision": self.revision,
            "status": self.status.value,
            "progress": self.progress,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "download_path": self.download_path,
            "expected_size": self.expected_size,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any], models_dir: Optional[str] = None) -> Optional['DownloadTask']:
        """Deserialize from dict. Returns None if data is invalid (e.g. poisoned)."""
        task_id = d.get("id")
        if not task_id:
            return None
        try:
            status_val = d.get("status", "pending")
            status = DownloadStatus(status_val) if status_val in [s.value for s in DownloadStatus] else DownloadStatus.FAILED
        except (ValueError, TypeError):
            status = DownloadStatus.FAILED
        model_name = d.get("model_name", "")
        if models_dir and model_name:
            try:
                _validate_model_path(models_dir, model_name)
            except ValueError:
                return None
        return cls(
            id=str(task_id),
            model_name=model_name,
            revision=d.get("revision"),
            status=status,
            progress=d.get("progress", ""),
            error=d.get("error"),
            started_at=d.get("started_at", ""),
            completed_at=d.get("completed_at"),
            download_path=d.get("download_path"),
            expected_size=d.get("expected_size"),
        )


def _download_worker_fn(model_name: str, revision: Optional[str], models_dir: str):
    """Runs in a child process. Performs the actual download."""
    from huggingface_hub import HfApi
    api = HfApi()
    local_dir = os.path.join(models_dir, model_name)
    os.makedirs(local_dir, exist_ok=True)
    api.snapshot_download(
        repo_id=model_name,
        revision=revision,
        local_dir=local_dir,
    )


class DownloadManager:
    MAX_CONCURRENT = 2

    def __init__(self, hf_service, config_service=None):
        self.hf_service = hf_service
        self.config_service = config_service
        self.downloads: Dict[str, DownloadTask] = {}
        self._processes: Dict[str, multiprocessing.Process] = {}
        self._speed_samples: Dict[str, deque] = {}
        self._lock = threading.Lock()
        self._state_file = os.path.join(
            os.environ.get("VLLM_CONFIG_DIR", "/vllm-configs"),
            "downloads.json"
        )
        self._load_state()
        self._start_monitor_thread()

    def _load_state(self):
        """Load persisted download state and mark interrupted downloads as resumable."""
        if not os.path.exists(self._state_file):
            return
        try:
            with open(self._state_file, 'r') as f:
                data = json.load(f)
            models_dir = getattr(self.hf_service, "models_dir", None) or os.environ.get("VLLM_MODELS_DIR", "/models")
            for task_dict in data.get("tasks", []):
                task = DownloadTask.from_dict(task_dict, models_dir=models_dir)
                if task is None:
                    continue
                if task.status in (DownloadStatus.PENDING, DownloadStatus.DOWNLOADING):
                    task.status = DownloadStatus.RESUMABLE
                    task.progress = "Interrupted — can be resumed"
                self.downloads[task.id] = task
            logger.info(f"Loaded {len(self.downloads)} download tasks from disk")
        except Exception as e:
            logger.warning(f"Failed to load download state: {e}")

    def _save_state(self):
        """Persist current download state to disk."""
        try:
            data = {"tasks": [t.to_dict() for t in self.downloads.values()]}
            with open(self._state_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save download state: {e}")

    def _start_monitor_thread(self):
        """Background thread that tracks download progress and detects completion."""
        def monitor():
            while True:
                time.sleep(2)
                with self._lock:
                    for task_id, proc in list(self._processes.items()):
                        task = self.downloads.get(task_id)
                        if not task:
                            continue

                        # Track download speed
                        if task.download_path and os.path.exists(task.download_path):
                            size = self._get_directory_size(task.download_path)
                            samples = self._speed_samples.setdefault(task_id, deque(maxlen=15))
                            samples.append((time.time(), size))

                        if not proc.is_alive():
                            if task.status == DownloadStatus.DOWNLOADING:
                                if proc.exitcode == 0:
                                    task.status = DownloadStatus.COMPLETED
                                    task.progress = "Download complete"
                                    task.completed_at = utc_now().isoformat()
                                    logger.info(f"Download completed: {task.model_name}")
                                    if self.config_service and task.download_path:
                                        try:
                                            self.config_service.generate_config_for_model(
                                                task.model_name, task.download_path
                                            )
                                        except Exception as e:
                                            logger.warning(f"Auto-config generation failed: {e}")
                                else:
                                    task.status = DownloadStatus.FAILED
                                    task.error = f"Process exited with code {proc.exitcode}"
                                    task.completed_at = utc_now().isoformat()
                                    logger.error(f"Download failed: {task.model_name} (exit {proc.exitcode})")
                                self._save_state()
                            del self._processes[task_id]
                            self._speed_samples.pop(task_id, None)

                    self._cleanup_completed()

        t = threading.Thread(target=monitor, daemon=True)
        t.start()

    def start_download(self, model_name: str, revision: Optional[str] = None,
                       expected_size: Optional[int] = None) -> str:
        """Start a background download and return task ID."""
        _validate_model_path(self.hf_service.models_dir, model_name)
        with self._lock:
            for existing in self.downloads.values():
                if existing.model_name == model_name and existing.status in (
                    DownloadStatus.PENDING, DownloadStatus.DOWNLOADING
                ):
                    raise ValueError(f"Model {model_name} is already being downloaded")

            active_count = sum(1 for p in self._processes.values() if p.is_alive())
            if active_count >= self.MAX_CONCURRENT:
                raise ValueError(f"Maximum concurrent downloads ({self.MAX_CONCURRENT}) reached. Try again later.")

        task_id = str(uuid.uuid4())[:8]
        download_path = os.path.join(self.hf_service.models_dir, model_name)

        task = DownloadTask(
            id=task_id,
            model_name=model_name,
            revision=revision,
            status=DownloadStatus.DOWNLOADING,
            started_at=utc_now().isoformat(),
            download_path=download_path,
            expected_size=expected_size,
            progress="Starting download...",
        )

        proc = multiprocessing.Process(
            target=_download_worker_fn,
            args=(model_name, revision, self.hf_service.models_dir),
            daemon=True,
        )

        with self._lock:
            self.downloads[task_id] = task
            self._processes[task_id] = proc
            self._save_state()

        proc.start()
        logger.info(f"Download started: {model_name} (pid={proc.pid}, task={task_id})")
        return task_id

    def resume_download(self, task_id: str) -> bool:
        """Resume a previously interrupted download."""
        task = self.downloads.get(task_id)
        if not task or task.status != DownloadStatus.RESUMABLE:
            return False
        try:
            _validate_model_path(self.hf_service.models_dir, task.model_name)
        except ValueError:
            return False

        with self._lock:
            task.status = DownloadStatus.DOWNLOADING
            task.started_at = utc_now().isoformat()
            task.completed_at = None
            task.error = None
            task.progress = "Resuming download..."

        proc = multiprocessing.Process(
            target=_download_worker_fn,
            args=(task.model_name, task.revision, self.hf_service.models_dir),
            daemon=True,
        )

        with self._lock:
            self._processes[task_id] = proc
            self._save_state()

        proc.start()
        logger.info(f"Download resumed: {task.model_name} (pid={proc.pid})")
        return True

    def cancel_download(self, task_id: str) -> bool:
        """Cancel a download by terminating the child process."""
        task = self.downloads.get(task_id)
        if not task:
            return False

        if task.status not in (DownloadStatus.PENDING, DownloadStatus.DOWNLOADING, DownloadStatus.RESUMABLE):
            return False

        proc = self._processes.get(task_id)
        if proc and proc.is_alive():
            proc.terminate()
            proc.join(timeout=10)
            if proc.is_alive():
                proc.kill()
                proc.join(timeout=5)
            logger.info(f"Download process terminated: {task.model_name}")

        with self._lock:
            task.status = DownloadStatus.CANCELLED
            task.error = "Cancelled by user"
            task.completed_at = utc_now().isoformat()
            self._processes.pop(task_id, None)
            self._speed_samples.pop(task_id, None)
            self._save_state()

        if task.download_path and os.path.exists(task.download_path):
            try:
                shutil.rmtree(task.download_path)
                logger.info(f"Cleaned up: {task.download_path}")
            except Exception as e:
                logger.warning(f"Cleanup failed: {e}")

        return True

    def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a download task with speed and progress info."""
        task = self.downloads.get(task_id)
        if not task:
            return None

        downloaded_size = 0
        if task.download_path and os.path.exists(task.download_path):
            downloaded_size = self._get_directory_size(task.download_path)

        speed_bps = 0.0
        samples = self._speed_samples.get(task_id)
        if samples and len(samples) >= 2:
            oldest_time, oldest_size = samples[0]
            newest_time, newest_size = samples[-1]
            dt = newest_time - oldest_time
            if dt > 0:
                speed_bps = (newest_size - oldest_size) / dt

        eta_seconds = None
        if speed_bps > 0 and task.expected_size and task.expected_size > downloaded_size:
            eta_seconds = int((task.expected_size - downloaded_size) / speed_bps)

        started = datetime.fromisoformat(task.started_at) if task.started_at else utc_now()
        elapsed_seconds = int((utc_now() - started).total_seconds())

        progress_pct = None
        if task.expected_size and task.expected_size > 0:
            progress_pct = min(100.0, (downloaded_size / task.expected_size) * 100)

        return {
            "id": task.id,
            "model_name": task.model_name,
            "revision": task.revision,
            "status": task.status.value,
            "progress": task.progress,
            "error": task.error,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "downloaded_size": downloaded_size,
            "downloaded_size_human": format_size(downloaded_size),
            "expected_size": task.expected_size,
            "expected_size_human": format_size(task.expected_size) if task.expected_size else None,
            "progress_pct": round(progress_pct, 1) if progress_pct is not None else None,
            "speed_bps": int(speed_bps),
            "speed_human": f"{format_size(int(speed_bps))}/s" if speed_bps > 0 else None,
            "eta_seconds": eta_seconds,
            "elapsed_seconds": elapsed_seconds,
        }

    def get_active_downloads(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                self.get_status(tid)
                for tid, task in self.downloads.items()
                if task.status in (DownloadStatus.PENDING, DownloadStatus.DOWNLOADING)
            ]

    def get_all_downloads(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [self.get_status(tid) for tid in self.downloads]

    def _cleanup_completed(self, max_age_seconds: int = 3600):
        """Remove old completed/failed/cancelled tasks."""
        now = utc_now()
        to_remove = []
        for task_id, task in self.downloads.items():
            if task.completed_at:
                try:
                    completed = datetime.fromisoformat(task.completed_at)
                    if (now - completed).total_seconds() > max_age_seconds:
                        to_remove.append(task_id)
                except (ValueError, TypeError):
                    pass
        for task_id in to_remove:
            del self.downloads[task_id]
        if to_remove:
            self._save_state()

    def _get_directory_size(self, path: str) -> int:
        total = 0
        try:
            for dirpath, _, filenames in os.walk(path):
                for f in filenames:
                    try:
                        total += os.path.getsize(os.path.join(dirpath, f))
                    except (OSError, FileNotFoundError):
                        pass
        except Exception:
            pass
        return total
