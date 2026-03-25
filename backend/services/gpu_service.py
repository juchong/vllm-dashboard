"""
GPU monitoring and power management service.
"""

import json
import os
import threading
from typing import Dict, Any, List, Optional

import psutil
import logging

logger = logging.getLogger(__name__)

try:
    import pynvml
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False
    pynvml = None


class GPUService:
    def __init__(self):
        self.nvml_initialized = False
        self.device_count = 0
        self._power_limits_path = os.path.join(
            os.environ.get("VLLM_CONFIG_DIR", "/vllm-configs"),
            "gpu_power_limits.json",
        )
        self._lock = threading.Lock()

        if not NVML_AVAILABLE:
            logger.warning("pynvml not available - GPU monitoring disabled")
            return

        try:
            pynvml.nvmlInit()
            self.device_count = pynvml.nvmlDeviceGetCount()
            self.nvml_initialized = True
            logger.info(f"NVML initialized successfully, found {self.device_count} GPU(s)")
        except Exception as e:
            logger.warning(f"Failed to initialize NVIDIA ML (GPU monitoring disabled): {e}")
            return

        self._load_and_apply_power_limits()

    def _load_and_apply_power_limits(self) -> None:
        """Read persisted power limits and apply them via NVML."""
        saved = self._read_power_limits_file()
        if not saved:
            return
        for idx_str, watts in saved.items():
            idx = int(idx_str)
            if idx >= self.device_count:
                logger.warning("[gpu-power] Saved limit for GPU %d but only %d GPUs present, skipping", idx, self.device_count)
                continue
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
                pynvml.nvmlDeviceSetPowerManagementLimit(handle, int(watts * 1000))
                logger.info("[gpu-power] Applied saved power limit %dW to GPU %d", watts, idx)
            except pynvml.NVMLError as e:
                logger.warning("[gpu-power] Failed to apply saved limit to GPU %d: %s", idx, e)

    def _read_power_limits_file(self) -> Dict[str, int]:
        try:
            if os.path.exists(self._power_limits_path):
                with open(self._power_limits_path, "r") as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("[gpu-power] Failed to read %s: %s", self._power_limits_path, e)
        return {}

    def _write_power_limits_file(self, data: Dict[str, int]) -> None:
        try:
            with open(self._power_limits_path, "w") as f:
                json.dump(data, f)
        except IOError as e:
            logger.error("[gpu-power] Failed to write %s: %s", self._power_limits_path, e)

    def get_power_constraints(self, gpu_index: int) -> Dict[str, Any]:
        """Return min/max/default power limits in watts for a GPU."""
        if not self.nvml_initialized or gpu_index >= self.device_count:
            raise ValueError(f"Invalid GPU index: {gpu_index}")
        handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
        min_mw, max_mw = pynvml.nvmlDeviceGetPowerManagementLimitConstraints(handle)
        default_mw = pynvml.nvmlDeviceGetPowerManagementDefaultLimit(handle)
        current_mw = pynvml.nvmlDeviceGetPowerManagementLimit(handle)
        return {
            "gpu_index": gpu_index,
            "min_watts": min_mw // 1000,
            "max_watts": max_mw // 1000,
            "default_watts": default_mw // 1000,
            "current_watts": current_mw // 1000,
        }

    def get_all_power_info(self) -> List[Dict[str, Any]]:
        """Return power constraints for every GPU."""
        if not self.nvml_initialized:
            return []
        results = []
        for i in range(self.device_count):
            try:
                results.append(self.get_power_constraints(i))
            except Exception as e:
                logger.warning("[gpu-power] Could not get constraints for GPU %d: %s", i, e)
        return results

    def set_power_limit(self, gpu_index: int, limit_watts: int) -> Dict[str, Any]:
        """Set and persist a GPU power limit in watts."""
        if not self.nvml_initialized:
            raise RuntimeError("NVML not initialized")
        if gpu_index < 0 or gpu_index >= self.device_count:
            raise ValueError(f"Invalid GPU index: {gpu_index}")

        handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
        min_mw, max_mw = pynvml.nvmlDeviceGetPowerManagementLimitConstraints(handle)
        limit_mw = limit_watts * 1000

        if limit_mw < min_mw or limit_mw > max_mw:
            raise ValueError(
                f"Power limit {limit_watts}W is outside allowed range "
                f"[{min_mw // 1000}W, {max_mw // 1000}W]"
            )

        pynvml.nvmlDeviceSetPowerManagementLimit(handle, limit_mw)
        logger.info("[gpu-power] Set GPU %d power limit to %dW", gpu_index, limit_watts)

        with self._lock:
            saved = self._read_power_limits_file()
            saved[str(gpu_index)] = limit_watts
            self._write_power_limits_file(saved)

        return self.get_power_constraints(gpu_index)

    def get_gpu_metrics(self) -> List[Dict[str, Any]]:
        """Get GPU metrics for all GPUs."""
        if not self.nvml_initialized or not NVML_AVAILABLE:
            return []

        metrics = []

        try:
            for i in range(self.device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)

                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode('utf-8')

                temp = pynvml.nvmlDeviceGetTemperature(
                    handle, pynvml.NVML_TEMPERATURE_GPU
                )

                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)

                try:
                    power = pynvml.nvmlDeviceGetPowerUsage(handle)
                    power_limit = pynvml.nvmlDeviceGetPowerManagementLimit(handle)
                    min_mw, max_mw = pynvml.nvmlDeviceGetPowerManagementLimitConstraints(handle)
                    default_mw = pynvml.nvmlDeviceGetPowerManagementDefaultLimit(handle)
                except pynvml.NVMLError:
                    power = 0
                    power_limit = 0
                    min_mw = 0
                    max_mw = 0
                    default_mw = 0

                util = pynvml.nvmlDeviceGetUtilizationRates(handle)

                metrics.append({
                    "index": i,
                    "name": name,
                    "temperature": temp,
                    "memory": {
                        "total": mem_info.total,
                        "used": mem_info.used,
                        "free": mem_info.free,
                        "usage_percent": (mem_info.used / mem_info.total) * 100 if mem_info.total > 0 else 0
                    },
                    "power": {
                        "usage": power,
                        "limit": power_limit,
                        "default_limit": default_mw,
                        "min_limit": min_mw,
                        "max_limit": max_mw,
                    },
                    "utilization": {
                        "gpu": util.gpu,
                        "memory": util.memory
                    }
                })
        except Exception as e:
            logger.error(f"Failed to get GPU metrics: {e}")
            return []

        return metrics

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get system metrics."""
        try:
            return {
                "cpu": {
                    "percent": psutil.cpu_percent(interval=0.1),
                    "count": psutil.cpu_count()
                },
                "memory": {
                    "total": psutil.virtual_memory().total,
                    "available": psutil.virtual_memory().available,
                    "used": psutil.virtual_memory().used,
                    "percent": psutil.virtual_memory().percent
                },
                "disk": {
                    "total": psutil.disk_usage('/').total,
                    "used": psutil.disk_usage('/').used,
                    "free": psutil.disk_usage('/').free,
                    "percent": psutil.disk_usage('/').percent
                },
                "network": {
                    "io": psutil.net_io_counters()
                }
            }
        except Exception as e:
            raise Exception(f"Failed to get system metrics: {str(e)}")

    def __del__(self):
        """Cleanup NVIDIA ML."""
        if self.nvml_initialized and NVML_AVAILABLE:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
