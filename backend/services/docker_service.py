"""
Docker service for container management
"""

import docker
from docker.errors import DockerException, NotFound, APIError
from typing import Dict, Any, Optional, List
import subprocess
import os
from pathlib import Path


class DockerService:
    def __init__(self):
        import os
        # Clear any Docker environment variables that might interfere
        if 'DOCKER_HOST' in os.environ:
            del os.environ['DOCKER_HOST']
        if 'DOCKER_CONTEXT' in os.environ:
            del os.environ['DOCKER_CONTEXT']
        if 'DOCKER_TLS_VERIFY' in os.environ:
            del os.environ['DOCKER_TLS_VERIFY']
        
        # Set DOCKER_HOST explicitly to use the socket
        os.environ['DOCKER_HOST'] = 'unix:///var/run/docker.sock'
        
        # Initialize Docker client
        self.client = docker.from_env()
        self.compose_path = os.environ.get("VLLM_COMPOSE_PATH", "/vllm-compose")
    
    def start_container(self, container_name: str, profile: Optional[str] = None) -> str:
        """Start a container using docker compose"""
        cmd = [
            "docker", "compose",
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
                check=True
            )
            return f"Container {container_name} started successfully"
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to start container: {e.stderr}")
    
    def stop_container(self, container_name: str) -> str:
        """Stop a container"""
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
                        "labels": container.labels
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
                        "labels": container.labels
                    }
        except Exception as e:
            raise Exception(f"Failed to get container status: {str(e)}")
        
        return status
    
    def get_container_logs(self, container_name: str, tail: int = 100) -> str:
        """Get container logs"""
        try:
            container = self.client.containers.get(container_name)
            logs = container.logs(tail=tail, stdout=True, stderr=True, timestamps=True)
            return logs.decode('utf-8')
        except NotFound:
            raise Exception(f"Container {container_name} not found")
        except APIError as e:
            raise Exception(f"Failed to get logs: {str(e)}")
    
    def stream_container_logs(self, container_name: str, tail: int = 100):
        """Stream container logs in real-time"""
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
