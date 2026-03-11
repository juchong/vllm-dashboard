"""
Docker service for container management.
Supports both Docker Compose (default instance) and Docker SDK (dynamic instances).
"""

import os
import re
import docker
from docker.errors import NotFound, APIError
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
import subprocess
import logging

from security import redact_log_content

logger = logging.getLogger(__name__)

SAFE_CONTAINER_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_container_name(name: str, allow_dashboard_proxy: bool = False) -> None:
    """Reject container names that could target arbitrary containers."""
    if not name or not SAFE_CONTAINER_PATTERN.match(name):
        raise ValueError("Invalid container name")
    is_vllm = "vllm" in name
    is_litellm = name == "litellm" or name == "litellm-db"
    if not is_vllm and not is_litellm:
        raise ValueError("Container must be a vLLM or LiteLLM container")
    if not allow_dashboard_proxy and ("dashboard" in name or "proxy" in name):
        raise ValueError("Cannot operate on dashboard or proxy containers")


@dataclass
class InstanceContainerConfig:
    """Configuration for creating a vLLM container via Docker SDK."""
    image: str
    container_name: str
    environment: Dict[str, str] = field(default_factory=dict)
    volumes: Dict[str, Dict[str, str]] = field(default_factory=dict)
    command: str = ""
    gpu_device_ids: Optional[List[str]] = None
    network: str = "traefik"
    port: int = 8000
    labels: Dict[str, str] = field(default_factory=dict)
    healthcheck: Optional[Dict[str, Any]] = None
    ports: Optional[Dict[str, int]] = None
    mem_limit: Optional[str] = "96g"


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

    # ── Compose-based operations (default instance) ──────────────────

    def start_container(self, container_name: str, profile: Optional[str] = None) -> str:
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
            subprocess.run(
                cmd, cwd=self.compose_path, capture_output=True, text=True,
                check=True, env=self._subprocess_env,
            )
            return f"Container {container_name} started successfully"
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to start container: {e.stderr}")

    def stop_container(self, container_name: str) -> str:
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
        _validate_container_name(container_name)
        try:
            container = self.client.containers.get(container_name)
            container.restart()
            return f"Container {container_name} restarted successfully"
        except NotFound:
            raise Exception(f"Container {container_name} not found")
        except APIError as e:
            raise Exception(f"Failed to restart container: {str(e)}")

    # ── SDK-based operations (dynamic instances) ─────────────────────

    def create_vllm_container(self, config: InstanceContainerConfig):
        """Create and start a vLLM container via Docker SDK."""
        device_requests = []
        if config.gpu_device_ids is None:
            device_requests = [docker.types.DeviceRequest(
                count=-1, capabilities=[["gpu"]]
            )]
        elif config.gpu_device_ids:
            device_requests = [docker.types.DeviceRequest(
                device_ids=config.gpu_device_ids, capabilities=[["gpu"]]
            )]

        healthcheck = config.healthcheck or {
            "test": ["CMD", "curl", "-f", f"http://localhost:{config.port}/health"],
            "interval": 60_000_000_000,
            "timeout": 10_000_000_000,
            "retries": 3,
            "start_period": 600_000_000_000,
        }

        container = self.client.containers.run(
            image=config.image,
            name=config.container_name,
            detach=True,
            ipc_mode="host",
            shm_size="4g",
            environment=config.environment,
            volumes=config.volumes,
            command=config.command,
            device_requests=device_requests or None,
            healthcheck=docker.types.Healthcheck(**healthcheck) if isinstance(healthcheck, dict) else None,
            network=config.network,
            labels=config.labels,
            restart_policy={"Name": "unless-stopped"},
            ports=config.ports or {},
            mem_limit=config.mem_limit,
        )
        logger.info(f"Created container {config.container_name} (id={container.id[:12]})")
        return container

    def remove_container(self, container_name: str) -> None:
        """Stop and remove a container. No-op if not found."""
        try:
            c = self.client.containers.get(container_name)
            c.stop(timeout=30)
            c.remove()
            logger.info(f"Removed container {container_name}")
        except NotFound:
            pass
        except APIError as e:
            logger.warning(f"Failed to remove container {container_name}: {e}")

    def pull_image(self, image: str) -> None:
        """Pull a Docker image via SDK."""
        logger.info(f"Pulling image: {image}")
        self.client.images.pull(image)
        logger.info(f"Image pulled: {image}")

    # ── Status queries ───────────────────────────────────────────────

    def get_container_status(self) -> Dict[str, Any]:
        """Get status of all vLLM containers."""
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

    def get_inference_container_status(self, known_names: Optional[Set[str]] = None) -> Dict[str, Any]:
        """Get status of vLLM inference containers.
        If known_names provided, match exactly. Otherwise use heuristic."""
        status = {}
        try:
            containers = self.client.containers.list(all=True)
            for container in containers:
                name = container.name

                if known_names is not None:
                    is_inference = name in known_names
                else:
                    is_inference = (
                        name.startswith("vllm") and
                        not any(x in name for x in ["dashboard", "proxy", "manager", "moe-tune"])
                    )

                if is_inference:
                    status[name] = {
                        "id": container.id,
                        "status": container.status,
                        "created": container.attrs.get("Created", ""),
                        "image": container.image.tags[0] if container.image.tags else "",
                        "labels": dict(container.labels) if container.labels else {},
                    }
        except Exception as e:
            raise Exception(f"Failed to get container status: {str(e)}")
        return status

    # ── Logs ─────────────────────────────────────────────────────────

    def get_container_logs(self, container_name: str, tail: int = 100) -> str:
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
        _validate_container_name(container_name, allow_dashboard_proxy=True)
        tail = max(1, min(tail, 10000))
        try:
            container = self.client.containers.get(container_name)
            return container.logs(
                tail=tail, stdout=True, stderr=True,
                timestamps=True, stream=True, follow=True
            )
        except NotFound:
            raise Exception(f"Container {container_name} not found")
        except APIError as e:
            raise Exception(f"Failed to stream logs: {str(e)}")

    # ── Metrics ──────────────────────────────────────────────────────

    def get_container_metrics(self) -> Dict[str, Any]:
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
