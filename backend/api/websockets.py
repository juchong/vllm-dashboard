"""
WebSocket endpoints for real-time updates
"""

import asyncio
import json
import logging
import os
from typing import Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from database import get_db
from security import extract_client_ip_from_scope
from services.auth_service import AuthService
from services.docker_service import DockerService
from services.gpu_service import GPUService

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_token_from_websocket(websocket: WebSocket) -> Optional[str]:
    """Extract session token from WebSocket cookies."""
    for name, value in websocket.scope.get("headers", []):
        if name == b"cookie":
            for part in value.decode().split(";"):
                if "=" in part:
                    k, v = part.strip().split("=", 1)
                    if k.strip() == "session":
                        return v.strip()
    return None


def _get_csrf_token_from_websocket(websocket: WebSocket) -> Optional[str]:
    """Extract CSRF token from WebSocket cookies."""
    for name, value in websocket.scope.get("headers", []):
        if name == b"cookie":
            for part in value.decode().split(";"):
                if "=" in part:
                    k, v = part.strip().split("=", 1)
                    if k.strip() == "csrf_token":
                        return v.strip()
    return None


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.connection_client_ips: Dict[WebSocket, str] = {}
        self.monitoring_tasks: Dict[WebSocket, asyncio.Task] = {}
        self.max_connections_per_ip = int(os.environ.get("WS_MAX_CONNECTIONS_PER_IP", "5"))
        self.idle_timeout_seconds = int(os.environ.get("WS_IDLE_TIMEOUT_SECONDS", "60"))
        self.csrf_token_map: Dict[WebSocket, str] = {}  # Map connections to their CSRF tokens for validation

    async def connect(self, websocket: WebSocket):
        client_ip = extract_client_ip_from_scope(websocket.scope)
        from_same_ip = [ws for ws in self.active_connections if self.connection_client_ips.get(ws) == client_ip]
        if len(from_same_ip) >= self.max_connections_per_ip:
            await websocket.close(code=4008, reason="Too many connections from client")
            raise WebSocketDisconnect()
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_client_ips[websocket] = client_ip

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.connection_client_ips.pop(websocket, None)
        self.csrf_token_map.pop(websocket, None)
        task = self.monitoring_tasks.pop(websocket, None)
        if task:
            task.cancel()
    
    async def start_monitoring(
        self, 
        websocket: WebSocket, 
        gpu_service: GPUService,
        docker_service: DockerService,
        known_container_names: set = None
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
                    container_status = docker_service.get_inference_container_status(
                        known_names=known_container_names
                    )
                    
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
                        "message": "An error occurred"
                    }))
                except:
                    pass
        
        task = asyncio.create_task(monitor())
        self.monitoring_tasks[websocket] = task
        return task


manager = ConnectionManager()


@router.websocket("/updates")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time monitoring updates. Requires authentication."""
    ws_origins_raw = os.environ.get("WS_ALLOWED_ORIGINS")
    if not ws_origins_raw:
        ws_origins_raw = os.environ.get("CORS_ORIGINS", "http://localhost:8080,http://localhost:5173")
    allowed_origins = {
        origin.strip()
        for origin in ws_origins_raw.split(",")
        if origin.strip()
    }
    origin = websocket.headers.get("origin")
    if origin not in allowed_origins:
        await websocket.close(code=4003, reason="Origin not allowed")
        return

    token = _get_token_from_websocket(websocket)
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return

    db = next(get_db())
    try:
        auth_service = AuthService(db)
        user = auth_service.verify_token(token)
        if not user or not user.is_active:
            await websocket.close(code=4001, reason="Invalid or expired token")
            return
        
        csrf_token = _get_csrf_token_from_websocket(websocket)
    finally:
        db.close()

    try:
        await manager.connect(websocket)
        if csrf_token:
            manager.csrf_token_map[websocket] = csrf_token
        else:
            logger.warning(f"WebSocket connection without CSRF token from origin: {origin}")

        gpu_service = websocket.app.state.gpu_service
        docker_service = websocket.app.state.docker_service
        registry = getattr(websocket.app.state, 'instance_registry', None)
        known_names = registry.get_all_container_names() if registry else None
        task = await manager.start_monitoring(websocket, gpu_service, docker_service, known_names)

        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            manager.disconnect(websocket)
    except WebSocketDisconnect:
        pass
