"""
Pydantic schemas for API models
"""

from pydantic import BaseModel
from typing import Dict, Any, Optional, List


class ContainerStatus(BaseModel):
    id: str
    status: str
    created: str
    image: str
    labels: Dict[str, str]


class GPUMetric(BaseModel):
    index: int
    name: str
    temperature: int
    memory: Dict[str, Any]
    power: Dict[str, Any]
    utilization: Dict[str, int]


class SystemMetric(BaseModel):
    cpu: Dict[str, Any]
    memory: Dict[str, Any]
    disk: Dict[str, Any]
    network: Dict[str, Any]


class ModelInfo(BaseModel):
    name: str
    path: str
    size: int
    size_human: str


class ConfigPair(BaseModel):
    model_name: str
    config_path: str


class ErrorResponse(BaseModel):
    detail: str
