"""
Docker service for container management
"""

import os
import re
import docker
from docker.errors import NotFound, APIError
from typing import Dict, Any, Optional, List
import subprocess

from security import redact_log_content

# Safe chars for container names (alphanumeric, hyphen, underscore)
# Compose may prefix with project: ai-vllm-1, ai-vllm-mistral-1
SAFE_CONTAINER_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_container_name(name: str, allow_dashboard_proxy: bool = False) -> None:
    """Reject container names that could target arbitrary containers. Allow vLLM containers only."""
    if not name or not SAFE_CONTAINER_PATTERN.match(name):
        raise ValueError("Invalid container name")
    if "vllm" not in name:
        raise ValueError("Container must be a vLLM container")
    if not allow_dashboard_proxy and ("dashboard" in name or "proxy" in name):
        raise ValueError("Cannot operate on dashboard or proxy containers")


class DockerService:
    DOCKER_SOCKET = "unix:///var/run/docker.sock"

    def __init__(self):
        self.client = docker.DockerClient(base_url=self.DOCKER_SOCKET)
        self.compose_path = os.environ.get("VLLM_COMPOSE_PATH", "/vllm-compose")
        self._subprocess_env = {
            **os.environ,
            "DOCKER_HOST": self.DOCKER_SOCKET,
        }
        for key in ("DOCKER_CONTEXT", "DOCKER_TLS_VERIFY"):
            self._subprocess_env.pop(key, None)
    
    def start_container(self, container_name: str, profile: Optional[str] = None) -> str:
        """Start a container using docker compose"""
        _validate_container_name(container_name)
        cmd = [
            "docker", "compose",
            "-p", "ai",
            "--file", f"{self.compose_path}/compose.yaml"
        ]
        
        if profile:
            cmd.extend(["--profile", profile])
        
        cmd.extend(["up", "-d", container_name])
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.compose_path,
                capture_output=True,
                text=True,
                check=True,
                env=self._subprocess_env,
            )
            return f"Container {container_name} started successfully"
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to start container: {e.stderr}")
    
    def stop_container(self, container_name: str) -> str:
        """Stop a container"""
        _validate_container_name(container_name)
        try:
            container = self.client.containers.get(container_name)
            container.stop()
            return f"Container {container_name} stopped successfully"
        except NotFound:
            raise Exception(f"Container {container_name} not found")
        except APIError as e:
            raise Exception(f"Failed to stop container: {str(e)}")
    
    def restart_container(self, container_name: str) -> str:
        """Restart a container"""
        _validate_container_name(container_name)
        try:
            container = self.client.containers.get(container_name)
            container.restart()
            return f"Container {container_name} restarted successfully"
        except NotFound:
            raise Exception(f"Container {container_name} not found")
        except APIError as e:
            raise Exception(f"Failed to restart container: {str(e)}")
    
    def get_container_status(self) -> Dict[str, Any]:
        """Get status of all vLLM containers"""
        status = {}
        
        try:
            containers = self.client.containers.list(all=True)
            for container in containers:
                if "vllm" in container.name:
                    status[container.name] = {
                        "id": container.id,
                        "status": container.status,
                        "created": container.attrs.get("Created", ""),
                        "image": container.image.tags[0] if container.image.tags else "",
                        "labels": {}
                    }
        except Exception as e:
            raise Exception(f"Failed to get container status: {str(e)}")
        
        return status

    def get_inference_container_status(self) -> Dict[str, Any]:
        """Get status of vLLM inference containers only (not dashboard, proxy, manager)"""
        # These are the actual vLLM inference server containers
        inference_containers = {"vllm", "vllm-devstral", "vllm-qwen", "vllm-mistral"}
        status = {}
        
        try:
            containers = self.client.containers.list(all=True)
            for container in containers:
                # Match exact names or names that start with vllm- but aren't management containers
                name = container.name
                is_inference = (
                    name in inference_containers or
                    (name.startswith("vllm-") and 
                     not any(x in name for x in ["dashboard", "proxy", "manager", "moe-tune"]))
                )
                
                if is_inference:
                    status[container.name] = {
                        "id": container.id,
                        "status": container.status,
                        "created": container.attrs.get("Created", ""),
                        "image": container.image.tags[0] if container.image.tags else "",
                        "labels": {}
                    }
        except Exception as e:
            raise Exception(f"Failed to get container status: {str(e)}")
        
        return status
    
    def get_container_logs(self, container_name: str, tail: int = 100) -> str:
        """Get container logs. Optionally redacts sensitive key=value patterns when REDACT_CONTAINER_LOGS is enabled."""
        _validate_container_name(container_name, allow_dashboard_proxy=True)
        tail = max(1, min(tail, 10000))
        try:
            container = self.client.containers.get(container_name)
            logs = container.logs(tail=tail, stdout=True, stderr=True, timestamps=True)
            content = logs.decode('utf-8')
            if os.environ.get("REDACT_CONTAINER_LOGS", "true").lower() in {"1", "true", "yes"}:
                content = redact_log_content(content)
            return content
        except NotFound:
            raise Exception(f"Container {container_name} not found")
        except APIError as e:
            raise Exception(f"Failed to get logs: {str(e)}")
    
    def stream_container_logs(self, container_name: str, tail: int = 100):
        """Stream container logs in real-time"""
        _validate_container_name(container_name, allow_dashboard_proxy=True)
        tail = max(1, min(tail, 10000))
        try:
            container = self.client.containers.get(container_name)
            logs = container.logs(
                tail=tail,
                stdout=True,
                stderr=True,
                timestamps=True,
                stream=True,
                follow=True
            )
            
            # Return streaming response
            return logs
        except NotFound:
            raise Exception(f"Container {container_name} not found")
        except APIError as e:
            raise Exception(f"Failed to stream logs: {str(e)}")
    
    def get_container_metrics(self) -> Dict[str, Any]:
        """Get container resource usage"""
        metrics = {}
        
        try:
            containers = self.client.containers.list()
            for container in containers:
                if "vllm" in container.name:
                    stats = container.stats(stream=False)
                    metrics[container.name] = {
                        "cpu": stats.get("cpu_stats", {}),
                        "memory": stats.get("memory_stats", {}),
                        "network": stats.get("networks", {}),
                        "blkio": stats.get("blkio_stats", {})
                    }
        except Exception as e:
            raise Exception(f"Failed to get container metrics: {str(e)}")
        
        return metrics
