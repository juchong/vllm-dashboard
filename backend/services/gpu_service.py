"""
GPU monitoring service
"""

from typing import Dict, Any, List, Optional
import psutil
import time
import logging

logger = logging.getLogger(__name__)

# Try to import pynvml, but don't fail if unavailable
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
    
    def get_gpu_metrics(self) -> List[Dict[str, Any]]:
        """Get GPU metrics for all GPUs"""
        if not self.nvml_initialized or not NVML_AVAILABLE:
            return []
        
        metrics = []
        
        try:
            for i in range(self.device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                
                # Get GPU name
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode('utf-8')
                
                # Get temperature
                temp = pynvml.nvmlDeviceGetTemperature(
                    handle, pynvml.NVML_TEMPERATURE_GPU
                )
                
                # Get memory info
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                
                # Get power usage
                try:
                    power = pynvml.nvmlDeviceGetPowerUsage(handle)
                    power_limit = pynvml.nvmlDeviceGetPowerManagementLimit(handle)
                except pynvml.NVMLError:
                    power = 0
                    power_limit = 0
                
                # Get utilization
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
                        "limit": power_limit
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
        """Get system metrics"""
        try:
            return {
                "cpu": {
                    "percent": psutil.cpu_percent(interval=1),
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
        """Cleanup NVIDIA ML"""
        if self.nvml_initialized and NVML_AVAILABLE:
            try:
                pynvml.nvmlShutdown()
            except:
                pass
