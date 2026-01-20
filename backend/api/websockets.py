"""
WebSocket endpoints for real-time updates
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Optional
import asyncio
import json
import logging
from services.gpu_service import GPUService
from services.docker_service import DockerService

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.monitoring_tasks: Dict[WebSocket, asyncio.Task] = {}
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.monitoring_tasks:
            self.monitoring_tasks[websocket].cancel()
            del self.monitoring_tasks[websocket]
    
    async def start_monitoring(
        self, 
        websocket: WebSocket, 
        gpu_service: GPUService,
        docker_service: DockerService
    ):
        """Start combined monitoring and send updates via WebSocket"""
        import os
        from datetime import datetime
        
        # Get timezone from environment
        timezone = os.environ.get('TZ', 'UTC')
        
        async def monitor():
            try:
                while True:
                    # Get GPU metrics
                    gpu_metrics = gpu_service.get_gpu_metrics()
                    
                    # Get system metrics
                    system_metrics = gpu_service.get_system_metrics()
                    
                    # Get container status for vLLM inference containers only
                    container_status = docker_service.get_inference_container_status()
                    
                    # Send combined update
                    await websocket.send_text(json.dumps({
                        "type": "monitoring_update",
                        "data": {
                            "gpu": gpu_metrics,
                            "system": system_metrics,
                            "containers": container_status,
                            "timezone": timezone,
                            "server_time": datetime.now().isoformat()
                        }
                    }))
                    
                    await asyncio.sleep(2)  # Update every 2 seconds
            except WebSocketDisconnect:
                pass
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                try:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": str(e)
                    }))
                except:
                    pass
        
        task = asyncio.create_task(monitor())
        self.monitoring_tasks[websocket] = task
        return task


manager = ConnectionManager()


@router.websocket("/updates")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time monitoring updates"""
    await manager.connect(websocket)
    monitoring_task: Optional[asyncio.Task] = None
    
    try:
        # Access app state through websocket.app.state
        gpu_service: GPUService = websocket.app.state.gpu_service
        docker_service: DockerService = websocket.app.state.docker_service
        monitoring_task = await manager.start_monitoring(websocket, gpu_service, docker_service)
        
        # Keep connection open and handle client messages
        while True:
            try:
                data = await websocket.receive_text()
                # Handle client messages (e.g., change update interval)
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass
            
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)
