"""Pydantic schemas for request/response serialization"""
from datetime import datetime
from typing import List, Optional, Any

from pydantic import BaseModel


# --- Task ---

class TaskCreate(BaseModel):
    name: str = ""
    mode: str = "mass-produce"  # mass-produce | llm
    config: dict = {}


class TaskResponse(BaseModel):
    id: int
    name: str
    mode: str
    status: str
    progress: float
    total_features: Optional[int] = None
    passed_features: Optional[int] = None
    deployed_version: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    logs: List[dict] = []

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    items: List[TaskResponse]
    total: int


class TaskLogEntry(BaseModel):
    id: int
    task_id: int
    level: str
    message: str
    timestamp: str


# --- Feature Version ---

class FeatureVersionResponse(BaseModel):
    version: str
    task_id: Optional[int] = None
    total_features: int
    passed_features: int
    created_at: str


class FeatureVersionListResponse(BaseModel):
    items: List[FeatureVersionResponse]


# --- Feature Metric ---

class FeatureMetricResponse(BaseModel):
    feature_name: str
    iv: Optional[float] = None
    psi: Optional[float] = None
    coverage: Optional[float] = None
    is_passed: bool


class FeatureMetricsResponse(BaseModel):
    version: str
    total: int
    passed: int
    items: List[FeatureMetricResponse]


# --- Agent Status ---

class AgentInfo(BaseModel):
    name: str
    display_name: str
    status: str  # idle | running | completed
    last_run_at: Optional[str] = None
    description: str


class AgentStatusResponse(BaseModel):
    agents: List[AgentInfo]
    total_tasks: int
    latest_version: Optional[str] = None
    passed_features_total: int


# --- Generic ---

class HealthResponse(BaseModel):
    status: str
    version: str
